"""Daemon process for continuously processing pending goals.

The daemon watches a file (``pending_goals.txt``) for new goals, executes them
using either the keyword planner or the smart planner, logs activity, and
stores results. It also provides utilities for starting, stopping, and
checking the daemon status.
"""

import os
import signal
import sys
import time
from datetime import datetime
from typing import List, Optional

from core.executor import execute_task
from core.planner import plan
from core.smart_executor import smart_execute_with_critique
from core.smart_planner import smart_plan
from memory.store import save

# Configuration --------------------------------------------------------------

BACKEND = os.environ.get("ZYPHOS_BACKEND", "phi").lower()
GOAL_FILE = os.path.expanduser("~/zyp/state/pending_goals.txt")
LOG_FILE = os.path.expanduser("~/zyp/logs/daemon.log")
PID_FILE = os.path.expanduser("~/zyp/state/zyphos.pid")


# Helper functions -----------------------------------------------------------

def _ensure_log_dir() -> None:
    """Make sure the directory for the log file exists."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log(msg: str) -> None:
    """Write a timestamped message to stdout and to the daemon log file.

    Args:
        msg: Message to log.
    """
    _ensure_log_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_pid() -> None:
    """Write the current process PID to ``PID_FILE``."""
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def clear_pid() -> None:
    """Remove the PID file if it exists."""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def get_pid() -> Optional[int]:
    """Read the PID from ``PID_FILE``.

    Returns:
        The PID as an ``int`` or ``None`` if the file is missing or malformed.
    """
    if not os.path.exists(PID_FILE):
        return None
    with open(PID_FILE, "r", encoding="utf-8") as f:
        try:
            return int(f.read().strip())
        except ValueError:
            return None


def is_running() -> bool:
    """Check whether a process with the stored PID is still alive."""
    pid = get_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def stop() -> None:
    """Terminate a running daemon process."""
    pid = get_pid()
    if pid is None:
        print("DAEMON: not running (no PID file)")
        return
    if not is_running():
        print("DAEMON: not running (stale PID)")
        clear_pid()
        return
    os.kill(pid, signal.SIGTERM)
    clear_pid()
    print(f"DAEMON: stopped (PID {pid})")


# Core daemon logic -----------------------------------------------------------

def run_goal(goal: str) -> None:
    """Execute a single goal, logging each step.

    The function decides between the keyword planner and the smart planner
    based on the ``BACKEND`` environment variable or the presence of a
    ``smart_mode`` flag file.

    Args:
        goal: The textual description of the goal to run.
    """
    log(f"GOAL: {goal}")
    use_smart = BACKEND == "llama" or os.path.exists(
        os.path.expanduser("~/zyp/state/smart_mode")
    )

    if use_smart:
        log("MODE: smart")
        tasks = smart_plan(goal)
    else:
        log("MODE: keyword")
        tasks = plan(goal)

    log(f"TASKS: {len(tasks)} generated")
    for task in tasks:
        log(f"  → {task['description']}")
        if use_smart:
            result = smart_execute_with_critique(task)
            result_str = result.get("result", {})
            if isinstance(result_str, dict):
                result_str = result_str.get("result", str(result_str))
        else:
            result = execute_task(task)
            result_str = result.get("result", "")
        log(f"  ✓ {result_str}")
    save(goal, tasks)


def start() -> None:
    """Start the daemon loop.

    The daemon writes its PID file, installs signal handlers for graceful
    shutdown, and then continuously polls ``GOAL_FILE`` for new goals.
    """
    if is_running():
        print(f"DAEMON: already running (PID {get_pid()})")
        return

    write_pid()
    log(f"DAEMON: started (PID {os.getpid()})")
    # Ensure the pending‑goals file exists.
    os.makedirs(os.path.dirname(GOAL_FILE), exist_ok=True)
    open(GOAL_FILE, "a", encoding="utf-8").close()

    def handle_exit(signum: int, frame) -> None:  # pragma: no cover
        log("DAEMON: shutting down")
        clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    while True:
        with open(GOAL_FILE, "r", encoding="utf-8") as f:
            goals: List[str] = [g.strip() for g in f.readlines() if g.strip()]
        if goals:
            # Clear the file before processing to avoid duplicate work if
            # the daemon crashes while handling a goal.
            with open(GOAL_FILE, "w", encoding="utf-8") as f:
                f.write("")
            for goal in goals:
                run_goal(goal)
        time.sleep(2)


if __name__ == "__main__":
    start()
