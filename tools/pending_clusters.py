import os
import json
import time
import shutil
import numpy as np

from tools.face_recognition_backend import BACKEND, get_quality_score

PENDING_DIR = os.path.expanduser("~/zyp/memory/persons/pending")

THRESHOLD_FACE_RECOGNITION = 0.6
THRESHOLD_INSIGHTFACE = 0.5

QUALITY_WINDOW = 10  # consider only the last N sightings when picking a resolution photo


def _cluster_dir(cluster_id: str) -> str:
    return os.path.join(PENDING_DIR, cluster_id)


def _load_cluster_info(cluster_id: str) -> dict:
    with open(os.path.join(_cluster_dir(cluster_id), "info.json")) as f:
        return json.load(f)


def _save_cluster_info(cluster_id: str, info: dict):
    with open(os.path.join(_cluster_dir(cluster_id), "info.json"), "w") as f:
        json.dump(info, f, indent=2)


def _load_cluster_embedding(cluster_id: str) -> np.ndarray:
    with open(os.path.join(_cluster_dir(cluster_id), "embedding.json")) as f:
        return np.array(json.load(f)["embedding"])


def _save_cluster_embedding(cluster_id: str, embedding: np.ndarray):
    with open(os.path.join(_cluster_dir(cluster_id), "embedding.json"), "w") as f:
        json.dump({"embedding": embedding.tolist()}, f)


def list_clusters() -> list:
    """All existing pending clusters, newest-first by last_seen."""
    if not os.path.exists(PENDING_DIR):
        return []
    clusters = []
    for entry in os.listdir(PENDING_DIR):
        info_path = os.path.join(PENDING_DIR, entry, "info.json")
        if os.path.exists(info_path):
            with open(info_path) as f:
                clusters.append(json.load(f))
    return sorted(clusters, key=lambda c: c["last_seen"], reverse=True)


def _match_against_clusters(embedding: list):
    """Compare a new unknown embedding against every existing cluster's centroid.
    Returns (cluster_id, score) for the best match within threshold, or (None, None)."""
    clusters = list_clusters()
    if not clusters:
        return None, None

    embedding = np.array(embedding)
    best_id, best_score = None, None

    for c in clusters:
        centroid = _load_cluster_embedding(c["id"])

        if BACKEND == "insightface":
            sim = float(
                (centroid / np.linalg.norm(centroid)) @ (embedding / np.linalg.norm(embedding))
            )
            if sim >= THRESHOLD_INSIGHTFACE and (best_score is None or sim > best_score):
                best_id, best_score = c["id"], sim
        else:
            dist = float(np.linalg.norm(centroid - embedding))
            if dist <= THRESHOLD_FACE_RECOGNITION and (best_score is None or dist < best_score):
                best_id, best_score = c["id"], dist

    return best_id, best_score


def _new_cluster(embedding: list, image_path: str) -> str:
    cluster_id = str(int(time.time() * 1000))
    cdir = _cluster_dir(cluster_id)
    os.makedirs(os.path.join(cdir, "sightings"), exist_ok=True)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    info = {
        "id": cluster_id,
        "backend": BACKEND,
        "first_seen": now,
        "last_seen": now,
        "sighting_count": 1
    }
    _save_cluster_info(cluster_id, info)
    _save_cluster_embedding(cluster_id, np.array(embedding))
    _add_sighting_photo(cluster_id, image_path, now)

    return cluster_id


def _add_sighting_photo(cluster_id: str, image_path: str, timestamp: str):
    safe_ts = timestamp.replace(" ", "_").replace(":", "-")
    dest = os.path.join(_cluster_dir(cluster_id), "sightings", f"{safe_ts}.jpg")
    shutil.copy(image_path, dest)


def record_sighting(embedding: list, image_path: str) -> str:
    """Main entry point. Call this whenever identify() returns 'unknown'.
    Matches against existing clusters; updates centroid + logs sighting if matched,
    otherwise creates a new cluster. Returns the cluster_id either way."""
    cluster_id, _ = _match_against_clusters(embedding)

    if cluster_id is None:
        return _new_cluster(embedding, image_path)

    # matched an existing cluster — update centroid (incremental mean) and log sighting
    info = _load_cluster_info(cluster_id)
    old_centroid = _load_cluster_embedding(cluster_id)
    n = info["sighting_count"]

    new_embedding = np.array(embedding)
    new_centroid = (old_centroid * n + new_embedding) / (n + 1)
    _save_cluster_embedding(cluster_id, new_centroid)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    info["sighting_count"] = n + 1
    info["last_seen"] = now
    _save_cluster_info(cluster_id, info)
    _add_sighting_photo(cluster_id, image_path, now)

    return cluster_id


def _best_sighting_photo(cluster_id: str) -> str:
    """Pick the highest InsightFace det_score photo among the last QUALITY_WINDOW
    sightings (by filename, which sorts chronologically since timestamps are
    zero-padded ISO-ish strings)."""
    sightings_dir = os.path.join(_cluster_dir(cluster_id), "sightings")
    files = sorted(os.listdir(sightings_dir))[-QUALITY_WINDOW:]

    best_path, best_score = None, -1.0
    for fname in files:
        path = os.path.join(sightings_dir, fname)
        score = get_quality_score(path)
        if score > best_score:
            best_path, best_score = path, score

    return best_path


def resolve_cluster(cluster_id: str, name: str, category: str = "known") -> str:
    """Convert a pending cluster into a permanent enrolled person, using the
    best-quality photo from its recent sightings as the reference image.
    Deletes the pending cluster afterward."""
    from tools.face_recognition_backend import enroll

    centroid = _load_cluster_embedding(cluster_id)
    best_photo = _best_sighting_photo(cluster_id)

    person_path = enroll(centroid.tolist(), name, best_photo, category=category)

    shutil.rmtree(_cluster_dir(cluster_id))
    return person_path
