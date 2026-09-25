import time
import threading
import requests

TOOL_NAME = "timer"
TOOL_DESCRIPTION = "Set a timer or reminder. Speaks when time is up."
TOOL_ARGS = {"minutes": "number of minutes", "message": "reminder message"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def _ring(message: str):
    try:
        requests.post(f"{SIDECAR_URL}/speak", json={"text": message})
    except:
        print(f"TIMER: {message}")

def run(args: dict) -> dict:
    minutes = float(args.get("minutes", 1))
    seconds = float(args.get("seconds", 0))
    message = args.get("message", f"Timer done! {minutes} minutes are up.")
    block = args.get("block", False)

    total_seconds = minutes * 60 + seconds

    if block:
        print(f"TIMER: waiting {total_seconds}s...")
        time.sleep(total_seconds)
        _ring(message)
        return {"status": "done", "minutes": minutes, "message": message}

    def countdown():
        time.sleep(total_seconds)
        _ring(message)

    t = threading.Thread(target=countdown, daemon=True)
    t.start()
    return {"status": "timer set", "minutes": minutes, "message": message}

    return {
        "status": "timer set",
        "minutes": minutes,
        "message": message
    }
