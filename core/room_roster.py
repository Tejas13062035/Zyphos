"""Short-term memory of who is in the room right now (separate from the face database)."""
import io
import threading
import time

import face_recognition
import numpy as np
from PIL import Image

from tools import esp32_cam as _cam
from tools.esp32_cam import capture_bytes
from tools.face_recognition_backend import BACKEND, detect_and_embed, identify, identify_embedding
from tools.pending_clusters import record_sighting

MATCH_DIST = 0.55          # dlib: embedding distance below which two faces count as the same person
MATCH_DIST_SFACE = 0.55    # sface: 1 - cosine similarity (so similarity >= 0.45)
ROSTER_TTL_S = 45 * 60     # forget someone the camera hasn't seen for this long
AWAY_MIN_S = 10 * 60       # greet a named person only if the camera hasn't seen them for this long
GREET_COOLDOWN_S = 300     # extra guard: never greet the same person twice within this time
UNKNOWN_REASK_S = 30 * 60  # don't ask the same stranger for their name again within this time
SCAN_FRAMES = 20           # most frames examined per scan
SCAN_MAX_S = 10            # time cap per scan
MAX_EMBS = 5               # face samples kept per person
DETECT_UPSAMPLE = 1        # dlib only: 2 finds smaller faces but is roughly 4x slower per frame
# sface only: a face blurrier than this is never called a stranger. In 8 door faces, sharpness >= 17 matched the
# enrolled person (0.43-0.51) and <= 15 did not (0.23-0.31), so a blurry frame of a known person looks "unknown".
SHARP_MIN_UNKNOWN = 16.0

_lock = threading.Lock()
_roster = []               # [{"name": str|None, "embs": [array], "first": ts, "last": ts}]
_last_greeted = {}         # name -> timestamp of the last greeting
_last_seen = {}            # name -> last time the camera saw them (survives roster clears)
_recent_unknown = []       # [(embedding, timestamp)] strangers already asked for a name


def clear():
    with _lock:
        _roster.clear()


def members():
    with _lock:
        _expire()
        return [p["name"] or "unknown" for p in _roster]


def _expire():
    cutoff = time.time() - ROSTER_TTL_S
    _roster[:] = [p for p in _roster if p["last"] > cutoff]


def _dist(a, b):
    if BACKEND == "sface":
        return 1.0 - float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))
    return float(np.linalg.norm(a - b))


def _match_thr():
    return MATCH_DIST_SFACE if BACKEND == "sface" else MATCH_DIST


def _find(emb):
    best, best_d = None, _match_thr()
    for p in _roster:
        d = min(_dist(e, emb) for e in p["embs"])
        if d < best_d:
            best, best_d = p, d
    return best


def _seen(emb):
    """True (and refresh) if this face belongs to someone already in the room."""
    with _lock:
        _expire()
        p = _find(emb)
        if p is None:
            return False
        now = time.time()
        p["last"] = now
        if p["name"]:
            _last_seen[p["name"]] = now
        if len(p["embs"]) < MAX_EMBS and min(_dist(e, emb) for e in p["embs"]) > 0.15:
            p["embs"].append(emb)
        return True


def _add(name, emb):
    """Add someone to the roster. Returns True if a new entry was created, False if the
    name was already there (the new face sample is merged into the existing entry)."""
    now = time.time()
    with _lock:
        if name:
            _last_seen[name] = now
            for p in _roster:
                if p["name"] == name:
                    p["last"] = now
                    if len(p["embs"]) < MAX_EMBS:
                        p["embs"].append(emb)
                    return False
        _roster.append({"name": name, "embs": [emb], "first": now, "last": now})
        return True


def _crop(img, loc, tag, bgr=False):
    top, right, bottom, left = loc
    h, w = img.shape[:2]
    m = int(0.4 * max(bottom - top, right - left))
    top, left = max(0, top - m), max(0, left - m)
    bottom, right = min(h, bottom + m), min(w, right + m)
    part = img[top:bottom, left:right]
    if bgr:
        part = np.ascontiguousarray(part[:, :, ::-1])
    path = f"/tmp/zyp_face_{tag}.jpg"
    Image.fromarray(part).save(path)
    return path


