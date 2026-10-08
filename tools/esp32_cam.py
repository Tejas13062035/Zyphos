"""ESP32-CAM client: finds the board on whatever network you're on, no hardcoded IP."""
import concurrent.futures as cf
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
URL_FILE = ROOT / "state" / "esp_cam_url"
CAPTURE_DIR = ROOT / "state" / "captures"
CAPTURE_PATH = "/tmp/zyp_esp32_cam.jpg"

STATE_NAMES = {0: "none", 1: "moving", 2: "stationary", 3: "moving+stationary"}
SCAN_COOLDOWN_S = 20

_base = None
_last_scan = 0.0


def _normalize(s):
    s = s.strip().rstrip("/")
    if not s.startswith("http"):
        s = "http://" + s
    return re.sub(r"(https?://[^/]+).*", r"\1", s)


def _read_cached():
    try:
        return URL_FILE.read_text().strip() or None
    except OSError:
        return None


def _save(base):
    URL_FILE.parent.mkdir(parents=True, exist_ok=True)
    URL_FILE.write_text(base + "\n")


def _is_esp(base, timeout):
    """True if base answers /presence with the radar JSON our firmware serves."""
    try:
        j = requests.get(base + "/presence", timeout=timeout).json()
        return "wake_count" in j and "present" in j
    except Exception:
        return False


def _local_prefixes():
    """Network prefixes (a.b.c) of this machine and of the Windows host."""
    ips = set()
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout
        ips.update(out.split())
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-NetIPAddress -AddressFamily IPv4).IPAddress"],
            capture_output=True, text=True, timeout=8).stdout
        ips.update(out.split())
    except Exception:
        pass
    prefixes = []
    for ip in ips:
        m = re.fullmatch(r"(\d+\.\d+\.\d+)\.\d+", ip.strip())
        if m and not ip.startswith(("127.", "169.254.")) and m.group(1) not in prefixes:
            prefixes.append(m.group(1))
    old = _read_cached()          # also try the previous network
    if old:
        m = re.match(r"https?://(\d+\.\d+\.\d+)\.\d+", old)
        if m and m.group(1) not in prefixes:
            prefixes.append(m.group(1))
    return prefixes


def discover():
    candidates = [f"http://{p}.{i}" for p in _local_prefixes() for i in range(1, 255)]
    ex = cf.ThreadPoolExecutor(max_workers=100)
    futs = {ex.submit(_is_esp, b, 0.6): b for b in candidates}
    try:
        for f in cf.as_completed(futs):
            if f.result():
                return futs[f]
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return None


def base_url():
    """Return the ESP's base URL, using the cache first and scanning if needed."""
    global _base, _last_scan
    if _base:
        return _base
    for cand in (_read_cached(), os.environ.get("ESP_CAM_URL")):
        if cand:
            cand = _normalize(cand)
            if _is_esp(cand, 1.5):
                _base = cand
                return _base
    if time.time() - _last_scan < SCAN_COOLDOWN_S:
        raise RuntimeError("ESP32-CAM not found (scanned recently, waiting before retrying)")
    _last_scan = time.time()
    found = discover()
    if not found:
        raise RuntimeError("ESP32-CAM not found on the network")
    _save(found)
    _base = found
    print(f"[esp32_cam] found at {found}")
    return _base


_fails = 0


def _get(path, timeout):
    """A busy ESP is retried at the same address; only repeated failures trigger a re-scan."""
    global _base, _fails
    last_err = None
    for _ in range(2):
        try:
            r = requests.get(base_url() + path, timeout=timeout)
            _fails = 0
            return r
        except requests.RequestException as e:
            last_err = e
            _fails += 1
            if _fails >= 4:
                _base = None      # looks like it really moved, so re-discover
                _fails = 0
    raise last_err


def capture() -> str:
    """Fetch one JPEG frame from the ESP32-CAM. Returns the local path (same as before)."""
    r = _get("/capture", 10)
    r.raise_for_status()
    with open(CAPTURE_PATH, "wb") as f:
        f.write(r.content)
    return CAPTURE_PATH


def capture_to_file(prefix="snap"):
    """Fetch one frame and keep it under state/captures/. Returns the path as a string."""
    r = _get("/capture", 10)
    r.raise_for_status()
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    path.write_bytes(r.content)
    return str(path)


def presence(timeout=2):
    r = _get("/presence", timeout)
    r.raise_for_status()
    return r.json()


def describe(p):
    if not (p.get("present") or p.get("pir")):
        return "The room looks empty."
    state = int(p.get("state", 0))
    if state == 0:
        return "A presence signal is still active, but the radar sees no target right now."
    dist = p.get("mov_cm") or p.get("stat_cm")
    where = f" about {dist / 100:.1f} m from the sensor" if dist else ""
    return f"Someone is in the room ({STATE_NAMES.get(state)}){where}."


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:                      # manual override: python3 tools/esp32_cam.py 10.1.2.3
        _save(_normalize(sys.argv[1]))
        print("saved", _normalize(sys.argv[1]))
    else:
        print("ESP32-CAM at", base_url())
        print(describe(presence()))
