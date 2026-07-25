#!/bin/bash
# Starts daemon, watchdog, and event reminder together

cd ~/zyp
source venv/bin/activate

echo "Starting Zyphos daemon..."
nohup python zyphos.py --daemon >> logs/daemon.log 2>&1 &

sleep 1

echo "Starting watchdog..."
python zyphos.py --watchdog

sleep 1

if ! pgrep -f "event_reminder.py" > /dev/null; then
    echo "Starting event reminder..."
    nohup python scripts/event_reminder.py >> logs/reminder.log 2>&1 &
else
    echo "Event reminder already running."
fi

sleep 1

echo ""
echo "Status:"
pgrep -f "zyphos.py --daemon" > /dev/null && echo "  Daemon:   RUNNING" || echo "  Daemon:   FAILED"
pgrep -f "watchdog.py" > /dev/null && echo "  Watchdog: RUNNING" || echo "  Watchdog: FAILED"
pgrep -f "event_reminder.py" > /dev/null && echo "  Reminder: RUNNING" || echo "  Reminder: FAILED"