def _greet(res):
    name = res["name"]
    now = time.time()
    if now - _last_greeted.get(name, 0) < GREET_COOLDOWN_S:
        return
    _last_greeted[name] = now
    try:
        from core.greeter_ambient import greet
        greet(res)
    except Exception as e:
        print(f"[roster] greeting failed: {e}")


def _recently_asked(emb):
    cutoff = time.time() - UNKNOWN_REASK_S
    _recent_unknown[:] = [(e, t) for e, t in _recent_unknown if t > cutoff]
    return any(_dist(e, emb) < _match_thr() for e, _ in _recent_unknown)


def _handle_unknown(res, emb, enroll):
    try:
        res["embedding"] = res.get("embedding", emb)
        res["cluster_id"] = record_sighting(res["embedding"], res["_image_path"])
        if enroll:
            from core.enrollment import handle_unknown
            handle_unknown(res)
    except Exception as e:
        print(f"[roster] unknown-person handling failed: {e}")


def _prewarm_llm():
    """Start loading the chat model while faces are being identified."""
    try:
        from core.llm import ask_chat
        ask_chat("Say ok.", max_tokens=2)
    except Exception:
        pass


def _sharpness(img):
    """Blur score (variance of the Laplacian) on a half-size green channel. Low = blurry. None if cv2 is missing."""
    try:
        import cv2
        return float(cv2.Laplacian(np.ascontiguousarray(img[::2, ::2, 1]), cv2.CV_64F).var())
    except Exception:
        return None


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def _decode_bgr(data):
    import cv2
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def _analyze_dlib(data):
    """dlib: returns (image, faces, detect_s, embed_s, image_is_bgr). Faces are {"loc","emb","score","sharp"}."""
    img = face_recognition.load_image_file(io.BytesIO(data))
    t1 = time.time()
    locs = face_recognition.face_locations(img, number_of_times_to_upsample=DETECT_UPSAMPLE)
    t_det = time.time() - t1
    if not locs:
        return img, [], t_det, 0.0, False
    t1 = time.time()
    encs = face_recognition.face_encodings(img, known_face_locations=locs)
    t_emb = time.time() - t1
    faces = [{"loc": loc, "emb": emb, "score": None, "sharp": None} for loc, emb in zip(locs, encs)]
    return img, faces, t_det, t_emb, False


def _analyze_sface(data):
    """YuNet + SFace: same return shape as _analyze_dlib, but the image is BGR."""
    bgr = _decode_bgr(data)
    if bgr is None:
        return None, [], 0.0, 0.0, True
    faces, t_det, t_emb = detect_and_embed(bgr)
    return bgr, faces, t_det, t_emb, True


