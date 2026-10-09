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

BURST_N = 3            # photos per arrival
BURST_GAP_S = 0.3      # pause between photos (each capture itself takes about 1 s)
COOLDOWN_S = 10        # minimum seconds between bursts, so sensor flapping can't spam photos
ABSENT_HOLD_S = 5      # sensors must read empty this long before it counts as a departure
SETTLED_EVERY_S = 30   # radar flickers between moving and stationary
POLL_S = 0.2
USE_PIR = True         # PIR reacts fastest to motion; set False if it triggers too often
USE_AMBIENT = True        # on arrival: identify the person and greet them; False = just take a photo burst
GREET_COOLDOWN_S = 300    # minimum seconds between face checks / greetings
GREET_ON_GAVE_UP = False  # False = stay silent when no face was found (avoids greeting an empty room)
ENROLL_UNKNOWN = True     # True = unknown faces start the "what's your name" flow


def log_event(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def burst(t_detect, state, dist):
    """Take the burst. The first photo is announced the moment it exists."""
    files = []
    name = esp32_cam.STATE_NAMES.get(state)
    for i in range(BURST_N):
        try:
            files.append(esp32_cam.capture_to_file("arrival"))
        except Exception as e:
            print(f"[watcher] capture {i} failed: {e}")
            time.sleep(0.5)
            continue
        if len(files) == 1:
            lat = time.time() - t_detect
            log_event({"event": "arrival", "state": name, "distance_cm": dist,
                       "images": list(files), "latency_s": round(lat, 1)})
            print(f"[watcher] arrival at {dist} cm - first image in {lat:.1f}s")
        if i < BURST_N - 1:
            time.sleep(BURST_GAP_S)
    lat = time.time() - t_detect
    if not files:
        log_event({"event": "arrival", "state": name, "distance_cm": dist,
                   "images": [], "latency_s": round(lat, 1)})
        print(f"[watcher] arrival at {dist} cm - no images captured")
    else:
        log_event({"event": "burst_done", "images": files, "latency_s": round(lat, 1)})
        print(f"[watcher] burst done: {len(files)} images in {lat:.1f}s")


_last_trigger = 0.0


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


_ambient_busy = threading.Event()


def _ambient_worker(t_start, dist):
    """Face check + greeting in the background, so polling and the VC-01 wake keep working."""
    try:
        from core.ambient_awareness import run_ambient_cycle
        result = run_ambient_cycle(greet_on_gave_up=GREET_ON_GAVE_UP,
                                   enroll_unknown=ENROLL_UNKNOWN)
        ok = isinstance(result, dict)
        status = result.get("status") if ok else None
        name = result.get("name") if ok else None
        secs = time.time() - t_start
        log_event({"event": "ambient", "status": status, "name": name,
                   "distance_cm": dist, "seconds": round(secs, 1)})
        print(f"[watcher] ambient: {status}" + (f" ({name})" if name else "") + f" in {secs:.1f}s")
    except Exception as e:
        log_event({"event": "ambient_error", "error": str(e)[:200]})
        print(f"[watcher] ambient cycle failed: {e}")
    finally:
        _ambient_busy.clear()


def main():
    occupied = False
    absent_since = None
    last_state = 0
    last_burst = 0.0
    last_ambient = 0.0
    last_settled = 0.0
    last_wake = None
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
        sensed = state != 0 or (USE_PIR and bool(p.get("pir")))
        dist = p.get("mov_cm") or p.get("stat_cm")
        state_name = esp32_cam.STATE_NAMES.get(state)

        if sensed:
            absent_since = None
            if not occupied:
                occupied = True
                if USE_AMBIENT:
                    if _ambient_busy.is_set() or time.time() - last_ambient < GREET_COOLDOWN_S:
                        log_event({"event": "arrival", "state": state_name,
                                   "distance_cm": dist, "note": "greeting cooldown"})
                        print(f"[watcher] arrival at {dist} cm (greeting cooldown)")
                    else:
                        last_ambient = time.time()
                        log_event({"event": "arrival", "state": state_name,
                                   "distance_cm": dist, "note": "face check started"})
                        print(f"[watcher] arrival at {dist} cm - checking face")
                        _ambient_busy.set()
                        threading.Thread(target=_ambient_worker,
                                         args=(time.time(), dist), daemon=True).start()
                elif time.time() - last_burst >= COOLDOWN_S:
                    burst(time.time(), state, dist)
                    last_burst = time.time()
                else:
                    log_event({"event": "arrival", "state": state_name,
                               "distance_cm": dist, "images": [], "note": "cooldown"})
                    print(f"[watcher] arrival at {dist} cm (cooldown, no burst)")
            elif last_state in (1, 3) and state == 2:
                if time.time() - last_settled >= SETTLED_EVERY_S:
                    last_settled = time.time()
                    log_event({"event": "settled", "distance_cm": p.get("stat_cm")})
                    print(f"[watcher] settled at {p.get('stat_cm')} cm")
        elif occupied:
            if absent_since is None:
                absent_since = time.time()
            elif time.time() - absent_since >= ABSENT_HOLD_S:
                occupied = False
                absent_since = None
                log_event({"event": "departure"})
                print("[watcher] departure")

        last_state = state
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
