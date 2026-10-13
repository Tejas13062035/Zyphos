#!/usr/bin/env python3
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import esp32_cam

LOG = ROOT / "state" / "presence_log.jsonl"
WAKE_FLAG = ROOT / "state" / "vc01_wake"

# --- presence (radar) ---
POLL_S = 0.2
ARRIVE_POLLS = 2           # consecutive polls with a real target before it counts as an arrival
MIN_TARGET_CM = 20         # a "target" reported at about 0 cm is radar noise, not a person
ABSENT_HOLD_S = 30         # radar must see nobody this long before it counts as a departure
SETTLED_EVERY_S = 30       # radar flickers between moving and stationary
PIR_ARMS_SCAN = True       # PIR motion starts looking for a face at once; it never decides a greeting
PIR_SCAN_COOLDOWN_S = 10

# --- who's in the room ---
USE_AMBIENT = True         # False = just take a photo burst on arrival
ENROLL_UNKNOWN = True      # True = a new stranger starts the "what's your name" flow
FACE_RETRIES = 3           # on arrival: retry this many times if no face is visible yet
FACE_RETRY_WAIT_S = 8
RESCAN_ON_MOTION = True    # someone starts moving after being still -> check for a new face
RESCAN_COOLDOWN_S = 30
HEARTBEAT_S = 120          # while occupied, look at the room at least this often

# --- photo burst (only when USE_AMBIENT = False) ---
BURST_N = 3
BURST_GAP_S = 0.3
COOLDOWN_S = 10

_scan_busy = threading.Event()
_present = threading.Event()   # set while the room is occupied
_last_trigger = 0.0


