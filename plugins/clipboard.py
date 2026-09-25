import requests

TOOL_NAME = "clipboard"
TOOL_DESCRIPTION = "Read or write Windows clipboard content"
TOOL_ARGS = {"action": "get|set", "text": "text to copy (for set)"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def run(args: dict) -> dict:
    action = args.get("action", "get").lower()

    if action == "get":
        r = requests.get(f"{SIDECAR_URL}/clipboard/get")
        return r.json()

    elif action == "set":
        text = args.get("text", "")
        r = requests.post(f"{SIDECAR_URL}/clipboard/set", json={"text": text})
        return r.json()

    return {"error": f"unknown action: {action}"}
