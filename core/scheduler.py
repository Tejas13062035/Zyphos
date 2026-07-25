"""Scheduler utilities for running goals at intervals or specific times.

This module provides functions to:
- Execute a single goal immediately (`run_goal`).
- Repeatedly execute a goal every *n* seconds (`schedule_every`).
- Execute a goal at a specific clock time each day (`schedule_at`).
- Launch a background process that will schedule a goal using the main
  `zyphos.py` entry point (`launch_background`).

All functions are intentionally side‑effecting (printing to stdout,
sleeping, spawning subprocesses) and return ``None``.
"""

import sys
import subprocess
import time
from datetime import datetime
from typing import Optional

from core.executor import execute_task
from core.planner import plan
from memory.store import save


def run_goal(goal: str) -> None:
    """Execute a single goal.

    The goal is parsed into tasks by :func:`core.planner.plan`. Each task is
    executed with :func:`core.executor.execute_task` and the result is printed.
    The goal and its tasks are persisted via :func:`memory.store.save`.

    Args:
        goal: The textual description of the goal to run.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] GOAL: {goal}")
    tasks = plan(goal)
    print(f"TASKS: {len(tasks)} generated")
    for task in tasks:
        print(f"  → executing: {task['description']}")
        result = execute_task(task)
        print(f"  ✓ {result['result']}")
    save(goal, tasks)


def schedule_every(goal: str, seconds: int) -> None:
    """Run ``goal`` repeatedly every ``seconds`` seconds.

    This function blocks indefinitely until the user interrupts with
    ``Ctrl+C``.

    Args:
        goal: The goal to execute.
        seconds: Interval between executions.
    """
    print(f"SCHEDULER: '{goal}' every {seconds}s — Ctrl+C to stop")
    while True:
        run_goal(goal)
        time.sleep(seconds)


def schedule_at(goal: str, time_str: str) -> None:
    """Run ``goal`` once each day at the specified ``HH:MM`` time.

    The function checks the current time every 10 seconds and triggers the
    goal when the clock matches ``time_str``. After triggering, it sleeps for
    a minute to avoid double‑triggering within the same minute.

    Args:
        goal: The goal to execute.
        time_str: Target time in ``HH:MM`` 24‑hour format.
    """
    print(f"SCHEDULER: '{goal}' at {time_str}")
    while True:
        now = datetime.now().strftime("%H:%M")
        if now == time_str:
            run_goal(goal)
            time.sleep(60)  # prevent double‑trigger within same minute
        time.sleep(10)


def launch_background(goal: str, every: Optional[int] = None, at: Optional[str] = None) -> None:
    """Spawn a detached background process that schedules ``goal``.

    The background process runs ``zyphos.py`` with the appropriate command‑line
    arguments so that the main application handles the scheduling logic.

    Args:
        goal: The goal to schedule.
        every: If provided, schedule the goal every ``every`` seconds.
        at: If provided, schedule the goal at the given ``HH:MM`` time.
    """
    args = [sys.executable, "zyphos.py", "--schedule", goal]
    if every is not None:
        args += ["--every", str(every)]
    if at is not None:
        args += ["--at", at]

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"SCHEDULER: running in background (PID {proc.pid})")
