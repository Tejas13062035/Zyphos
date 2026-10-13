#!/bin/bash
# Starts daemon, watchdog, web UI, and event reminder together
echo "$(date): start_all.sh reached" >> /home/tejas_n/zyp/logs/taskscheduler_canary.log
cd ~/zyp
source venv/bin/activate
export PYTHONPATH="$PWD:$PYTHONPATH"

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
pgrep -f "zyphos.py --daemon" > /dev/null && echo "  Daemon:   RUNNING" || echo "  Daemon:   FAILED"
pgrep -f "watchdog.py" > /dev/null && echo "  Watchdog: RUNNING" || echo "  Watchdog: FAILED"
pgrep -f "scripts/webui.py" > /dev/null && echo "  Web UI:   RUNNING" || echo "  Web UI:   FAILED"
pgrep -f "scripts/webui_hud.py" > /dev/null && echo "  HUD UI:   RUNNING" || echo "  HUD UI:   FAILED"
pgrep -f "event_reminder.py" > /dev/null && echo "  Reminder: RUNNING" || echo "  Reminder: FAILED"
pgrep -f "uvicorn api.src.main:app" > /dev/null && echo "  Kokoro:   RUNNING" || echo "  Kokoro:   NOT RUNNING"
pgrep -f "scripts/presence_watcher.py" > /dev/null && echo "  Watcher:  RUNNING" || echo "  Watcher:  NOT RUNNING"
