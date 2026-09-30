"""
Auto-detects the correct URL to reach the Windows sidecar from WSL.
Tries 127.0.0.1 first (fast path, works when WSL localhost forwarding
is functioning). Falls back to the WSL default gateway IP if that fails.
Caches the working URL after first successful detection.
"""
import subprocess
import requests

_cached_url = None


def _get_gateway_ip():
    try:
        result = subprocess.run(
            ["ip", "route", "show"],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            if line.startswith("default via"):
                return line.split()[2]
    except Exception:
        pass
    return None


def get_sidecar_url():
    global _cached_url
    if _cached_url:
        try:
            r = requests.get(f"{_cached_url}/status", timeout=1)
            if r.status_code == 200:
                return _cached_url
        except Exception:
            pass
        _cached_url = None  # cached URL stopped working, re-detect below

    candidates = ["http://127.0.0.1:5000"]
    gateway = _get_gateway_ip()
    if gateway:
        candidates.append(f"http://{gateway}:5000")

    for url in candidates:
        try:
            r = requests.get(f"{url}/status", timeout=2)
            if r.status_code == 200:
                _cached_url = url
                return url
        except Exception:
            continue

    _cached_url = candidates[0]
    return candidates[0]
