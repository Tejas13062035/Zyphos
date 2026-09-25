from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

import subprocess
import re

TOOL_NAME = "network_scan"
TOOL_DESCRIPTION = "Scan local network for connected devices using nmap"
TOOL_ARGS = {"action": "scan|quick", "target": "IP range e.g. 192.168.1.0/24"}

def get_local_range():
    result = subprocess.run(["ip", "route"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "src" in line and "kernel" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "src":
                    ip = parts[i+1]
                    base = ".".join(ip.split(".")[:3])
                    return f"{base}.0/24"
    return "192.168.31.0/24"

def run(args: dict) -> dict:
    import requests as req
    base = args.get("target", "192.168.31")
    print(f"NETWORK: scanning {base}.0/24 via sidecar...")
    r = req.post(f"{SIDECAR_URL}/network_scan", json={"target": base}, timeout=120)
    return r.json()

        
