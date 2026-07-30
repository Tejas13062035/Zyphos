import os
import requests
from dotenv import load_dotenv
from core.quota_tracker import get_usage, LIMITS
load_dotenv(os.path.expanduser("~/zyp/.env"))

TOOL_NAME = "doctor"
TOOL_DESCRIPTION = "Run a full system health check across LLM APIs, sidecar, memory index, and config"
TOOL_ARGS = {}

def _check_env_keys():
    required = [
        "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
        "OPENWEATHER_API_KEY", "NEWS_API_KEY", "NASA_API_KEY", "GITHUB_TOKEN"
    ]
    missing = [k for k in required if not os.getenv(k)]
    return missing

def _check_cerebras():
    try:
        r = requests.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('CEREBRAS_API_KEY')}"},
            json={"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False

def _check_sidecar():
    try:
        r = requests.get("http://127.0.0.1:5000/status", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def _check_disk():
    import shutil
    total, used, free = shutil.disk_usage(os.path.expanduser("~"))
    free_gb = free / (1024 ** 3)
    return free_gb

def _check_memory_index():
    index_path = os.path.expanduser("~/zyp/state/memory.index")
    memory_json = os.path.expanduser("~/zyp/state/memory.json")
    return os.path.exists(index_path) and os.path.exists(memory_json)

def _check_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def _check_known_issues():
    issues = []

    # Check 1: Cerebras reasoning-model truncation risk
    # If max_tokens is set too low anywhere critical, warn
    llm_path = os.path.expanduser("~/zyp/core/llm.py")
    if os.path.exists(llm_path):
        with open(llm_path) as f:
            content = f.read()
        if "reasoning_effort" not in content:
            issues.append("Cerebras calls missing 'reasoning_effort' param — risk of JSON truncation on short prompts (seen with gpt-oss-120b)")

    # Check 2: researcher.py fallback query max_tokens too low
    researcher_path = os.path.expanduser("~/zyp/core/researcher.py")
    if os.path.exists(researcher_path):
        with open(researcher_path) as f:
            content = f.read()
        if "max_tokens=30\n" in content or "max_tokens=30," in content or "max_tokens=60\n" in content or "max_tokens=60," in content or "max_tokens=60)" in content:
            issues.append("researcher.py follow-up query max_tokens may be too low — can cause reasoning-model truncation, use 150+")

    # Check 3: stale memory index size sanity check
    memory_json = os.path.expanduser("~/zyp/state/memory.json")
    if os.path.exists(memory_json):
        size_mb = os.path.getsize(memory_json) / (1024 * 1024)
        if size_mb > 50:
            issues.append(f"memory.json is {size_mb:.1f}MB — consider running --forget to prune old entries, large files slow FAISS load")

    # Check 4: reports/ folder growing unbounded (should be gitignored but still fills disk)
    reports_dir = os.path.expanduser("~/zyp/reports")
    if os.path.exists(reports_dir):
        count = len([f for f in os.listdir(reports_dir) if f.endswith(".txt")])
        if count > 30:
            issues.append(f"reports/ has {count} files — consider archiving or deleting old research reports")

    return issues

def run(args=None):
    results = []

    missing_keys = _check_env_keys()
    if missing_keys:
        results.append(f"MISSING KEYS: {', '.join(missing_keys)}")
    else:
        results.append("API keys: all present")

    cerebras_ok = _check_cerebras()
    results.append(f"Cerebras LLM: {'reachable' if cerebras_ok else 'UNREACHABLE'}")

    sidecar_ok = _check_sidecar()
    results.append(f"Windows sidecar: {'running' if sidecar_ok else 'NOT RUNNING'}")

    ollama_ok = _check_ollama()
    results.append(f"Ollama (local LLM): {'running' if ollama_ok else 'not running (optional)'}")

    mem_ok = _check_memory_index()
    results.append(f"Memory index: {'found' if mem_ok else 'MISSING'}")

    free_gb = _check_disk()
    disk_status = "ok" if free_gb > 2 else "LOW SPACE"
    results.append(f"Disk free: {free_gb:.1f} GB ({disk_status})")

    usage = get_usage()
    usage_lines = []
    for provider in ["cerebras", "groq", "gemini"]:
        count = usage.get(provider, 0)
        limit = LIMITS.get(provider, 0)
        usage_lines.append(f"  {provider}: {count}/{limit} today")
    results.append("API usage today:\n" + "\n".join(usage_lines))

    known_issues = _check_known_issues()
    if known_issues:
        results.append("KNOWN ISSUE PATTERNS DETECTED:\n" + "\n".join(f"  - {i}" for i in known_issues))
    else:
        results.append("No known issue patterns detected.")

    all_critical_ok = cerebras_ok and sidecar_ok and mem_ok and not missing_keys
    overall = "All systems operational." if all_critical_ok else "Issues detected — see above."

    summary = "\n".join(results) + f"\n\n{overall}"

    return {"status": "ok", "result": summary, "healthy": all_critical_ok}
