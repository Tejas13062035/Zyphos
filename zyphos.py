import sys
import os
import time
from tools.stt import listen
from core.voice_auth import enroll, verify, is_enrolled
from core.explainer import explain
from memory.store import save, recall, forget
from core.chainer import chain
from core.smart_executor import smart_execute, smart_execute_with_critique
from core.smart_planner import smart_plan
from core.planner import plan
from core.executor import execute_task
from core.daemon import start as daemon_start, stop as daemon_stop, is_running, get_pid
from core.scheduler import schedule_every, schedule_at, launch_background
from memory.store import save, recall


def run_goal(goal, smart=False, smart_plan_mode=False, critique=False, chain_mode=False):
    print(f"\nGOAL: {goal}")
    tasks = smart_plan(goal) if smart_plan_mode else plan(goal)
    print(f"TASKS: {len(tasks)} generated")
    last_result = ""
    for task in tasks:
        print(f"  → executing: {task['description']}")
        if smart:
            if critique:
                result = smart_execute_with_critique(task)
            else:
                result = smart_execute(task)
        else:
            result = execute_task(task)
        last_result = result.get("result", "")
        print(f"  ✓ {last_result}")
    if chain_mode and smart and last_result:
        print(f"[CHAIN] Starting chain from last result...")
        chain(goal, last_result)
    save(goal, tasks)
    print("MEMORY: saved")