def log_event(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def burst(t_detect, state, dist):
    files = []
    name = esp32_cam.STATE_NAMES.get(state)
    for i in range(BURST_N):
        try:
            files.append(esp32_cam.capture_to_file("arrival"))
        except Exception as e:
            print(f"[watcher] capture {i} failed: {e}")
            time.sleep(0.5)
            continue
        if i < BURST_N - 1:
            time.sleep(BURST_GAP_S)
    lat = time.time() - t_detect
    log_event({"event": "arrival", "state": name, "distance_cm": dist,
               "images": files, "latency_s": round(lat, 1)})
    print(f"[watcher] arrival at {dist} cm - {len(files)} images in {lat:.1f}s")


def trigger_listen(hex_msg):
    """VC-01 heard the wake phrase. Drop a flag file the voice loop watches."""
    global _last_trigger
    if time.time() - _last_trigger < 3:      # the VC-01 may send several messages per phrase
        return
    _last_trigger = time.time()
    WAKE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    WAKE_FLAG.write_text(f"{time.time()} {hex_msg}\n")
    print(f"[watcher] VC-01 wake ({hex_msg})")
    log_event({"event": "wake", "hex": hex_msg})


def _scan_worker(reason, announce, retry, t_trig):
    t0 = time.time()
    try:
        from core import room_roster
        attempts = 0
        while True:
            attempts += 1
            res = room_roster.scan(announce=announce, enroll_unknown=ENROLL_UNKNOWN)
            if res["saw_face"] or not retry or attempts >= FACE_RETRIES or not _present.is_set():
                break
            time.sleep(FACE_RETRY_WAIT_S)
            if not _present.is_set():
                break
        secs = time.time() - t0
        in_room = room_roster.members()
        t = res.get("timing") or {}
        t_dec = res.get("decision_at")
        trig_to_decision = round(t_dec - t_trig, 2) if t_dec else None
        log_event({"event": "scan", "reason": reason, "saw_face": res["saw_face"],
                   "new": res["new"], "in_room": in_room, "frames": res.get("frames"),
                   "face_px": res.get("face_px"), "attempts": attempts, "seconds": round(secs, 1),
                   "trigger_to_decision_s": trig_to_decision, "timing": t,
                   "faces": res.get("face_log")})
        print(f"[watcher] scan ({reason}): new={res['new'] or 'none'} in_room={in_room} "
              f"frames={res.get('frames')} face_px={res.get('face_px')} ({secs:.1f}s)")
        print(f"[watcher]   trigger->decision={trig_to_decision}s | first_frame={t.get('first_frame_s')}s "
              f"ttfb={t.get('ttfb_s')}s download={t.get('download_s')}s detect={t.get('detect_s')}s "
              f"embed={t.get('embed_s')}s match={t.get('match_s')}s sharp={t.get('sharp')}")
    except Exception as e:
        log_event({"event": "scan_error", "error": str(e)[:200]})
        print(f"[watcher] scan failed: {e}")
    finally:
        _scan_busy.clear()


def start_scan(reason, announce=True, retry=False):
    if _scan_busy.is_set():
        return False
    _scan_busy.set()
    threading.Thread(target=_scan_worker, args=(reason, announce, retry, time.time()), daemon=True).start()
    return True


def _clear_roster():
    mod = sys.modules.get("core.room_roster")
    if mod:
        mod.clear()


def main():
    occupied = False
    absent_since = None
    last_state = 0
    last_pir = False
    valid_streak = 0
    last_burst = 0.0
    last_settled = 0.0
    last_scan = 0.0
    last_pir_scan = 0.0
    last_wake = None
    first_poll = True
    print("[watcher] looking for the ESP32-CAM...")
    while True:
        try:
            p = esp32_cam.presence()
        except Exception:
            time.sleep(1)   # ESP busy or offline; esp32_cam re-discovers after repeated failures
            continue

        wc = int(p.get("wake_count", 0))
        if last_wake is None:
            last_wake = wc               # ignore any count from before we started
        elif wc != last_wake:
            if wc > last_wake:
                trigger_listen(p.get("wake_hex", ""))
            last_wake = wc               # also covers an ESP reboot (count resets to 0)

        state = int(p.get("state", 0))
        dist = p.get("mov_cm") or p.get("stat_cm") or 0
        valid = state != 0 and dist >= MIN_TARGET_CM       # a real target, not radar noise
        valid_streak = valid_streak + 1 if valid else 0
        pir = bool(p.get("pir"))
        pir_edge = pir and not last_pir
        last_pir = pir
        state_name = esp32_cam.STATE_NAMES.get(state)
        now = time.time()

        if first_poll:
            first_poll = False
            if valid:                    # already in the room at startup: not an arrival
                occupied = True
                _present.set()
                if USE_AMBIENT:
                    last_scan = now
                    start_scan("startup", announce=False)   # learn who is here, say nothing
        elif valid:
            absent_since = None
            if not occupied:
                if valid_streak >= ARRIVE_POLLS:
                    occupied = True
                    _present.set()
                    log_event({"event": "arrival", "state": state_name, "distance_cm": dist})
                    print(f"[watcher] arrival at {dist} cm")
                    if USE_AMBIENT:
                        last_scan = now
                        start_scan("arrival", retry=True)
                    elif now - last_burst >= COOLDOWN_S:
                        burst(now, state, dist)
                        last_burst = time.time()
            else:
                if USE_AMBIENT and not _scan_busy.is_set():
                    motion = RESCAN_ON_MOTION and last_state == 2 and state in (1, 3)
                    beat = now - last_scan >= HEARTBEAT_S
                    if (motion and now - last_scan >= RESCAN_COOLDOWN_S) or beat:
                        last_scan = now
                        start_scan("motion" if motion and not beat else "heartbeat")
                if last_state in (1, 3) and state == 2:
                    if now - last_settled >= SETTLED_EVERY_S:
                        last_settled = now
                        log_event({"event": "settled", "distance_cm": p.get("stat_cm")})
                        print(f"[watcher] settled at {p.get('stat_cm')} cm")
        elif occupied:
            if absent_since is None:
                absent_since = now
            elif now - absent_since >= ABSENT_HOLD_S:
                occupied = False
                absent_since = None
                _present.clear()
                _clear_roster()          # room is empty: forget who was in it
                log_event({"event": "departure"})
                print("[watcher] departure")

        # PIR reacts faster than the radar: use it to start looking for a face immediately.
        # It never greets by itself, because a greeting needs a face that has been away for a while.
        if (PIR_ARMS_SCAN and USE_AMBIENT and pir_edge and not occupied
                and now - last_pir_scan >= PIR_SCAN_COOLDOWN_S):
            last_pir_scan = now
            last_scan = now
            if start_scan("pir", retry=True):
                print("[watcher] motion at the door - looking for a face")

        last_state = state if valid else 0
        time.sleep(1.0 if _scan_busy.is_set() else POLL_S)


if __name__ == "__main__":
    main()
