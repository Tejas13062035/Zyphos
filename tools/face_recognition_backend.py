import os
import json
import numpy as np

BACKEND = os.environ.get("ZYPHOS_FACE_BACKEND", "face_recognition").lower()
PERSONS_DIR = os.path.expanduser("~/zyp/memory/persons")

THRESHOLD_FACE_RECOGNITION = 0.6   # dlib distance — lower is stricter
THRESHOLD_INSIGHTFACE = 0.5        # cosine similarity — higher is stricter

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


def identify(image_path: str) -> dict:
    """Matches against enrolled people only. Pending-cluster matching lives in
    pending_clusters.py, layered on top of this when identify() returns 'unknown'.
    Returns one of:
    {"status": "no_face_detected"}
    {"status": "unknown", "embedding": [...]}
    {"status": "known", "name": ..., "category": ..., "distance"/"similarity": ...}
    """
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