def main():
    if len(sys.argv) < 2:
        print("Usage: python zyphos.py 'goal1' 'goal2' ...")
        return

    if sys.argv[1] in ("--help", "-h"):
        print("""
Z.Y.P.H.O.S — Usage

BASIC:
  zyphos.py "goal"                    Run goal with keyword executor
  zyphos.py --smart "goal"            Run goal with LLM tool selection
  zyphos.py --smart-plan "goal"       Run goal with LLM task planning
  zyphos.py --critique "goal"         Enable self-critique + retries
  zyphos.py --chain "goal"            Enable goal chaining after execution

VOICE:
  zyphos.py --listen                  Voice input with biometric auth

DAEMON:
  zyphos.py --daemon                  Start background daemon
  zyphos.py --stop                    Stop daemon
  zyphos.py --restart                 Restart daemon
  zyphos.py --send "goal"             Queue a goal to the daemon
  zyphos.py --smart-daemon            Enable smart mode in daemon
  zyphos.py --smart-daemon --off      Disable smart mode in daemon
  zyphos.py --status                  Show daemon + recent memory

MEMORY:
  zyphos.py --memory "query"          Semantic search past goals
  zyphos.py --forget "query"          Delete matching memory entries

SCHEDULING:
  zyphos.py --schedule "goal" --every SECONDS
  zyphos.py --schedule "goal" --at HH:MM
  zyphos.py --schedule "goal" --at HH:MM --bg

MONITORING:
  zyphos.py --watchdog                Start auto-restart watchdog

OTHER:
  zyphos.py --help                    Show this message
""")
        return

    if sys.argv[1] == "--status":
        pid = get_pid()
        running = is_running()
        print(f"DAEMON: {'running' if running else 'stopped'} (PID {pid if running else 'none'})")
        entries = recall(5)
        print(f"LAST {len(entries)} goals:")
        for e in entries:
            print(f"  [{e['timestamp']}] {e['goal']}")
        return

    if sys.argv[1] == "--memory":
        query = " ".join(sys.argv[2:])
        entries = recall(query, top_k=5)
        print(f"MEMORY RECALL: {query}")
        for e in entries:
            print(f"  [{e['timestamp']}] {e['goal']}")
            for t in e.get("tasks", []):
                print(f"    - {t}")
        return

    if sys.argv[1] == "--forget":
        query = " ".join(sys.argv[2:])
        if not query:
            print("ERROR: --forget needs a query, e.g. --forget \"test goal\"")
            return
        count = forget(query)
        print(f"FORGET: deleted {count} matching entries")
        return

    if sys.argv[1] == "--daemon":
        daemon_start()
        return

    if sys.argv[1] == "--stop":
        daemon_stop()
        return

    if sys.argv[1] == "--restart":
        daemon_stop()
        import time
        time.sleep(1)
        daemon_start()
        return

    if sys.argv[1] == "--schedule":
        goal = sys.argv[2]
        every = None
        at = None
        bg = "--bg" in sys.argv
        if "--every" in sys.argv:
            every = int(sys.argv[sys.argv.index("--every") + 1])
        if "--at" in sys.argv:
            at = sys.argv[sys.argv.index("--at") + 1]
        if bg:
            launch_background(goal, every=every, at=at)
        elif every:
            schedule_every(goal, every)
        elif at:
            schedule_at(goal, at)
        else:
            print("ERROR: --schedule needs --every SECONDS or --at HH:MM")
        return

    if sys.argv[1] == "--after":
        seconds = int(sys.argv[2])
        goal = " ".join(sys.argv[3:])
        print(f"SCHEDULED: '{goal}' in {seconds} seconds")
        import threading
        def delayed():
            import time as _time
            _time.sleep(seconds)
            run_goal(goal, smart=True, smart_plan_mode=True)
        t = threading.Thread(target=delayed, daemon=False)
        t.start()
        print(f"Waiting {seconds}s... (Ctrl+C to cancel)")
        t.join()
        return

    if sys.argv[1] == "--smart-daemon":
        flag_file = os.path.expanduser("~/zyp/state/smart_mode")
        if "--off" in sys.argv:
            if os.path.exists(flag_file):
                os.remove(flag_file)
            print("DAEMON: smart mode disabled")
        else:
            open(flag_file, "w").close()
            print("DAEMON: smart mode enabled")
        return

    if sys.argv[1] == "--watchdog":
        import subprocess
        venv_python = os.path.expanduser("~/zyp/venv/bin/python")
        log_file = open(os.path.expanduser("~/zyp/logs/watchdog.log"), "a")
        subprocess.Popen(
            [venv_python, "scripts/watchdog.py"],
            cwd=os.path.expanduser("~/zyp"),
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        print("WATCHDOG: started in background")
        return

    if sys.argv[1] == "--send":
        goal = " ".join(sys.argv[2:])
        with open(os.path.expanduser("~/zyp/state/pending_goals.txt"), "a") as f:
            f.write(goal + "\n")
        print(f"SENT: {goal}")
        return

    if sys.argv[1] == "--listen":
        duration = 5
        text = listen(duration, confirm=True)
        if text:
            run_goal(text, smart=True, smart_plan_mode=True, critique=True, chain_mode=True)
        return

    if sys.argv[1] == "--wakeword":
        from tools.wakeword import start as wakeword_start

        def on_wake():
            from tools.sidecar import speak
            speak("Yes?")
            print("WAKEWORD: listening for command...")
            try:
                goal = listen(5)
                print(f"GOAL: {goal}")
                run_goal(goal, smart=True)
            except Exception as e:
                print(f"WAKEWORD: error — {e}")

        print("WAKEWORD: starting — say 'Zyphos' or 'Arise' to activate")
        t = wakeword_start(on_wake)
        try:
            while True:
                import time as _time
                _time.sleep(1)
        except KeyboardInterrupt:
            print("WAKEWORD: stopped")
        return

    if sys.argv[1] == "--explain":
        explain()
        return

    if sys.argv[1] == "--enroll":
        enroll()
        return

    if sys.argv[1] == "--research":
        topic = " ".join(sys.argv[2:])
        if not topic:
            print("Usage: python zyphos.py --research 'your topic'")
            return
        from core.researcher import research
        report = research(topic, depth=3)
        print("\nREPORT:\n")
        print(report)
        return

    if sys.argv[1] == "--briefing":
        from scripts.briefing import briefing
        briefing()
        return

    if sys.argv[1] == "--greet":
        from core.greeter import greet
        greet()
        return

    smart = True
    smart_plan_mode = True
    critique = "--critique" in sys.argv
    chain_mode = "--chain" in sys.argv
    goals = [g for g in sys.argv[1:] if not g.startswith("--")]

    print(f"QUEUE: {len(goals)} goal(s)")
    for goal in goals:
        run_goal(goal, smart=smart, smart_plan_mode=smart_plan_mode, critique=critique, chain_mode=chain_mode)

if __name__ == "__main__":
    main()
