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
