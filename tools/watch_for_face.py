import shutil
import time
from tools.esp32_cam import capture
from tools.face_recognition_backend import identify
from tools.pending_clusters import record_sighting

BURST_FRAMES = 6           # frames examined per attempt
BURST_MAX_SECONDS = 15     # safety cap per attempt (a frame can take a few seconds over WiFi)
BURST_FRAME_GAP = 0.3      # seconds between frames within a burst
MAX_ATTEMPTS_NO_FACE = 3   # total attempts if nothing is ever detected
MAX_ATTEMPTS_UNKNOWN = 2   # total attempts once a face has been seen (even if unmatched)


def _burst_once():
    """Capture and identify up to BURST_FRAMES frames.
    Returns a 'known' result as soon as one frame matches. If the frames show only
    unmatched faces, returns the first of them (its image is copied so later captures
    can't overwrite it). Returns None if no frame contains a face."""
    start = time.time()
    first_seen = None
    for _ in range(BURST_FRAMES):
        if (time.time() - start) > BURST_MAX_SECONDS:
            break
        try:
            image_path = capture()
        except Exception:
            time.sleep(BURST_FRAME_GAP)
            continue

        result = identify(image_path)
        status = result["status"]

        if status == "known":
            result["_image_path"] = image_path
            return result

        if status != "no_face_detected" and first_seen is None:
            keep = f"/tmp/zyp_face_{int(time.time() * 1000)}.jpg"
            shutil.copy(image_path, keep)
            result["_image_path"] = keep
            first_seen = result

        time.sleep(BURST_FRAME_GAP)

    return first_seen


def watch_until_resolved() -> dict:
    """Called when PIR fires. Runs bursts until a face is recognized (known or
    unknown) or the attempt budget runs out. Attempt budget shortens to
    MAX_ATTEMPTS_UNKNOWN the moment any face is detected, even unmatched."""
    attempts = 0
    max_attempts = MAX_ATTEMPTS_NO_FACE  # widens/narrows based on what's seen

    while attempts < max_attempts:
        attempts += 1
        result = _burst_once()

        if result is None:
            continue  # no face this burst, keep going under the current budget

        if result["status"] == "known":
            return result

        if result["status"] == "unknown":
            max_attempts = min(max_attempts, attempts + (MAX_ATTEMPTS_UNKNOWN - 1))
            if attempts >= max_attempts:
                cluster_id = record_sighting(result["embedding"], result["_image_path"])
                result["cluster_id"] = cluster_id
                return result
            # else: one more attempt allowed, loop continues

    return {"status": "gave_up", "attempts": attempts}

