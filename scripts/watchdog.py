import time
import os
import sys
import subprocess
from datetime import datetime

INTERVAL = 30  # seconds between checks
LOG_FILE = os.path.expanduser("~/zyp/logs/watchdog.log")
VENV_PYTHON = os.path.expanduser("~/zyp/venv/bin/python")
ZYPHOS_DIR = os.path.expanduser("~/zyp")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def is_daemon_running():
    pid_file = os.path.expanduser("~/zyp/state/zyphos.pid")
    if not os.path.exists(pid_file):
        return False
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, OSError):
        return False

def is_reminder_running():
    result = subprocess.run(
        ["pgrep", "-f", "event_reminder.py"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())

def is_webui_running():
    result = subprocess.run(
        ["pgrep", "-f", "scripts/webui.py"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())

def is_hud_running():
    pid_file = os.path.expanduser("~/zyp/state/webui_hud.pid")
    if not os.path.exists(pid_file):
        return False
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, OSError):
        return False

def restart_webui():
    log("WATCHDOG: webui down — restarting...")
    proc = subprocess.Popen(
        [VENV_PYTHON, "scripts/webui.py"],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/webui.log"), "a"),
        stderr=subprocess.STDOUT
    )
    with open(os.path.expanduser("~/zyp/state/webui.pid"), "w") as f:
        f.write(str(proc.pid))
    log("WATCHDOG: webui restarted")
def restart_hud():
    log("WATCHDOG: webui_hud down — restarting...")
    proc = subprocess.Popen(
        [VENV_PYTHON, "scripts/webui_hud.py"],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/webui_hud.log"), "a"),
        stderr=subprocess.STDOUT
    )
    with open(os.path.expanduser("~/zyp/state/webui_hud.pid"), "w") as f:
        f.write(str(proc.pid))
    log("WATCHDOG: webui_hud restarted")

def restart_reminder():
    log("WATCHDOG: reminder down — restarting...")
    subprocess.Popen(
        [VENV_PYTHON, "scripts/event_reminder.py"],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/reminder.log"), "a"),
        stderr=subprocess.STDOUT
    )
    log("WATCHDOG: reminder restarted")

def restart_daemon():
    log("WATCHDOG: daemon down — restarting...")
    subprocess.Popen(
        [VENV_PYTHON, "zyphos.py", "--daemon"],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/daemon.log"), "a"),
        stderr=subprocess.STDOUT
    )
    log("WATCHDOG: daemon restarted")


def is_kokoro_up():
    import urllib.request
    for _ in range(2):   # Kokoro can be slow to answer while it's generating speech
        try:
            urllib.request.urlopen("http://localhost:8880/docs", timeout=5)
            return True
        except Exception:
            pass
    return False


def is_watcher_running():
    result = subprocess.run(
        ["pgrep", "-f", "scripts/presence_watcher.py"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


_last_kokoro_restart = 0.0


def restart_kokoro():
    global _last_kokoro_restart
    if time.time() - _last_kokoro_restart < 90:
        log("WATCHDOG: kokoro still starting — waiting")
        return
    _last_kokoro_restart = time.time()
    log("WATCHDOG: kokoro down — restarting...")
    subprocess.Popen(
        ["bash", os.path.expanduser("~/zyp/scripts/start_kokoro.sh")],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/kokoro_start.log"), "a"),
        stderr=subprocess.STDOUT
    )
    log("WATCHDOG: kokoro restart launched")


def restart_watcher():
    log("WATCHDOG: presence watcher down — restarting...")
    subprocess.Popen(
        [VENV_PYTHON, "scripts/presence_watcher.py"],
        cwd=ZYPHOS_DIR,
        stdout=open(os.path.expanduser("~/zyp/logs/presence_watcher.log"), "a"),
        stderr=subprocess.STDOUT
    )
    log("WATCHDOG: presence watcher restarted")


def main():
    log(f"WATCHDOG: started (PID {os.getpid()}) — checking every {INTERVAL}s")
    while True:
        if not is_daemon_running():
            restart_daemon()
        else:
            log("WATCHDOG: daemon OK")
        if not is_reminder_running():
            restart_reminder()
        else:
            log("WATCHDOG: reminder OK")
        if not is_webui_running():
            restart_webui()
        else:
            log("WATCHDOG: webui OK")
        if not is_hud_running():
            restart_hud()
        else:
            log("WATCHDOG: webui_hud OK")
        time.sleep(INTERVAL)
        if not is_kokoro_up():
            restart_kokoro()
        else:
            log("WATCHDOG: kokoro OK")
        if not is_watcher_running():
            restart_watcher()
        else:
            log("WATCHDOG: presence watcher OK")


if __name__ == "__main__":
    main()
