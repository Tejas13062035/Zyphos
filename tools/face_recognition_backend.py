import os
import json
import threading
import time
import numpy as np

BACKEND = os.environ.get("ZYPHOS_FACE_BACKEND", "face_recognition").lower()
PERSONS_DIR = os.path.expanduser("~/zyp/memory/persons")

THRESHOLD_FACE_RECOGNITION = 0.6   # dlib distance — lower is stricter

# --- sface backend (OpenCV YuNet detector + SFace embedder; no onnxruntime needed) ---
THRESHOLD_SFACE = 0.363            # cosine similarity; OpenCV's recommended same-person threshold
SFACE_MARGIN = 0.15                # with 2+ enrolled people the best must beat the runner-up by this much
YUNET_SCORE_MIN = 0.8              # detector confidence (no false positives in 36 door frames at 0.8)
MODELS_DIR = os.path.expanduser("~/zyp/state/models")
YUNET_MODEL = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_MODEL = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

_insightface_app = None  # lazy-loaded once, reused — model init is slow


def _get_insightface_app():
    global _insightface_app
    if _insightface_app is None:
        from insightface.app import FaceAnalysis
        _insightface_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _insightface_app.prepare(ctx_id=0, det_size=(640, 640))
    return _insightface_app


def get_quality_score(image_path: str) -> float:
    """InsightFace det_score, used as the universal quality signal regardless
    of which backend is doing the actual identity matching. Returns 0.0 if no
    face is detected (caller should already know a face exists from identify(),
    so this should rarely fire, but don't crash if it does)."""
    import cv2
    if BACKEND == "sface":                      # no InsightFace needed: detector score x sharpness x size
        bgr = cv2.imread(image_path)
        if bgr is None:
            return 0.0
        found, _, _ = detect_and_embed(bgr)
        if not found:
            return 0.0
        f = max(found, key=lambda d: d["loc"][2] - d["loc"][0])
        px = f["loc"][2] - f["loc"][0]
        return float(f["score"]) * min(1.0, f["sharp"] / 30.0) * min(1.0, px / 120.0)
    app = _get_insightface_app()
    image = cv2.imread(image_path)
    faces = app.get(image)
    if not faces:
        return 0.0
    return float(faces[0].det_score)


def _load_known_people():
    known = []
    if not os.path.exists(PERSONS_DIR):
        return known
    for fname in os.listdir(PERSONS_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(PERSONS_DIR, fname)) as f:
                known.append(json.load(f))
    return known


def _identify_face_recognition(image_path: str):
    import face_recognition
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return {"status": "no_face_detected"}

    encoding = encodings[0]
    known = [p for p in _load_known_people() if p.get("backend") == "face_recognition"]

    if not known:
        return {"status": "unknown", "embedding": encoding.tolist()}

    known_encodings = [np.array(p["embedding"]) for p in known]
    distances = face_recognition.face_distance(known_encodings, encoding)
    best_idx = int(np.argmin(distances))

    if distances[best_idx] <= THRESHOLD_FACE_RECOGNITION:
        p = known[best_idx]
        return {
            "status": "known",
            "name": p["name"],
            "category": p.get("category", "known"),
            "distance": float(distances[best_idx])
        }
    return {"status": "unknown", "embedding": encoding.tolist()}


def _identify_insightface(image_path: str):
    import cv2
    app = _get_insightface_app()

    image = cv2.imread(image_path)
    faces = app.get(image)
    if not faces:
        return {"status": "no_face_detected"}

    embedding = faces[0].embedding
    known = [p for p in _load_known_people() if p.get("backend") == "insightface"]

    if not known:
        return {"status": "unknown", "embedding": embedding.tolist()}

    known_embeddings = np.array([p["embedding"] for p in known])
    norm_embedding = embedding / np.linalg.norm(embedding)
    norm_known = known_embeddings / np.linalg.norm(known_embeddings, axis=1, keepdims=True)
    similarities = norm_known @ norm_embedding
    best_idx = int(np.argmax(similarities))

    if similarities[best_idx] >= THRESHOLD_INSIGHTFACE:
        p = known[best_idx]
        return {
            "status": "known",
            "name": p["name"],
            "category": p.get("category", "known"),
            "similarity": float(similarities[best_idx])
        }
    return {"status": "unknown", "embedding": embedding.tolist()}


_known_cache = {"sig": None, "people": []}


def _persons_signature():
    try:
        files = [f for f in os.listdir(PERSONS_DIR) if f.endswith(".json")]
        return tuple(sorted((f, os.stat(os.path.join(PERSONS_DIR, f)).st_mtime_ns) for f in files))
    except OSError:
        return ()


def _known_people_cached():
    """Enrolled people, re-read from disk only when a person file was added, removed or edited."""
    sig = _persons_signature()
    if sig != _known_cache["sig"]:
        _known_cache["people"] = _load_known_people()
        _known_cache["sig"] = sig
    return _known_cache["people"]


def identify_embedding(encoding) -> dict:
    """Match an already-computed face_recognition (dlib) encoding against enrolled people.
    Skips decoding an image and detecting the face a second time (about 1 s saved per face).
    Only valid when BACKEND == "face_recognition"."""
    if BACKEND == "sface":
        return _identify_embedding_sface(encoding)
    import face_recognition
    enc = np.asarray(encoding)
    known = [p for p in _known_people_cached() if p.get("backend") == "face_recognition"]
    if known:
        distances = face_recognition.face_distance([np.array(p["embedding"]) for p in known], enc)
        i = int(np.argmin(distances))
        if distances[i] <= THRESHOLD_FACE_RECOGNITION:
            p = known[i]
            return {"status": "known", "name": p["name"], "category": p.get("category", "known"),
                    "distance": float(distances[i])}
    return {"status": "unknown", "embedding": enc.tolist()}


