#!/usr/bin/env python3
"""Stress test for the room-awareness pipeline: ESP32-CAM + radar, roster, watcher, face ID, TTS, greeting.

  python3 scripts/stress_test_room.py                 full run (stops the watcher + watchdog, restarts them at the end)
  python3 scripts/stress_test_room.py --quick         fewer iterations
  python3 scripts/stress_test_room.py --live          leave the watcher/watchdog running (realistic, but they compete for the ESP)
  python3 scripts/stress_test_room.py --soak 30       also poll the ESP for 30 minutes
  python3 scripts/stress_test_room.py --speak         also play one real greeting through the speakers
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from tools import esp32_cam

# pass/fail thresholds (my picks; adjust to taste)
PRESENCE_P95_S = 1.0
CAPTURE_MIN_OK = 0.95
LOADED_PRESENCE_P95_S = 3.0
KOKORO_P50_S = 2.0
GREETING_P50_S = 3.0
IDENTIFY_P95_S = 3.0

RESULTS = []


def record(sec, name, ok, detail="", warn=False):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    RESULTS.append((sec, name, status, detail))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def info(name, detail):
    RESULTS.append(("info", name, "INFO", detail))
    print(f"  [INFO] {name} - {detail}")


def section(title):
    print(f"\n== {title} ==")


def pct(vals, p):
    if not vals:
        return float("inf")
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def stats(vals):
    if not vals:
        return "no data"
    return f"p50={pct(vals, 50):.2f}s p95={pct(vals, 95):.2f}s max={max(vals):.2f}s"


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:
        record(fn.__name__, "section crashed", False, f"{type(e).__name__}: {e}")
        return None


def rss_mb(pattern):
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    best = None
    for pid in r.stdout.split():
        try:
            for line in open(f"/proc/{pid}/status"):
                if line.startswith("VmRSS:"):
                    mb = int(line.split()[1]) / 1024
                    best = mb if best is None else max(best, mb)
        except OSError:
            pass
    return best


def stop_services():
    subprocess.run(["pkill", "-f", "scripts/watchdog.py"])
    subprocess.run(["pkill", "-f", "scripts/presence_watcher.py"])
    time.sleep(1)


def start_services():
    subprocess.Popen(["bash", str(ROOT / "scripts" / "start_all.sh")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


# ---------------------------------------------------------------- tests

def t_services():
    section("Services running")
    checks = {"daemon": "zyphos.py --daemon", "watchdog": "scripts/watchdog.py",
              "presence watcher": "scripts/presence_watcher.py",
              "event reminder": "event_reminder.py", "kokoro": "uvicorn api.src.main:app"}
    deadline = time.time() + 45      # start_all.sh may still be launching services from the previous run
    for name, pat in checks.items():
        ok = False
        while True:
            r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
            ok = bool(r.stdout.strip())
            if ok or time.time() > deadline:
                break
            time.sleep(2)
        record("services", name, ok)


def t_roster():
    section("Roster logic (synthetic faces, no camera)")
    import numpy as np
    from core import room_roster as r
    rng = np.random.default_rng(7)

    def face():
        return rng.normal(size=128) * 0.0884          # norm about 1

    def noisy(v):
        return v + rng.normal(size=128) * 0.005       # same person, small variation

    r.clear()
    a, b = face(), face()
    record("roster", "empty roster sees nobody", not r._seen(a))
    r._add("Tejas", a)
    record("roster", "same person (noisy) is recognized", r._seen(noisy(a)))
    record("roster", "different person is NOT matched", not r._seen(b))
    r._add(None, b)
    names = r.members()
    record("roster", "members lists named + unknown", sorted(names) == ["Tejas", "unknown"], str(names))
    record("roster", "unknown person re-recognized", r._seen(noisy(b)))
    r._roster[0]["last"] = time.time() - r.ROSTER_TTL_S - 5
    record("roster", "stale person expires", r.members() == ["unknown"], str(r.members()))
    r.clear()
    record("roster", "clear() empties the roster", r.members() == [])

    for i in range(20):
        r._add(f"p{i}", face())
    t = time.time()
    for _ in range(1000):
        r._seen(face())
    dt = time.time() - t
    record("roster", "1000 lookups against 20 people < 1s", dt < 1.0, f"{dt * 1000:.0f} ms")
    r.clear()

    errs = []

    def worker():
        try:
            g = np.random.default_rng()
            for _ in range(300):
                v = g.normal(size=128) * 0.0884
                if not r._seen(v):
                    r._add(None, v)
                r.members()
        except Exception as e:
            errs.append(repr(e))

    ths = [threading.Thread(target=worker) for _ in range(8)]
    for t_ in ths:
        t_.start()
    for t_ in ths:
        t_.join(30)
    record("roster", "8 threads hammering it, no errors", not errs, errs[0] if errs else "")
    r.clear()


def t_watcher_logic():
    section("Watcher state machine (mocked ESP and scan)")
    import importlib.util
    import numpy as np
    from core import room_roster

    spec = importlib.util.spec_from_file_location("presence_watcher", ROOT / "scripts" / "presence_watcher.py")
    w = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w)

    class Stop(BaseException):
        pass

    class NeverBusy:
        def is_set(self):
            return False

        def set(self):
            pass

        def clear(self):
            pass

    calls = []

    def fake_scan(announce=True, enroll_unknown=True):
        calls.append(announce)
        return {"saw_face": True, "new": ["Tester"]}

    def P(state=0, pir=False, wake=0, hexv=""):
        return {"present": state != 0, "since_ms": 1000, "pir": pir, "wake_count": wake,
                "wake_hex": hexv, "state": state,
                "mov_cm": 150 if state in (1, 3) else 0, "mov_e": 100,
                "stat_cm": 150 if state in (2, 3) else 0, "stat_e": 100}

    tmpdir = Path(tempfile.mkdtemp())
    w.LOG = tmpdir / "log.jsonl"
    w.WAKE_FLAG = tmpdir / "wake"
    w.POLL_S = 0.05
    w.ABSENT_HOLD_S = 0.5
    w.RESCAN_COOLDOWN_S = 0.3
    w.HEARTBEAT_S = 999
    w.SETTLED_EVERY_S = 0.2
    w.FACE_RETRY_WAIT_S = 0.05

    orig_scan, orig_presence = room_roster.scan, esp32_cam.presence
    room_roster.scan = fake_scan

    def run(timeline):
        calls.clear()
        w.LOG.write_text("")
        if w.WAKE_FLAG.exists():
            w.WAKE_FLAG.unlink()
        w._present.clear()
        w._scan_busy = NeverBusy()
        w._last_trigger = 0.0
        total = sum(d for d, _ in timeline)
        start = time.time()

        def fake_presence(timeout=2):
            el = time.time() - start
            if el >= total:
                raise Stop()
            t0 = 0.0
            for d, p in timeline:
                t0 += d
                if el < t0:
                    if p is None:
                        raise ConnectionError("mock ESP offline")
                    return dict(p)
            raise Stop()

        esp32_cam.presence = fake_presence

        def target():
            try:
                w.main()
            except Stop:
                pass

        th = threading.Thread(target=target, daemon=True)
        with contextlib.redirect_stdout(io.StringIO()):
            th.start()
            th.join(total + 8)
            time.sleep(0.4)
        evs = [json.loads(line) for line in w.LOG.read_text().splitlines() if line.strip()]
        return th.is_alive(), evs, list(calls)

    def count(evs, name):
        return sum(1 for e in evs if e["event"] == name)

    try:
        # A: normal visit
        room_roster._add("dummy", np.zeros(128))
        alive, evs, cl = run([(0.6, P(0)), (1.0, P(2)), (1.0, P(1)), (1.0, P(2)), (1.5, P(0))])
        reasons = [e.get("reason") for e in evs if e["event"] == "scan"]
        record("watcher", "normal visit: 1 arrival, 1 departure",
               count(evs, "arrival") == 1 and count(evs, "departure") == 1,
               f"arrival={count(evs, 'arrival')} departure={count(evs, 'departure')}")
        record("watcher", "scans on arrival and on new motion",
               "arrival" in reasons and "motion" in reasons, str(reasons))
        record("watcher", "first scan announces", bool(cl) and cl[0] is True, str(cl))
        record("watcher", "'settled' event logged", count(evs, "settled") >= 1)
        record("watcher", "roster cleared on departure", room_roster.members() == [], str(room_roster.members()))
        record("watcher", "loop exited cleanly", not alive)

        # B: flapping sensor
        alive, evs, cl = run([(0.5, P(0)), (0.8, P(2)), (0.25, P(0)), (0.8, P(2)), (1.5, P(0))])
        record("watcher", "0.25s dropout is NOT a departure",
               count(evs, "arrival") == 1 and count(evs, "departure") == 1,
               f"arrival={count(evs, 'arrival')} departure={count(evs, 'departure')}")

        # C: already in the room at startup
        alive, evs, cl = run([(1.0, P(2)), (1.5, P(0))])
        record("watcher", "occupied at startup: silent scan, no arrival",
               cl and cl[0] is False and count(evs, "arrival") == 0, f"calls={cl}")

        # D: ESP offline, then back
        alive, evs, cl = run([(1.3, None), (0.8, P(0)), (1.0, P(2)), (1.2, P(0))])
        record("watcher", "survives ESP offline, then detects arrival",
               count(evs, "arrival") == 1 and not alive, f"arrival={count(evs, 'arrival')}")

        # E: VC-01 wake counter
        alive, evs, cl = run([(0.5, P(0, wake=0)), (0.5, P(0, wake=1, hexv="AB12")), (0.5, P(0, wake=1, hexv="AB12"))])
        flag_ok = w.WAKE_FLAG.exists() and "AB12" in w.WAKE_FLAG.read_text()
        record("watcher", "VC-01 wake_count increase writes the flag file", flag_ok)

        # F: radar noise - a "target" at 0 cm must never count as an arrival
        alive, evs, cl = run([(0.5, P(0)), (1.0, dict(P(1), mov_cm=0, stat_cm=0)), (0.5, P(0))])
        record("watcher", "radar noise at 0 cm is NOT an arrival",
               count(evs, "arrival") == 0 and not cl, f"arrival={count(evs, 'arrival')} scans={cl}")

        # G: PIR alone wakes the camera (a scan) but never declares an arrival
        alive, evs, cl = run([(0.5, P(0)), (0.3, P(0, pir=True)), (1.0, P(0))])
        record("watcher", "PIR motion starts a scan but is not an arrival",
               count(evs, "arrival") == 0 and cl == [True], f"arrival={count(evs, 'arrival')} scans={cl}")

        # H: a single-poll blip is not an arrival
        alive, evs, cl = run([(0.5, P(0)), (0.04, P(2)), (0.8, P(0))])
        record("watcher", "a one-poll radar blip is NOT an arrival",
               count(evs, "arrival") == 0, f"arrival={count(evs, 'arrival')}")
    finally:
        esp32_cam.presence = orig_presence
        room_roster.scan = orig_scan
        room_roster.clear()
        shutil.rmtree(tmpdir, ignore_errors=True)


def t_roster_scan():
    section("Roster scan: greeting rules (mocked camera and faces)")
    import numpy as np
    import core.greeter_ambient as g
    from core import room_roster as rr

    rng = np.random.default_rng(3)
    emb = rng.normal(size=128) * 0.0884
    emb_other_angle = emb + rng.normal(size=128) * 0.06      # same person, but farther than MATCH_DIST
    stranger = rng.normal(size=128) * 0.0884
    greeted, asked = [], []
    cur = {"emb": emb, "res": {"status": "known", "name": "Tejas", "category": "close", "distance": 0.4}}

    fr = rr.face_recognition
    names = ("capture_bytes", "identify_embedding", "BACKEND", "_handle_unknown", "_prewarm_llm")
    saved_rr = {n: getattr(rr, n) for n in names}
    saved_fr = {n: getattr(fr, n) for n in ("load_image_file", "face_locations", "face_encodings")}
    saved_greet = g.greet
    rr.capture_bytes = lambda: b"jpg"
    rr.identify_embedding = lambda e: dict(cur["res"])
    rr.BACKEND = "face_recognition"
    rr._handle_unknown = lambda res, e, enroll: asked.append(1)
    rr._prewarm_llm = lambda: None
    fr.load_image_file = lambda f: np.zeros((200, 200, 3), np.uint8)
    fr.face_locations = lambda img, number_of_times_to_upsample=1: [(20, 120, 100, 40)]
    fr.face_encodings = lambda img, known_face_locations=None: [cur["emb"]]
    g.greet = lambda res: greeted.append(res["name"])
    try:
        rr.clear(); rr._last_seen.clear(); rr._last_greeted.clear(); rr._recent_unknown.clear()
        r = rr.scan()
        record("scan", "first sighting after a long absence is greeted", greeted == ["Tejas"], str(greeted))
        record("scan", "scan reports face size", r.get("face_px") == 80, f"face_px={r.get('face_px')}")

        cur["emb"] = emb_other_angle
        rr.scan()
        record("scan", "same person at another head angle is NOT greeted again", greeted == ["Tejas"], str(greeted))
        record("scan", "...and stays a single roster entry", rr.members() == ["Tejas"], str(rr.members()))

        rr.clear()                                       # a false 'departure' while sitting
        cur["emb"] = emb
        rr.scan()
        record("scan", "returning within AWAY_MIN_S is NOT greeted", greeted == ["Tejas"], str(greeted))

        rr.clear(); rr._last_seen["Tejas"] = time.time() - rr.AWAY_MIN_S - 5; rr._last_greeted.clear()
        rr.scan()
        record("scan", "returning after a real absence IS greeted", greeted == ["Tejas", "Tejas"], str(greeted))

        rr.clear(); rr._last_seen.clear(); rr._last_greeted.clear()
        rr.scan(announce=False)
        record("scan", "silent scan (startup) greets nobody", greeted == ["Tejas", "Tejas"], str(greeted))

        rr.clear()
        cur["emb"] = stranger
        cur["res"] = {"status": "unknown", "embedding": stranger.tolist()}
        rr.scan()
        record("scan", "a new stranger is asked for a name once", len(asked) == 1, f"asked {len(asked)}x")
        rr.clear()
        rr.scan()
        record("scan", "the same stranger back soon is NOT asked again", len(asked) == 1, f"asked {len(asked)}x")
    finally:
        for n, v in saved_rr.items():
            setattr(rr, n, v)
        for n, v in saved_fr.items():
            setattr(fr, n, v)
        g.greet = saved_greet
        rr.clear(); rr._last_seen.clear(); rr._last_greeted.clear(); rr._recent_unknown.clear()

    # identify_embedding matches without detecting a face again, and notices newly enrolled people
    try:
        import tools.face_recognition_backend as be
        d = Path(tempfile.mkdtemp())
        old_dir = be.PERSONS_DIR
        be.PERSONS_DIR = str(d)
        be._known_cache["sig"] = None
        try:
            r0 = be.identify_embedding(emb)
            (d / "tejas.json").write_text(json.dumps({"name": "Tejas", "category": "close",
                                                       "backend": "face_recognition", "embedding": emb.tolist()}))
            r1 = be.identify_embedding(emb + rng.normal(size=128) * 0.002)
            r2 = be.identify_embedding(stranger)
        finally:
            be.PERSONS_DIR = old_dir
            be._known_cache["sig"] = None
            shutil.rmtree(d, ignore_errors=True)
        record("scan", "identify_embedding: nobody enrolled gives unknown", r0["status"] == "unknown")
        record("scan", "identify_embedding: picks up a newly enrolled person", r1.get("name") == "Tejas", str(r1)[:80])
        record("scan", "identify_embedding: a stranger stays unknown", r2["status"] == "unknown")
    except Exception as e:
        record("scan", "identify_embedding", False, repr(e))


def t_sface():
    section("sface backend: matching rules and blur-aware strangers (mocked models)")
    import numpy as np
    import tools.face_recognition_backend as be
    import core.greeter_ambient as g
    from core import room_roster as rr

    rng = np.random.default_rng(11)
    unit = lambda v: (v / np.linalg.norm(v)).astype(np.float32)
    near = lambda v, noise: unit(v + rng.normal(size=128) * noise)
    a1 = unit(rng.normal(size=128)); a2 = near(a1, 0.05)      # person A: two enrolled photos
    b1 = unit(rng.normal(size=128))                            # person B
    stranger = unit(rng.normal(size=128))
    mix = unit(a1 + b1)                                        # looks equally like A and B

    # ---- matching rules in the backend (temp persons folder)
    d = Path(tempfile.mkdtemp())
    old_dir, old_backend = be.PERSONS_DIR, be.BACKEND
    be.PERSONS_DIR, be.BACKEND = str(d), "sface"
    be._known_cache["sig"] = None

    def put(name, **kw):
        (d / f"{name.lower()}.json").write_text(json.dumps({"name": name, "category": "close", **kw}))
        be._known_cache["sig"] = None
    try:
        put("A", backend="face_recognition", embedding=[0.0] * 128, sface_embeddings=[a1.tolist(), a2.tolist()])
        put("B", backend="face_recognition", embedding=[0.0] * 128, sface_embeddings=[b1.tolist()])
        put("Old", backend="face_recognition", embedding=[0.1] * 128)           # dlib only: must be ignored
        r = be.identify_embedding(near(a1, 0.03))
        record("sface", "a close face of person A is known as A", r.get("name") == "A", str(r)[:60])
        r = be.identify_embedding(near(a2, 0.03))
        record("sface", "any of a person's several embeddings can match", r.get("name") == "A", str(r)[:60])
        r = be.identify_embedding(stranger)
        record("sface", "a stranger is unknown and reports its best similarity",
               r["status"] == "unknown" and "best_similarity" in r, str(r.get("best_similarity")))
        r = be.identify_embedding(mix)
        record("sface", "a face torn between two people is ambiguous, not guessed",
               r["status"] == "unknown" and r.get("ambiguous") is True, str({k: v for k, v in r.items() if k != "embedding"}))
        (d / "b.json").unlink(); (d / "old.json").unlink(); be._known_cache["sig"] = None
        r = be.identify_embedding(mix)
        record("sface", "with one person enrolled the margin rule does not apply", r.get("name") == "A", str(r)[:60])
        c1 = unit(rng.normal(size=128))
        put("C", backend="sface", embedding=c1.tolist())                       # enrolled while BACKEND == sface
        r = be.identify_embedding(near(c1, 0.03))
        record("sface", "a person enrolled directly under sface (single embedding) matches", r.get("name") == "C", str(r)[:60])
    finally:
        be.PERSONS_DIR, be.BACKEND = old_dir, old_backend
        be._known_cache["sig"] = None
        shutil.rmtree(d, ignore_errors=True)

    # ---- roster scan with the sface path (detector, decoder and matcher mocked)
    cur = {"faces": [], "res": None}
    greeted, asked = [], []
    face = lambda emb, sharp, px=100: {"loc": (50, 200, 50 + px, 100), "emb": emb, "score": 0.9, "sharp": sharp}
    names = ("capture_bytes", "_decode_bgr", "detect_and_embed", "identify_embedding", "BACKEND", "_handle_unknown", "_prewarm_llm")
    saved = {n: getattr(rr, n) for n in names}
    saved_greet = g.greet
    rr.capture_bytes = lambda: b"x"
    rr._decode_bgr = lambda data: np.zeros((300, 400, 3), np.uint8)
    rr.detect_and_embed = lambda bgr: (cur["faces"], 0.02, 0.005)
    rr.identify_embedding = lambda e: dict(cur["res"])
    rr.BACKEND = "sface"
    rr._handle_unknown = lambda res, e, enroll: asked.append(1)
    rr._prewarm_llm = lambda: None
    g.greet = lambda res: greeted.append(res["name"])

    def reset():
        rr.clear(); rr._last_seen.clear(); rr._last_greeted.clear(); rr._recent_unknown.clear()
    try:
        record("sface", "roster treats a close face as the same person", (rr.clear(), rr._add(None, a1), rr._seen(near(a1, 0.03)))[2])
        record("sface", "roster does not merge different people", not rr._seen(stranger))

        reset()
        cur["faces"] = [face(a1, sharp=10)]
        cur["res"] = {"status": "known", "name": "A", "category": "close", "similarity": 0.40}
        r = rr.scan()
        record("sface", "a BLURRY face that matches is still greeted", greeted == ["A"], str(greeted))
        record("sface", "scan logs size, sharpness and similarity",
               r["face_log"] and r["face_log"][0]["px"] == 100 and r["face_log"][0]["sharp"] == 10.0
               and r["face_log"][0]["sim"] == 0.4, str(r["face_log"][:1]))

        reset()
        cur["faces"] = [face(stranger, sharp=10)]
        cur["res"] = {"status": "unknown", "embedding": stranger.tolist(), "best_similarity": 0.25}
        r = rr.scan()
        record("sface", "a BLURRY unmatched face is never called a stranger",
               not asked and rr.members() == [], f"asked={len(asked)} members={rr.members()}")

        cur["faces"] = [face(stranger, sharp=30)]
        cur["res"] = {"status": "unknown", "embedding": stranger.tolist(), "best_similarity": 0.10, "ambiguous": True}
        rr.scan()
        record("sface", "an ambiguous face is not asked for a name", not asked, f"asked={len(asked)}")

        cur["res"] = {"status": "unknown", "embedding": stranger.tolist(), "best_similarity": 0.10}
        rr.scan()
        record("sface", "a SHARP unmatched face seen twice is asked once", len(asked) == 1, f"asked={len(asked)}")
        rr.clear(); rr.scan()                       # they left and came back; the 'already asked' memory stays
        record("sface", "...and not asked again soon after", len(asked) == 1, f"asked={len(asked)}")
    finally:
        for n, v in saved.items():
            setattr(rr, n, v)
        g.greet = saved_greet
        reset()


def t_scan_load():
    section("Load on the ESP (mocked camera)")
    import numpy as np
    from core import room_roster as rr
    fr = rr.face_recognition
    calls = []
    saved_rr = {n: getattr(rr, n) for n in ("capture_bytes", "BACKEND", "SCAN_MAX_S", "SCAN_FRAMES", "_prewarm_llm")}
    saved_fr = {n: getattr(fr, n) for n in ("load_image_file", "face_locations", "face_encodings")}
    rr.capture_bytes = lambda: (calls.append(time.time()), b"x")[1]
    rr.BACKEND = "face_recognition"; rr.SCAN_MAX_S = 3; rr.SCAN_FRAMES = 60; rr._prewarm_llm = lambda: None
    fr.load_image_file = lambda f: np.zeros((50, 50, 3), np.uint8)

    def slow_locs(img, number_of_times_to_upsample=1):
        time.sleep(0.4)                              # a slow detector, like dlib
        return []
    fr.face_locations = slow_locs
    try:
        r = rr.scan(announce=False)
        record("esp", "a scan never captures much faster than it processes",
               len(calls) <= r["frames"] + 2, f"captures={len(calls)}, frames processed={r['frames']}")
    finally:
        for n, v in saved_rr.items():
            setattr(rr, n, v)
        for n, v in saved_fr.items():
            setattr(fr, n, v)
        rr.clear()


def t_esp_policy():
    section("ESP link policy: a slow ESP must not trigger a network scan")
    import requests as rq
    saved = (esp32_cam._base, esp32_cam._last_scan, esp32_cam._read_cached,
             esp32_cam.discover, esp32_cam._save, rq.get)
    scans = []

    class Reply:
        def json(self):
            return {"present": True, "wake_count": 0}

    def slow_get(url, timeout=None, **k):
        time.sleep(1.8)                              # slower than the old 1.5 s check, faster than the new 5 s one
        if timeout is not None and timeout < 1.8:
            raise rq.exceptions.Timeout()
        return Reply()

    def dead_get(url, timeout=None, **k):
        raise rq.exceptions.ConnectionError()
    try:
        esp32_cam._read_cached = lambda: "http://10.0.0.9"
        esp32_cam._save = lambda base: None          # never overwrite your real saved address
        esp32_cam.discover = lambda: (scans.append(1), "http://10.0.0.99")[1]
        esp32_cam._base, esp32_cam._last_scan = None, 0.0
        rq.get = slow_get
        url = esp32_cam.base_url()
        record("esp", "a slow-but-alive ESP keeps its address (no network scan)",
               url == "http://10.0.0.9" and not scans, f"url={url}, scans={len(scans)}")
        esp32_cam._base, esp32_cam._last_scan = None, 0.0
        rq.get = dead_get
        url = esp32_cam.base_url()
        record("esp", "an unreachable address still triggers discovery",
               url == "http://10.0.0.99" and len(scans) == 1, f"url={url}, scans={len(scans)}")
        import inspect
        d = inspect.signature(esp32_cam.capture_bytes).parameters
        record("esp", "scan captures fail fast (5 s, one try)", d["timeout"].default == 5 and d["tries"].default == 1,
               f"timeout={d['timeout'].default} tries={d['tries'].default}")
    finally:
        (esp32_cam._base, esp32_cam._last_scan, esp32_cam._read_cached,
         esp32_cam.discover, esp32_cam._save, rq.get) = saved


def t_personal_greeting():
    section("Personal greeting (no LLM for people who have one)")
    import core.greeter_ambient as g
    calls = []
    saved = g.ask_chat
    g.ask_chat = lambda prompt, max_tokens=60: (calls.append(prompt), "stub greeting")[1]
    try:
        line = g.generate_greeting({"status": "known", "name": "Tejas", "category": "close"})
        every = {l for group in g.PERSONAL_GREETINGS["tejas"].values() for l in group}
        record("greeting", "Tejas gets a personal line without an LLM call", line in every and not calls,
               f"{line!r}, llm calls={len(calls)}")
        line2 = g.generate_greeting({"status": "known", "name": "Visitor", "category": "close"})
        record("greeting", "everyone else is still greeted by the LLM", line2 == "stub greeting" and len(calls) == 1,
               f"calls={len(calls)}")
    finally:
        g.ask_chat = saved


def t_esp(n):
    section("ESP32-CAM link")
    try:
        base = esp32_cam.base_url()
    except Exception as e:
        record("esp", "find ESP32-CAM on the network", False, str(e))
        return False
    info("address", base)
    lat, fails, last = [], 0, None
    for _ in range(n):
        t = time.time()
        try:
            last = esp32_cam.presence()
            lat.append(time.time() - t)
        except Exception:
            fails += 1
        time.sleep(0.05)
    record("esp", "presence polls", fails == 0, f"{n - fails}/{n} ok, {stats(lat)}")
    record("esp", f"presence p95 < {PRESENCE_P95_S}s", bool(lat) and pct(lat, 95) < PRESENCE_P95_S)
    if last:
        need = ["present", "state", "mov_cm", "stat_cm", "pir", "wake_count", "since_ms"]
        missing = [k for k in need if k not in last]
        record("esp", "JSON has all fields", not missing, f"missing: {missing}" if missing else "")
        record("esp", "radar state is 0..3", int(last.get("state", -1)) in (0, 1, 2, 3), f"state={last.get('state')}")
        info("current reading", f"state={last.get('state')} pir={last.get('pir')} "
                                f"dist={last.get('mov_cm') or last.get('stat_cm')}cm")
    return fails < n


def t_capture(n):
    section("Camera capture")
    from io import BytesIO
    from PIL import Image
    ok, lat, sizes = 0, [], []
    for _ in range(n):
        t = time.time()
        try:
            path = esp32_cam.capture()
            dt = time.time() - t
            data = Path(path).read_bytes()
            im = Image.open(BytesIO(data))
            im.load()                                   # truncated or garbled data raises here
            if len(data) > 5000 and im.size[0] >= 320:
                ok += 1
                lat.append(dt)
                sizes.append(len(data) // 1024)
        except Exception:
            pass
        time.sleep(0.2)
    record("capture", "valid JPEGs", ok >= CAPTURE_MIN_OK * n, f"{ok}/{n} decoded fine, {stats(lat)}")
    if sizes:
        info("frame size", f"{min(sizes)}-{max(sizes)} KB")


def t_concurrent(n):
    section("Presence polling while capturing (what a face check does)")
    stop = threading.Event()
    plat, pfail = [], [0]

    def poller():
        while not stop.is_set():
            t = time.time()
            try:
                esp32_cam.presence()
                plat.append(time.time() - t)
            except Exception:
                pfail[0] += 1
            time.sleep(0.2)

    th = threading.Thread(target=poller, daemon=True)
    th.start()
    caps_ok = 0
    for _ in range(n):
        try:
            esp32_cam.capture()
            caps_ok += 1
        except Exception:
            pass
    stop.set()
    th.join(5)
    record("concurrent", "captures succeed under polling", caps_ok == n, f"{caps_ok}/{n}")
    record("concurrent", "polls survive captures", pfail[0] == 0,
           f"{len(plat)} ok, {pfail[0]} failed, {stats(plat)}", warn=True)
    record("concurrent", f"poll p95 < {LOADED_PRESENCE_P95_S}s", bool(plat) and pct(plat, 95) < LOADED_PRESENCE_P95_S,
           warn=True)


def t_faces(n):
    section("Face pipeline (sit in front of the camera for this one)")
    import face_recognition
    from tools.face_recognition_backend import identify
    det, idl, found, known = [], [], 0, 0
    for _ in range(n):
        try:
            p = esp32_cam.capture()
        except Exception:
            continue
        t = time.time()
        img = face_recognition.load_image_file(p)
        locs = face_recognition.face_locations(img)
        det.append(time.time() - t)
        if locs:
            found += 1
            t = time.time()
            res = identify(p)
            idl.append(time.time() - t)
            if res.get("status") == "known":
                known += 1
        time.sleep(0.3)
    record("faces", "face found in the frames", found >= n // 2, f"{found}/{n} (be in view and well lit)", warn=True)
    record("faces", "recognized as someone known", known >= max(1, found // 2) if found else False,
           f"{known}/{found}", warn=True)
    if det:
        info("detect time", stats(det))
    if idl:
        record("faces", f"identify p95 < {IDENTIFY_P95_S}s", pct(idl, 95) < IDENTIFY_P95_S, stats(idl))


def t_kokoro(n, parallel):
    section("Kokoro TTS")
    import requests
    url = "http://localhost:8880/v1/audio/speech"

    def gen(text):
        t = time.time()
        r = requests.post(url, json={"model": "kokoro", "input": text, "voice": "bm_george",
                                     "response_format": "mp3"}, timeout=(3, 60))
        return r.status_code == 200 and len(r.content) > 1000, time.time() - t

    for label, text in (("1 word", "Hello."), ("10 words", "Welcome back Tejas, how has your day been so far?")):
        lat, ok = [], 0
        for _ in range(n):
            try:
                good, dt = gen(text)
                if good:
                    ok += 1
                    lat.append(dt)
            except Exception:
                pass
        record("kokoro", f"{label}: {n} requests", ok == n and pct(lat, 50) < KOKORO_P50_S,
               f"{ok}/{n} ok, {stats(lat)}")
    if parallel:
        res = []

        def one():
            try:
                res.append(gen("Welcome back Tejas, how has your day been so far?"))
            except Exception:
                res.append((False, 0))

        t = time.time()
        ths = [threading.Thread(target=one) for _ in range(3)]
        for x in ths:
            x.start()
        for x in ths:
            x.join(90)
        record("kokoro", "3 requests at once", len(res) == 3 and all(g for g, _ in res),
               f"wall time {time.time() - t:.1f}s")


def t_greeting(n):
    section("Greeting text (Ollama)")
    from core.greeter_ambient import generate_greeting
    lat, empty = [], 0
    for _ in range(n):
        t = time.time()
        g = generate_greeting({"status": "known", "name": "Visitor", "category": "close"})
        lat.append(time.time() - t)
        if not g or not str(g).strip():
            empty += 1
    record("greeting", "non-empty greetings", empty == 0, f"{n - empty}/{n}")
    record("greeting", f"p50 < {GREETING_P50_S}s", pct(lat, 50) < GREETING_P50_S, stats(lat))


def t_hygiene():
    section("Logs, disk, memory")
    free = shutil.disk_usage(ROOT).free / 1e9
    record("hygiene", "free disk > 5 GB", free > 5, f"{free:.0f} GB free")
    cap = ROOT / "state" / "captures"
    if cap.exists():
        mb = sum(f.stat().st_size for f in cap.glob("*") if f.is_file()) / 1e6
        record("hygiene", "state/captures < 500 MB", mb < 500, f"{mb:.0f} MB", warn=True)
    plog = ROOT / "state" / "presence_log.jsonl"
    if plog.exists():
        record("hygiene", "presence_log < 50 MB", plog.stat().st_size < 50e6, f"{plog.stat().st_size / 1e6:.1f} MB", warn=True)
        errs = 0
        for line in plog.read_text().splitlines()[-500:]:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") in ("scan_error", "ambient_error"):
                errs += 1
        record("hygiene", "no scan errors in the last 500 log events", errs == 0, f"{errs} errors", warn=True)
    for name, pat, limit in (("watcher", "scripts/presence_watcher.py", 1500), ("kokoro", "uvicorn api.src.main:app", 3000)):
        m = rss_mb(pat)
        if m is None:
            info(f"{name} memory", "not running")
        else:
            record("hygiene", f"{name} memory < {limit} MB", m < limit, f"{m:.0f} MB", warn=True)


def t_soak(minutes):
    section(f"Soak test ({minutes:g} min)")
    end = time.time() + minutes * 60
    polls = fails = reboots = caps = cap_fail = 0
    lat = []
    last_wc = last_up = None
    last_cap = 0.0
    last_print = time.time()
    w0, k0 = rss_mb("scripts/presence_watcher.py"), rss_mb("uvicorn api.src.main:app")
    while time.time() < end:
        t = time.time()
        try:
            p = esp32_cam.presence()
            lat.append(time.time() - t)
            polls += 1
            wc, up = int(p.get("wake_count", 0)), p.get("uptime_ms")
            if (last_wc is not None and wc < last_wc) or (up is not None and last_up is not None and up < last_up):
                reboots += 1
            last_wc, last_up = wc, up
        except Exception:
            fails += 1
        if time.time() - last_cap > 30:
            last_cap = time.time()
            try:
                esp32_cam.capture()
                caps += 1
            except Exception:
                cap_fail += 1
        if time.time() - last_print > 60:
            last_print = time.time()
            print(f"    ...{(end - time.time()) / 60:.0f} min left: {polls} polls, {fails} failed, {reboots} reboots")
        time.sleep(0.5)
    total = polls + fails
    record("soak", "poll failure rate < 1%", total > 0 and fails / total < 0.01, f"{fails}/{total}, {stats(lat)}")
    record("soak", "ESP never rebooted", reboots == 0, f"{reboots} counter resets (wake_count / uptime)")
    record("soak", "captures during soak", caps and cap_fail / (caps + cap_fail) <= 0.02, f"{caps} ok, {cap_fail} failed")
    for name, before, pat in (("watcher", w0, "scripts/presence_watcher.py"), ("kokoro", k0, "uvicorn api.src.main:app")):
        after = rss_mb(pat)
        if before is not None and after is not None:
            record("soak", f"{name} memory growth < 200 MB", after - before < 200, f"{before:.0f} -> {after:.0f} MB", warn=True)


def t_speak():
    section("Spoken greeting (audible)")
    try:
        from tools.sidecar import speak_fast as speak
    except ImportError:
        from tools.sidecar import speak
    t = time.time()
    speak("Stress test greeting. This is the second sentence.")
    dt = time.time() - t
    record("speak", "two-sentence greeting played", dt < 20, f"{dt:.1f}s total (includes playback)")


def t_contracts(esp_ok):
    section("Contracts and regressions found by reading the code")
    # smart_planner must parse a JSON plan (it once lacked `import json`, which made every plan one task)
    try:
        from core import smart_planner
        orig = smart_planner.ask
        smart_planner.ask = lambda *a, **k: '[{"description": "joke"}, {"description": "screenshot"}]'
        try:
            tasks = smart_planner.smart_plan("tell a joke then take a screenshot")
        finally:
            smart_planner.ask = orig
        record("contracts", "smart_plan parses a 2-step plan", len(tasks) == 2, f"got {len(tasks)} task(s)")
    except Exception as e:
        record("contracts", "smart_plan parses a 2-step plan", False, repr(e))

    # name extraction must not enroll "Yes" / "Hello" as a person
    try:
        from core.enrollment import _extract_name_simple as ex
        bad = [t for t in ("Yes", "Hello", "okay", "Thanks", "Sure") if ex(t) is not None]
        want = {"my name is rahul": "Rahul", "Rahul": "Rahul", "I'm Anita Roy": "Anita Roy"}
        wrong = [t for t, w in want.items() if ex(t) != w]
        record("contracts", "name extraction rejects non-names", not bad, f"wrongly accepted: {bad}")
        record("contracts", "name extraction accepts real names", not wrong, f"wrong: {wrong}")
    except Exception as e:
        record("contracts", "name extraction", False, repr(e))

    # an LLM error must never be spoken aloud
    try:
        import core.greeter_ambient as g
        spoken = []
        og, osp = g.generate_greeting, g.speak
        g.generate_greeting = lambda r: "LLM_ERROR: local Ollama unavailable, no cloud fallback configured"
        g.speak = lambda t: spoken.append(t)
        try:
            g.greet({"status": "known", "name": "Tejas", "category": "close"})
        finally:
            g.generate_greeting, g.speak = og, osp
        ok = bool(spoken) and not spoken[0].startswith("LLM_ERROR")
        record("contracts", "greeting never speaks an LLM error", ok, spoken[0] if spoken else "nothing spoken")
    except Exception as e:
        record("contracts", "greeting never speaks an LLM error", False, repr(e))

    # speak_kokoro must not add a fixed sleep after /play (mocked network, so no audio plays)
    try:
        import shutil
        import tools.sidecar as sc

        class R:
            content = b"x" * 2000
            def raise_for_status(self): pass
            def json(self): return {"status": "playing"}

        op, oc = sc.requests.post, shutil.copy
        sc.requests.post = lambda *a, **k: R()
        shutil.copy = lambda *a, **k: None
        try:
            t = time.time()
            sc.speak_kokoro("x" * 150, "bm_george")
            dt = time.time() - t
        finally:
            sc.requests.post, shutil.copy = op, oc
        record("contracts", "speak_kokoro adds no fixed sleep after /play", dt < 1.0, f"{dt:.1f}s with instant mocks")
    except Exception as e:
        record("contracts", "speak_kokoro adds no fixed sleep after /play", False, repr(e))

    # the plugin must follow the executor's run(args: dict) contract
    try:
        from core.plugin_loader import load_plugins
        pl = load_plugins()
        record("contracts", "room_presence plugin loads", "room_presence" in pl)
        if "room_presence" in pl and esp_ok:
            r = pl["room_presence"]["run"]({"action": "status"})
            record("contracts", "room_presence status returns an ok dict",
                   isinstance(r, dict) and r.get("status") == "ok", str(r)[:100])
            r = pl["room_presence"]["run"]({"action": "snapshot"})
            p = r.get("path") if isinstance(r, dict) else None
            record("contracts", "room_presence snapshot saves a file", bool(p) and Path(p).exists(), str(r)[:100])
    except Exception as e:
        record("contracts", "room_presence plugin", False, repr(e))


# ---------------------------------------------------------------- main

def summary(started):
    fails = [r for r in RESULTS if r[2] == "FAIL"]
    warns = [r for r in RESULTS if r[2] == "WARN"]
    passes = [r for r in RESULTS if r[2] == "PASS"]
    print("\n" + "=" * 50)
    print(f"PASS {len(passes)}   WARN {len(warns)}   FAIL {len(fails)}   ({time.time() - started:.0f}s)")
    for s, n, st, d in fails + warns:
        print(f"  {st}: [{s}] {n}" + (f" - {d}" if d else ""))
    out = ROOT / "state" / "stress_room_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"when": datetime.now().isoformat(timespec="seconds"),
                               "results": [{"section": s, "name": n, "status": st, "detail": d}
                                           for s, n, st, d in RESULTS]}, indent=1))
    print(f"report: {out}")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--live", action="store_true", help="leave watcher/watchdog running")
    ap.add_argument("--soak", type=float, default=0, help="minutes of continuous polling")
    ap.add_argument("--speak", action="store_true", help="play one real greeting")
    a = ap.parse_args()
    q = a.quick
    started = time.time()

    safe(t_services)
    safe(t_roster)
    safe(t_roster_scan)
    safe(t_sface)
    safe(t_scan_load)
    safe(t_esp_policy)
    safe(t_personal_greeting)
    safe(t_watcher_logic)

    isolated = False
    if not a.live:
        print("\n(stopping watchdog + presence watcher so they don't compete for the ESP)")
        stop_services()
        isolated = True
    try:
        esp_ok = safe(t_esp, 15 if q else 50)
        safe(t_contracts, esp_ok)
        if esp_ok:
            safe(t_capture, 5 if q else 15)
            safe(t_concurrent, 5 if q else 10)
            safe(t_faces, 3 if q else 8)
        else:
            info("skipped", "capture / concurrency / faces / soak need the ESP")
        safe(t_kokoro, 2 if q else 5, not q)
        safe(t_greeting, 1 if q else 3)
        if esp_ok and a.soak > 0:
            safe(t_soak, a.soak)
        if a.speak:
            safe(t_speak)
        safe(t_hygiene)
    finally:
        if isolated:
            print("\n(restarting services via start_all.sh)")
            start_services()
    sys.exit(summary(started))


if __name__ == "__main__":
    main()
