import psutil
import os
import requests

TOOL_NAME = "system_stats"
TOOL_DESCRIPTION = "Get CPU, RAM, disk usage and battery stats"
TOOL_ARGS = {"speak": "true/false to speak the result"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def run(args: dict) -> dict:
    speak = args.get("speak", False)

    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()

    ram_used = round(ram.used / 1024**3, 1)
    ram_total = round(ram.total / 1024**3, 1)
    disk_used = round(disk.used / 1024**3, 1)
    disk_total = round(disk.total / 1024**3, 1)

    battery_info = f"{round(battery.percent)}% {'charging' if battery.power_plugged else 'on battery'}" if battery else "unknown"

    summary = (
        f"CPU {cpu}%, "
        f"RAM {ram_used}GB of {ram_total}GB used, "
        f"Disk {disk_used}GB of {disk_total}GB used, "
        f"Battery {battery_info}"
    )

    if speak:
        try:
            requests.post(f"{SIDECAR_URL}/speak", json={"text": summary})
        except:
            pass

    return {
        "status": "ok",
        "cpu_percent": cpu,
        "ram_used_gb": ram_used,
        "ram_total_gb": ram_total,
        "disk_used_gb": disk_used,
        "disk_total_gb": disk_total,
        "battery": battery_info,
        "summary": summary
    }
