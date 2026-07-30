import os
import json
from datetime import datetime

LOG_FILE = os.path.expanduser("~/zyp/state/tool_usage.jsonl")

def log_tool_use(tool_name: str):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = {"tool": tool_name, "timestamp": datetime.now().isoformat()}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def read_usage():
    if not os.path.exists(LOG_FILE):
        return []
    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return entries
