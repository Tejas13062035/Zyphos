import time
from tools.webcam import capture
from tools.face_recognition_backend import identify
from tools.pending_clusters import record_sighting

BURST_DURATION = 2.5       # seconds per attempt
BURST_FRAME_GAP = 0.5      # seconds between frames within a burst
MAX_ATTEMPTS_NO_FACE = 3   # total attempts if nothing is ever detected
MAX_ATTEMPTS_UNKNOWN = 2   # total attempts once a face has been seen (even if unmatched)


def _burst_once():
    """Capture and identify frames for BURST_DURATION seconds.
    Returns the first non-'no_face_detected' result, or None if nothing found."""
    start = time.time()
    while (time.time() - start) < BURST_DURATION:
        try:
            image_path = capture()
        except Exception:
            time.sleep(BURST_FRAME_GAP)
            continue

        result = identify(image_path)
        if result["status"] != "no_face_detected":
            result["_image_path"] = image_path
            return result

        time.sleep(BURST_FRAME_GAP)

    return None


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

