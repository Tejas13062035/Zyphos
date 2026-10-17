#!/bin/bash
# Starts daemon, watchdog, web UI, and event reminder together
echo "$(date): start_all.sh reached" >> /home/tejas_n/zyp/logs/taskscheduler_canary.log
cd ~/zyp
source venv/bin/activate
export PYTHONPATH="$PWD:$PYTHONPATH"
export ZYPHOS_FACE_BACKEND=sface

echo "Starting Kokoro TTS..."
~/zyp/scripts/start_kokoro.sh

echo "Starting Zyphos daemon..."
if ! pgrep -f "zyphos.py --daemon" > /dev/null; then
    nohup python zyphos.py --daemon >> logs/daemon.log 2>&1 &
fi
sleep 1

echo "Starting web UI..."
if ! pgrep -f "scripts/webui.py" > /dev/null; then
    nohup python scripts/webui.py >> logs/webui.log 2>&1 &
fi
sleep 1
echo "Starting HUD web UI..."
if ! pgrep -f "scripts/webui_hud.py" > /dev/null; then
    nohup python scripts/webui_hud.py >> logs/webui_hud.log 2>&1 &
fi
sleep 1

if ! pgrep -f "event_reminder.py" > /dev/null; then
    echo "Starting event reminder..."
    nohup python scripts/event_reminder.py >> logs/reminder.log 2>&1 &
else
    echo "Event reminder already running."
fi
sleep 1

echo "Starting presence watcher..."
if ! pgrep -f "scripts/presence_watcher.py" > /dev/null; then
    nohup python scripts/presence_watcher.py >> logs/presence_watcher.log 2>&1 &
fi
sleep 1

echo "Starting watchdog..."
if ! pgrep -f "watchdog.py" > /dev/null; then
    nohup python zyphos.py --watchdog >> logs/watchdog.log 2>&1 &
fi
sleep 1

echo ""
echo "Status:"
sleep 3
check() {   # name, pattern, label-if-missing
  for i in $(seq 1 20); do
    if pgrep -f "$2" > /dev/null; then echo "  $1 RUNNING"; return; fi
    sleep 1
  done
  echo "  $1 $3"
}
check "Daemon:  " "zyphos.py --daemon" FAILED
check "Watchdog:" "scripts/watchdog.py" FAILED
check "Web UI:  " "scripts/webui.py" FAILED
check "HUD UI:  " "scripts/webui_hud.py" FAILED
check "Reminder:" "event_reminder.py" FAILED
check "Kokoro:  " "uvicorn api.src.main:app" "NOT RUNNING"
check "Watcher: " "scripts/presence_watcher.py" "NOT RUNNING"
