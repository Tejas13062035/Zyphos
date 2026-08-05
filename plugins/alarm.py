import json
import os
import uuid
from datetime import datetime, timedelta

TOOL_NAME = "alarm"
TOOL_DESCRIPTION = "sets, lists, or cancels alarms — e.g. 'set an alarm for 7:30 AM' or 'set an alarm in 20 minutes'"
TOOL_ARGS = {"action": "str (set|list|cancel)", "time": "str (HH:MM 24hr format, or 'in N minutes')", "label": "str (optional description)", "alarm_id": "str (for cancel)"}

ALARMS_FILE = os.path.expanduser("~/zyp/state/alarms.json")


def _load_alarms():
    if not os.path.exists(ALARMS_FILE):
        return []
    with open(ALARMS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_alarms(alarms):
    with open(ALARMS_FILE, "w") as f:
        json.dump(alarms, f, indent=2)


def _parse_time(time_str: str) -> str:
    time_str = time_str.strip().lower()

    if "in" in time_str and "minute" in time_str:
        import re
        match = re.search(r'\d+', time_str)
        if match:
            minutes = int(match.group())
            target = datetime.now() + timedelta(minutes=minutes)
            return target.strftime("%H:%M")

    try:
        parsed = datetime.strptime(time_str, "%H:%M")
        return parsed.strftime("%H:%M")
    except ValueError:
        pass

    try:
        parsed = datetime.strptime(time_str, "%I:%M %p")
        return parsed.strftime("%H:%M")
    except ValueError:
        pass

    return time_str


def run(args: dict) -> dict:
    action = args.get("action", "set").lower()

    if action == "set":
        time_str = args.get("time", "")
        label = args.get("label", "").strip() or "Alarm"

        if not time_str:
            return {"status": "error", "result": "no time provided"}

        target_time = _parse_time(time_str)

        alarms = _load_alarms()
        alarm = {
            "id": str(uuid.uuid4())[:8],
            "time": target_time,
            "label": label,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "triggered": False
        }
        alarms.append(alarm)
        _save_alarms(alarms)

        return {"status": "ok", "result": f"Alarm set for {target_time} — {label} (id: {alarm['id']})"}

    elif action == "list":
        alarms = _load_alarms()
        active = [a for a in alarms if not a["triggered"]]
        if not active:
            return {"status": "ok", "result": "No active alarms."}
        lines = [f"{a['id']}: {a['time']} — {a['label']}" for a in active]
        return {"status": "ok", "result": "\n".join(lines)}

    elif action == "cancel":
        alarm_id = args.get("alarm_id", "")
        alarms = _load_alarms()
        remaining = [a for a in alarms if a["id"] != alarm_id]
        deleted = len(alarms) - len(remaining)
        _save_alarms(remaining)
        return {"status": "ok", "result": f"Cancelled {deleted} alarm(s)."}

    else:
        return {"status": "error", "result": f"unknown action: {action}"}
