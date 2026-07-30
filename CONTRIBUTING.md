# Contributing to Zyphos

Zyphos is primarily a solo research project, but the plugin system is designed to be easy to extend. If you want to add a tool, fix a bug, or improve the docs, here's how.

---

## Adding a plugin

This is the easiest and most welcome kind of contribution. Drop a `.py` file into `plugins/` — no core code changes, no registration step.

```python
TOOL_NAME = "my_tool"
TOOL_DESCRIPTION = "One sentence describing what this tool does"
TOOL_ARGS = {"param": "type: description"}

def run(args=None):
    # your logic here
    return {"status": "ok", "result": "output"}
```

Zyphos auto-discovers the plugin on next run via `core/plugin_loader.py`, and it becomes available to both:
- the keyword executor (`core/executor.py`)
- the LLM-driven smart executor (`core/smart_executor.py`), whose system prompt is built dynamically from every loaded plugin's `TOOL_DESCRIPTION` and `TOOL_ARGS`

### Plugin guidelines
- Always return a dict with at least a `status` key (`"ok"` or `"error"`).
- Put the human-readable output in a `result` key — that's what gets spoken via TTS and shown to the user.
- Wrap external API calls in `try/except` and return `{"error": str(e)}` on failure instead of letting exceptions crash the executor.
- If your plugin needs an API key, load it via `python-dotenv` from `~/zyp/.env` and add the variable name to `.env.example` (never commit real keys).
- Keep responses reasonably short — long unstructured text sent to TTS reads poorly. Truncate or summarize before returning.
- If your plugin's output will often be spoken, avoid markdown formatting (`**bold**`, `# headers`) in the `result` string, or strip it before returning.

---

## Reporting a bug

Open an issue with:
- The exact goal/command you ran
- What you expected vs. what happened
- Relevant terminal output (redact any API keys or personal info first)

---

## Code style

- Type hints and docstrings on new functions where practical
- Keep functions focused — one plugin, one job
- Match the existing pattern in a file before introducing a new one (e.g. don't add a class-based plugin next to a dozen function-based ones)

---

## What not to touch without discussion

- `core/smart_executor.py` and `core/smart_planner.py` — these are tuned carefully around specific LLM backend quirks (token limits, JSON parsing, reasoning-model behavior). Changes here can have wide-reaching effects.
- `core/daemon.py` and the auto-start/watchdog scripts — these manage process lifecycle and are easy to break in ways that only show up after a reboot.

For anything touching those files, open an issue first to discuss the approach.

---

## Questions

This is a personal project built by [Tejas](https://github.com/Tejas13062035). Feel free to open an issue for questions about the architecture or roadmap.