_sface = {"det": None, "rec": None}
_sface_lock = threading.Lock()   # the detector keeps its input size as state, so one detect at a time


def _get_sface():
    if _sface["det"] is None:
        import cv2
        for m in (YUNET_MODEL, SFACE_MODEL):
            if not os.path.exists(m):
                raise FileNotFoundError(f"{m} is missing - run scripts/bench_faces.py once to download the models")
        _sface["det"] = cv2.FaceDetectorYN.create(YUNET_MODEL, "", (320, 320), YUNET_SCORE_MIN, 0.3, 5000)
        _sface["rec"] = cv2.FaceRecognizerSF.create(SFACE_MODEL, "")
    return _sface["det"], _sface["rec"]


def face_sharpness(bgr, left, top, width, height) -> float:
    """Blur score of a face crop (variance of the Laplacian). Low = blurry."""
    import cv2
    crop = bgr[max(0, top):max(0, top) + height, max(0, left):max(0, left) + width]
    if crop.size == 0:
        return 0.0
    return float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def detect_and_embed(bgr):
    """YuNet + SFace on a BGR image (as cv2.imread / cv2.imdecode give).
    Returns (faces, detect_seconds, embed_seconds). Each face is
    {"loc": (top, right, bottom, left), "emb": unit-length float32 vector, "score": float, "sharp": float}."""
    det, rec = _get_sface()
    h, w = bgr.shape[:2]
    faces = []
    with _sface_lock:
        t0 = time.time()
        det.setInputSize((w, h))
        _, rows = det.detect(bgr)
        t_det = time.time() - t0
        t0 = time.time()
        for r in ([] if rows is None else rows):
            x, y, fw, fh = [int(v) for v in r[:4]]
            left, top = max(0, x), max(0, y)
            right, bottom = min(w, x + fw), min(h, y + fh)
            feat = rec.feature(rec.alignCrop(bgr, r)).ravel().astype(np.float32)
            feat = feat / (float(np.linalg.norm(feat)) or 1.0)
            faces.append({"loc": (top, right, bottom, left), "emb": feat, "score": float(r[-1]),
                          "sharp": face_sharpness(bgr, left, top, right - left, bottom - top)})
        t_emb = time.time() - t0
    return faces, t_det, t_emb


def _cos(a, b) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


def _sface_people():
    """[(person, [embeddings])] for everyone who has SFace embeddings. A person can carry several
    ("sface_embeddings"), or one if they were enrolled while BACKEND == "sface"."""
    out = []
    for p in _known_people_cached():
        embs = p.get("sface_embeddings")
        if not embs and p.get("backend") == "sface" and p.get("embedding"):
            embs = [p["embedding"]]
        if embs:
            out.append((p, [np.asarray(e, dtype=np.float32) for e in embs]))
    return out


def _identify_embedding_sface(emb) -> dict:
    emb = np.asarray(emb, dtype=np.float32)
    scored = sorted(((max(_cos(e, emb) for e in embs), p) for p, embs in _sface_people()),
                    key=lambda t: -t[0])
    result = {"status": "unknown", "embedding": emb.tolist()}
    if scored:
        best_sim, best = scored[0]
        second_sim = scored[1][0] if len(scored) > 1 else -1.0
        result["best_similarity"] = round(best_sim, 3)
        if best_sim >= THRESHOLD_SFACE:
            if len(scored) < 2 or best_sim - second_sim >= SFACE_MARGIN:
                return {"status": "known", "name": best["name"], "category": best.get("category", "known"),
                        "similarity": best_sim, "distance": 1.0 - best_sim}
            result["ambiguous"] = True      # similar to two enrolled people: don't guess
    return result


def _identify_sface(image_path: str) -> dict:
    import cv2
    bgr = cv2.imread(image_path)
    if bgr is None:
        return {"status": "no_face_detected"}
    found, _, _ = detect_and_embed(bgr)
    if not found:
        return {"status": "no_face_detected"}
    biggest = max(found, key=lambda d: d["loc"][2] - d["loc"][0])
    return _identify_embedding_sface(biggest["emb"])


def identify(image_path: str) -> dict:
    """Matches against enrolled people only. Pending-cluster matching lives in
    pending_clusters.py, layered on top of this when identify() returns 'unknown'.
    Returns one of:
    {"status": "no_face_detected"}
    {"status": "unknown", "embedding": [...]}
    {"status": "known", "name": ..., "category": ..., "distance"/"similarity": ...}
    """
    if BACKEND == "sface":
        return _identify_sface(image_path)
    if BACKEND == "insightface":
        return _identify_insightface(image_path)
    return _identify_face_recognition(image_path) 


def enroll(embedding: list, name: str, image_path: str, category: str = "known"):
    """Create a new permanent person file + reference photo. category defaults
    to 'known' — 'close' is set only via the promotion CLI command, or passed
    explicitly for manual same-session enrollment (e.g. enrolling yourself)."""
    import shutil
    os.makedirs(PERSONS_DIR, exist_ok=True)
    safe_name = name.lower().replace(" ", "_")

    person = {
        "name": name,
        "category": category,
        "backend": BACKEND,
        "embedding": embedding
    }
    json_path = os.path.join(PERSONS_DIR, f"{safe_name}.json")
    if os.path.exists(json_path):
        raise FileExistsError(f"A person named '{name}' is already enrolled — pick a different name or edit the existing file directly")

    with open(json_path, "w") as f:
        json.dump(person, f, indent=2)

    photo_path = os.path.join(PERSONS_DIR, f"{safe_name}.jpg")
    shutil.copy(image_path, photo_path)

    return json_path