def scan(announce=True, enroll_unknown=True):
    """Look at the room. Only faces NOT already on the roster get identified. A named person is
    greeted only after being away for AWAY_MIN_S; a stranger is asked for a name once.
    Returns {"saw_face", "new", "frames", "face_px", "decision_at", "timing": {...}, "face_log": [...]}."""
    if announce:
        threading.Thread(target=_prewarm_llm, daemon=True).start()
    t0 = time.time()
    analyze = _analyze_sface if BACKEND == "sface" else _analyze_dlib

    # A producer thread keeps fetching frames while this thread works on the previous one. Only the
    # newest frame is kept, so a person who is walking is never judged by a stale picture.
    cond = threading.Condition()
    box = {"data": None, "done": False, "n": 0, "first": None, "caps": []}
    stop = threading.Event()
    tm = {"detect": [], "embed": [], "match": [], "sharp": [], "decision": None}
    face_log = []       # one entry per face that went through identification, for tuning thresholds

    def producer():
        while not stop.is_set() and time.time() - t0 < SCAN_MAX_S and box["n"] < SCAN_FRAMES:
            with cond:      # stay at most one frame ahead: never out-run the processing, or the ESP is
                while (box["data"] is not None and not stop.is_set()      # hammered for frames nobody looks at
                       and time.time() - t0 < SCAN_MAX_S):
                    cond.wait(0.05)
            if stop.is_set() or time.time() - t0 >= SCAN_MAX_S:
                break
            try:
                data = capture_bytes()
            except Exception as e:
                print(f"[roster] capture failed: {e}")
                stop.wait(0.3)
                continue
            lc = getattr(_cam, "last_capture", None)
            with cond:
                box["data"] = data
                box["n"] += 1
                if box["first"] is None:
                    box["first"] = time.time() - t0
                if lc:
                    box["caps"].append(dict(lc))
                cond.notify()
            stop.wait(0.05)
        with cond:
            box["done"] = True
            cond.notify()

    def next_frame():
        with cond:
            while box["data"] is None and not box["done"]:
                cond.wait(1.0)
            data, box["data"] = box["data"], None
            cond.notify()
            return data

    threading.Thread(target=producer, daemon=True).start()

    pending = []        # unknown faces seen once: (embedding, result). Confirmed on a later frame.
    new_people = []
    saw_face = False
    frames = 0
    biggest = 0
    decision_at = None
    try:
        while True:
            data = next_frame()
            if data is None:
                break
            frames += 1
            img, dets, t_det, t_emb, is_bgr = analyze(data)
            if img is None:
                continue
            tm["sharp"].append(_sharpness(img))
            tm["detect"].append(t_det)
            if not dets:
                continue
            tm["embed"].append(t_emb)
            saw_face = True
            biggest = max([biggest] + [d["loc"][2] - d["loc"][0] for d in dets])
            for i, d in enumerate(dets):
                loc, emb = d["loc"], d["emb"]
                if _seen(emb):
                    continue                       # already in the room: ignore
                tag = f"{int(time.time() * 1000)}_{i}"
                t1 = time.time()
                if BACKEND in ("face_recognition", "sface"):
                    res = identify_embedding(emb)  # no second detection pass
                else:
                    crop = _crop(img, loc, tag, bgr=is_bgr)
                    res = identify(crop)
                    res["_image_path"] = crop
                tm["match"].append(time.time() - t1)
                status = res.get("status")
                face_log.append({
                    "px": loc[2] - loc[0],
                    "score": round(d["score"], 2) if d["score"] is not None else None,
                    "sharp": round(d["sharp"], 1) if d["sharp"] is not None else None,
                    "status": status,
                    "name": res.get("name"),
                    "sim": round(res.get("similarity", res.get("best_similarity", 0.0)), 2)
                           if ("similarity" in res or "best_similarity" in res) else None,
                })
                if status == "known":
                    name = res["name"]
                    pending[:] = [q for q in pending if _dist(q[0], emb) >= _match_thr()]
                    prev_seen = _last_seen.get(name, 0.0)
                    if not _add(name, emb):
                        continue                   # same person, other head angle: merge only
                    new_people.append(name)
                    if decision_at is None:
                        decision_at = time.time()
                        tm["decision"] = decision_at - t0
                    if announce and time.time() - prev_seen >= AWAY_MIN_S:
                        _greet(res)
                elif status == "unknown":
                    if BACKEND == "sface" and (res.get("ambiguous") or (d["sharp"] or 0.0) < SHARP_MIN_UNKNOWN):
                        continue                   # too blurry (or torn between two people) to call anyone a stranger
                    match = next((q for q in pending if _dist(q[0], emb) < _match_thr()), None)
                    if match is None:
                        pending.append((emb, res))  # one sighting isn't enough to call them a stranger
                    else:
                        pending.remove(match)
                        _add(None, emb)
                        new_people.append("unknown")
                        if decision_at is None:
                            decision_at = time.time()
                            tm["decision"] = decision_at - t0
                        if announce and not _recently_asked(emb):
                            _recent_unknown.append((emb, time.time()))
                            if "_image_path" not in res:
                                res["_image_path"] = _crop(img, loc, tag, bgr=is_bgr)
                            _handle_unknown(res, emb, enroll_unknown)
            if not pending:
                break
    finally:
        stop.set()
    caps = box["caps"]
    timing = {
        "first_frame_s": round(box["first"], 2) if box["first"] is not None else None,
        "ttfb_s": _avg([c.get("ttfb") for c in caps]),
        "download_s": _avg([c["total"] - c["ttfb"] for c in caps if "total" in c and "ttfb" in c]),
        "detect_s": _avg(tm["detect"]), "embed_s": _avg(tm["embed"]), "match_s": _avg(tm["match"]),
        "sharp": _avg(tm["sharp"]),
        "decision_s": round(tm["decision"], 2) if tm["decision"] is not None else None,
    }
    return {"saw_face": saw_face, "new": new_people, "frames": frames, "face_px": biggest,
            "decision_at": decision_at, "timing": timing, "face_log": face_log[-10:]}
