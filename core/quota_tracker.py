import os
import json
from datetime import datetime

QUOTA_FILE = os.path.expanduser("~/zyp/state/quota_usage.json")

# rough free-tier daily limits — adjust if these change
LIMITS = {
    "cerebras": 1000,   # requests/day (approx, varies by tier)
    "groq": 1000,       # requests/day (approx, varies by tier)
    "gemini": 1500,     # requests/day
}

def _load():
    if not os.path.exists(QUOTA_FILE):
        return {}
    try:
        with open(QUOTA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data):
    os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _today():
    return datetime.now().strftime("%Y-%m-%d")

def record_call(provider: str):
    data = _load()
    today = _today()
    if data.get("date") != today:
        data = {"date": today}
    data[provider] = data.get(provider, 0) + 1
    _save(data)

    count = data[provider]
    limit = LIMITS.get(provider, 9999)
    if limit and count >= limit * 0.8 and count < limit * 0.85:
        print(f"[QUOTA WARNING] {provider}: {count}/{limit} calls used today (80%+)")
    elif limit and count >= limit:
        print(f"[QUOTA EXCEEDED] {provider}: {count}/{limit} calls used today — likely to fail")

def get_usage() -> dict:
    data = _load()
    today = _today()
    if data.get("date") != today:
        return {"date": today, "cerebras": 0, "groq": 0, "gemini": 0}
    return data
