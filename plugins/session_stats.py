import os
import json
from collections import Counter
from datetime import datetime, timedelta

TOOL_NAME = "session_stats"
TOOL_DESCRIPTION = "Show usage statistics — goals run today, most-used plugins, memory size"
TOOL_ARGS = {"period": "str: 'today', 'week', or 'all' (default today)"}

MEMORY_JSON = os.path.expanduser("~/zyp/state/memory.json")

def _load_memory():
    if not os.path.exists(MEMORY_JSON):
        return []
    try:
        with open(MEMORY_JSON) as f:
            return json.load(f)
    except Exception:
        return []

def run(args=None):
    period = args.get("period", "today") if args else "today"
    entries = _load_memory()

    if not entries:
        return {"status": "ok", "result": "No memory entries found yet."}

    now = datetime.now()
    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    else:
        cutoff = None

    filtered = []
    for e in entries:
        ts = e.get("timestamp") or e.get("date")
        if not ts:
            filtered.append(e)
            continue
        try:
            entry_time = datetime.fromisoformat(ts)
        except Exception:
            filtered.append(e)
            continue
        if cutoff is None or entry_time >= cutoff:
            filtered.append(e)

    total_goals = len(filtered)
    import ast
    from core.tool_usage_log import read_usage
    usage_entries = read_usage()

    tool_counter = Counter()
    for u in usage_entries:
        ts = u.get("timestamp", "")
        try:
            entry_time = datetime.fromisoformat(ts)
        except Exception:
            continue
        if cutoff is None or entry_time >= cutoff:
            tool_counter[u["tool"]] += 1

    total_memory = len(entries)
    memory_size_mb = os.path.getsize(MEMORY_JSON) / (1024 * 1024) if os.path.exists(MEMORY_JSON) else 0

    top_tools = tool_counter.most_common(5)
    top_tools_str = ", ".join(f"{t} ({c})" for t, c in top_tools) if top_tools else "no tool data recorded"

    result = (
        f"Goals run ({period}): {total_goals}. "
        f"Most used tools: {top_tools_str}. "
        f"Total memory entries (all time): {total_memory}. "
        f"Memory file size: {memory_size_mb:.2f} MB."
    )

    return {
        "status": "ok",
        "result": result,
        "total_goals": total_goals,
        "top_tools": top_tools,
        "total_memory": total_memory
    }
