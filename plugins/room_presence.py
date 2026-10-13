from tools import esp32_cam

TOOL_NAME = "room_presence"
TOOL_DESCRIPTION = "Check whether someone is in the room (radar + motion sensor), or take a snapshot with the room camera."
TOOL_ARGS = {"action": "status or snapshot"}


def run(action="status", **kwargs):
    try:
        if action == "snapshot":
            return f"Snapshot saved: {esp32_cam.capture_to_file('snap')}"
        return esp32_cam.describe(esp32_cam.presence())
    except Exception as e:
        return f"Room sensor unreachable: {e}"


from tools import esp32_cam

TOOL_NAME = "room_presence"
TOOL_DESCRIPTION = "Check whether someone is in the room (radar + motion sensor), or take a snapshot with the room camera."
TOOL_ARGS = {"action": "status or snapshot"}


def run(args: dict) -> dict:
    action = str((args or {}).get("action", "status")).strip().lower()
    try:
        if action in ("snapshot", "photo", "picture", "capture"):
            path = esp32_cam.capture_to_file("snap")
            return {"status": "ok", "result": f"Snapshot saved: {path}", "path": path}
        return {"status": "ok", "result": esp32_cam.describe(esp32_cam.presence())}
    except Exception as e:
        return {"status": "error", "result": f"Room sensor unreachable: {e}"}
