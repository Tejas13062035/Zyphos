import time
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/zyp"))

from plugins.alarm import _load_alarms, _save_alarms
from plugins.calendar import run as calendar_run
import requests

CHECK_INTERVAL = 300  # 5 minutes — for calendar event reminders
ALARM_CHECK_INTERVAL = 30  # 30 seconds — for precise alarm firing
REMINDER_WINDOWS = [30, 10]  # minutes before event to remind
LOG_FILE = os.path.expanduser("~/zyp/logs/reminder.log")
REMINDED_FILE = os.path.expanduser("~/zyp/state/reminded_events.txt")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def speak(text):
    try:
        requests.post("http://127.0.0.1:5000/speak", json={"text": text}, timeout=5)
    except Exception:
        pass


def get_reminded():
    if not os.path.exists(REMINDED_FILE):
        return set()
    with open(REMINDED_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def mark_reminded(event_id):
    with open(REMINDED_FILE, "a") as f:
        f.write(event_id + "\n")

def _trigger_alarm(label: str):
    import time as time_module
    urgent_msg = f"Alarm! Alarm! {label}! Wake up!"
    for i in range(5):
        speak(urgent_msg)
        time_module.sleep(1.5)


def check_alarms():
    alarms = _load_alarms()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    changed = False
    for alarm in alarms:
        if alarm.get("triggered", False):
            continue
        if alarm["date"] != today_str:
            continue
        try:
            alarm_time = datetime.strptime(f"{today_str} {alarm['time']}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if now >= alarm_time:
            log(f"ALARM TRIGGERED: {alarm['label']}")
            _trigger_alarm(alarm["label"])
            alarm["triggered"] = True
            changed = True
    if changed:
        _save_alarms(alarms)

def check_events():
    reminded = get_reminded()
    result = calendar_run({"action": "today"})

    if result.get("status") != "ok":
        return

    events = result.get("events", [])
    now = datetime.now()
    newly_reminded = []

    for event_str in events:
        try:
            time_part, title = event_str.split(": ", 1)
            event_time = datetime.fromisoformat(time_part.strip())
            minutes_until = (event_time.replace(tzinfo=None) - now).total_seconds() / 60

            for window in REMINDER_WINDOWS:
                event_id = f"{time_part}_{title.strip()}_{window}min"
                if event_id in reminded or event_id in newly_reminded:
                    continue

                if 0 <= minutes_until <= window:
                    msg = f"Reminder: {title.strip()} starts in about {int(minutes_until)} minutes."
                    log(msg)
                    speak(msg)
                    newly_reminded.append(event_id)
        except (ValueError, IndexError):
            continue

    for event_id in newly_reminded:
        mark_reminded(event_id)


def main():
    log("Event reminder started — 30min/10min event windows, 30s alarm precision")
    last_event_check = 0

    while True:
        now = time.time()

        try:
            check_alarms()
        except Exception as e:
            log(f"Error checking alarms: {e}")

        if now - last_event_check >= CHECK_INTERVAL:
            try:
                check_events()
            except Exception as e:
                log(f"Error checking events: {e}")
            last_event_check = now

        time.sleep(ALARM_CHECK_INTERVAL)

if __name__ == "__main__":
    main()
