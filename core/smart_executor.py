import os
import json
from typing import Union

from tools.sidecar import speak
from plugins.system_stats import run as stats_run
from plugins.joke import run as joke_run
from plugins.security import run as security_run
from plugins.port_scanner import run as port_scan_run
from plugins.whatsapp_bulk import run as wa_bulk_run
from plugins.youtube import run as youtube_run
from plugins.file_organizer import run as organizer_run
from plugins.notes import run as notes_run
from plugins.timer import run as timer_run
from plugins.clipboard import run as clipboard_run
from plugins.weather import run as weather_run
from plugins.calendar import run as calendar_run
from plugins.gmail import run as gmail_run
from plugins.drive import run as drive_run
from core.plugin_loader import load_plugins
from core.critic import critique
from tools.search import search_summary
from tools.vision import look
from core.llm import ask_cerebras, ask_groq
from tools.sidecar import click, type_text, screenshot, scroll, drag, hotkey
from tools.filesystem import read_file, write_file, list_dir, delete_file
from tools.shell import run_shell

def ask(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    result = ask_cerebras(prompt, system, max_tokens)
    if result.startswith("LLM_ERROR"):
        result = ask_groq(prompt, system, max_tokens)
    return result

def _build_system_prompt() -> str:
    """
    Build the system prompt that lists all available tools.
    Dynamically includes any plugins loaded via ``load_plugins``.
    """
    plugin_lines = ""
    for name, plugin in load_plugins().items():
        args_str = ", ".join(f"{k}: {v}" for k, v in plugin["args"].items())
        plugin_lines += f"\n- {name}: {{{args_str}}}  — {plugin['description']}"
    return SYSTEM_PROMPT_BASE + plugin_lines


SYSTEM_PROMPT_BASE = """You are a task execution engine. Given a task description, respond with a JSON object only.
No explanation, no markdown, just raw JSON.

Available tools:
- joke: {} — get a random joke
- open_app: {"app": str}  → opens Windows app (notepad, chrome, calculator, spotify etc). ALWAYS use this for opening apps, never run_shell for Windows apps.
- search <query>  → web search, returns top results
- security: {"action": "password|ip_lookup|dns|whois|breach_check|wifi_info", "target": str}
- port_scanner: {"target": str, "ports": "1-1000"}
- look: {"prompt": str}  — takes a screenshot and describes what's on screen
- system_stats: {"speak": bool}
- speak: {"text": str} — speak text out loud via TTS
- text_to_speech: {"text": str} — alias for speak
- whatsapp_bulk: {"contacts": [str], "message": str}
- timer: {"minutes": float, "seconds": float, "message": str, "block": bool}  → set block=true when next task should wait for timer
- music: {"action": "play|stop", "query": str}  → plays audio via VLC (PREFERRED for playing songs)
- youtube: {"action": "search|playlist", "query": str}  → opens YouTube in browser (use only when user wants to WATCH or BROWSE, not just listen)
- file_organizer: {"path": str}
- notes: {"action": "add|read|list|delete", "note": str, "title": str}
- clipboard: {"action": "get|set", "text": str}
- timer: {"minutes": float, "seconds": float, "message": str}
- weather: {"city": str, "speak": bool}
- calendar: {"action": "list|today|add", "summary": str, "date": "YYYY-MM-DD", "time": "HH:MM"}
- gmail: {"action": "send|read|search", "to": str, "subject": str, "body": str}
- drive: {"action": "list|upload|download|search", "query": str}
- screenshot: {}
- click: {"x": int, "y": int}
- type_text: {"text": str}
- scroll: {"x": int, "y": int, "amount": int}
- drag: {"x1": int, "y1": int, "x2": int, "y2": int}
- hotkey: {"keys": [str]}
- read_file: {"path": str}
- write_file: {"path": str, "content": str}
- list_dir: {"path": str}
- delete_file: {"path": str}
- run_shell: {"command": str}

Respond with exactly: {"tool": "tool_name", "args": {...}}"""


def _run_joke(args, desc=""):
    """
    Retrieve one or more jokes and optionally speak them.
    """
    import re
    import time

    count = args.get("count", 1)
    if count == 1:
        # If the description contains a number, use it as the count
        match = re.search(r'\b(\d+)\b', desc)
        if match:
            count = int(match.group(1))

    category = args.get("category") or "Any"
    jokes = []
    for _ in range(count):
        r = joke_run({"count": 1, "category": category})
        joke_text = r.get("joke", "")
        if joke_text:
            jokes.append(joke_text)
            speak(joke_text)
            time.sleep(2)
    return {"status": "ok", "jokes": jokes, "result": "\n".join(jokes)}


TOOL_MAP = {
    "search": lambda args: {"status": "ok", "result": search_summary(args.get("query", args[0] if isinstance(args, list) else ""))},
    "open_app": lambda args: __import__('requests').post('http://127.0.0.1:5000/open_app', json={"app": args.get("app", "")}).json(),
    "look": lambda args: look(args.get("prompt", "What do you see on this screen?")),
    "system_stats": lambda args: stats_run(args),
    "joke": lambda args: _run_joke(args),
    "screenshot": lambda args: screenshot(),
    "security": lambda args: security_run(args),
    "text_to_speech": lambda args: speak(args.get("text", "")),
    "speak": lambda args: speak(args.get("text", "")),
    "port_scanner": lambda args: port_scan_run(args),
    "whatsapp_bulk": lambda args: wa_bulk_run(args),
    "youtube": lambda args: youtube_run(args),
    "file_organizer": lambda args: organizer_run(args),
    "click": lambda args: click(args["x"], args["y"]),
    "type_text": lambda args: type_text(args["text"]),
    "scroll": lambda args: scroll(args["x"], args["y"], args.get("amount", 3)),
    "clipboard": lambda args: clipboard_run(args),
    "notes": lambda args: notes_run(args),
    "weather": lambda args: weather_run(args),
    "drag": lambda args: drag(args["x1"], args["y1"], args["x2"], args["y2"]),
    "hotkey": lambda args: hotkey(args["keys"]),
    "read_file": lambda args: read_file(args["path"]) if os.path.exists(os.path.expanduser(args["path"])) else {"error": f"skipped: path does not exist: {args['path']}"},
    "timer": lambda args: timer_run(args),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "list_dir": lambda args: list_dir(args["path"]),
    "calendar": lambda args: calendar_run(args),
    "gmail": lambda args: gmail_run(args),
    "drive": lambda args: drive_run(args),
    "delete_file": lambda args: delete_file(args["path"]),
    "run_shell": lambda args: run_shell(args["command"]),
}

# Load plugins and merge them into TOOL_MAP
_plugins = load_plugins()
for _name, _plugin in _plugins.items():
    TOOL_MAP[_name] = _plugin["run"]


def smart_execute(task: Union[dict, str]) -> dict:
    """
    Execute a single task description using the LLM to decide which tool to call.

    ``task`` can be either:
        * a dict with a ``description`` key (the normal case), or
        * a raw string containing the description.

    The function returns the original task dict enriched with ``status`` and ``result``.
    """
    # Normalise ``task`` to a dict with a ``description`` field
    if isinstance(task, str):
        task = {"description": task}
    elif not isinstance(task, dict):
        raise TypeError("task must be a dict or a string")

    desc = task.get("description", "")
    # Tools that require extra verification before execution
    SENSITIVE_TOOLS = ["gmail", "drive", "calendar", "notes", "whatsapp_bulk", "delete_file"]

    response = ask(desc, system=_build_system_prompt(), max_tokens=250)

    try:
        # Extract the first complete JSON object from the LLM response
        start = response.find("{")
        depth = 0
        end = start
        for i, c in enumerate(response[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        clean = response[start:end]
        parsed = json.loads(clean)

        tool = parsed["tool"]
        # Verify identity for sensitive tools
        if tool in SENSITIVE_TOOLS:
            from core.voice_auth import verify, is_enrolled
            if is_enrolled():
                if not verify():
                    task["status"] = "done"
                    task["result"] = {"error": "Voice authentication failed. Access denied."}
                    speak("Sorry, I could not verify your identity. Access denied.")
                    return task

        args = parsed.get("args", {})

        if tool not in TOOL_MAP:
            task["status"] = "done"
            task["result"] = {"error": f"unknown tool: {tool}"}
            return task

        # ``joke`` is handled specially to allow extra speaking logic
        if tool == "joke":
            result = _run_joke(args, desc)
        else:
            result = TOOL_MAP[tool](args)

        task["status"] = "done"
        task["result"] = {
            "result": str(result),
            "tool": tool,
            "args": args
        }

        # Auto‑speak for conversational‑style goals
        speak_triggers = [
            "tell me", "what is", "what are", "read", "who is",
            "show me", "how many", "where is", "when is"
        ]
        original_goal = desc.lower()
        if any(t in original_goal for t in speak_triggers):
            if tool not in ["joke", "wisdom", "speak", "text_to_speech", "type_text", "screenshot", "click", "hotkey", "music"]:
                result_text = ""
                if isinstance(result, dict):
                    result_text = (
                        result.get("summary") or
                        result.get("result") or
                        result.get("description") or
                        str(result)
                    )
                else:
                    result_text = str(result)

                if result_text and len(result_text) > 5:
                    speak(str(result_text)[:1000])  # cap at 1000 chars

    except Exception as e:
        task["status"] = "done"
        task["result"] = {"error": f"smart_execute failed: {e}", "raw": response}

    return task


def smart_execute_with_critique(task: Union[dict, str], max_retries: int = 2) -> dict:
    """
    Execute a task with optional critique/retry logic.

    Returns the final task dict (including ``status`` and ``result``).
    """
    for attempt in range(max_retries + 1):
        result = smart_execute(task)
        inner = result.get("result", {})
        # Build the description for the critique call
        description = task if isinstance(task, str) else task.get("description", "")

        if isinstance(inner, dict):
            critique_result_str = inner.get("result", str(inner))
        else:
            critique_result_str = str(inner)

        # strip large base64/binary payloads before sending to critic
        if len(critique_result_str) > 500:
            critique_result_str = critique_result_str[:500] + "...[truncated for critic]"

        verdict = critique(
            task=description,
            result=critique_result_str,
            tool=inner.get("tool", "") if isinstance(inner, dict) else "",
            args=inner.get("args", {}) if isinstance(inner, dict) else {}
        )

        if verdict.get("passed"):
            if attempt > 0:
                print(f"[CRITIC] Passed on attempt {attempt + 1}.")
            return result

        reason = verdict.get("reason", "unknown")
        print(f"[CRITIC] Attempt {attempt + 1} failed: {reason}")

        if attempt < max_retries:
            print(f"[CRITIC] Retrying ({attempt + 2}/{max_retries + 1})...")
        else:
            print(f"[CRITIC] Max retries reached. Returning last result.")

    return result
