import json
from typing import Any, Dict, Optional

from core.llm import ask

# Prompt used when calling the LLM to act as a critic.
CRITIC_PROMPT = """You are a task critic for an AI agent called Zyphos.
You are given a task description, the tool that was called, the args passed to it, and the result.
Decide if the task succeeded or failed.

Respond ONLY with a JSON object in this format:
{"passed": true, "reason": "short reason"}
or
{"passed": false, "reason": "short reason"}

No explanation outside the JSON."""


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Extract a JSON object from a raw LLM response.

    The function first attempts to parse the whole response as JSON.
    If that fails, it falls back to a simple brace‑matching algorithm that
    returns the first complete JSON object found in the text.

    Returns a dictionary with at least the keys ``passed`` (bool) and ``reason`` (str).
    """
    # 1️⃣ Try to parse the entire response – many LLMs already return clean JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2️⃣ Fallback: locate the first `{` and match braces until the object is closed.
    start = text.find("{")
    if start == -1:
        return {"passed": False, "reason": "no JSON in critic response"}

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # Attempt to parse the candidate substring.
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return {"passed": False, "reason": "json parse failed"}

    # If we exit the loop without closing the braces we have an incomplete object.
    return {"passed": False, "reason": "incomplete json"}


def critique(
    task: str,
    result: str,
    tool: str = "",
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ask the LLM to evaluate whether a tool execution succeeded.

    Parameters
    ----------
    task: str
        The original task description.
    result: str
        The raw result returned by the tool.
    tool: str, optional
        Name of the tool that was invoked. Empty string means unknown.
    args: dict, optional
        Arguments that were passed to the tool. ``None`` is treated as an empty dict.

    Returns
    -------
    dict
        A dictionary containing at least ``passed`` (bool) and ``reason`` (str).
    """
    # Ensure ``args`` is always a JSON‑serialisable object.
    # Unrecoverable environment errors (Ollama unreachable, model missing, etc.)
    # can't be fixed by retrying or replanning — fail immediately, don't waste
    # LLM calls or trigger chaining on something reasoning can't solve.
    if isinstance(result, str) and "LLM_ERROR:" in result:
        return {"passed": False, "reason": result, "unrecoverable": True}
    args_obj: Dict[str, Any] = args if isinstance(args, dict) else {}
    args_str = json.dumps(args_obj)

    prompt = (
        f"Task: {task}\n"
        f"Tool called: {tool if tool else 'unknown'}\n"
        f"Args: {args_str}\n"
        f"Result: {result}"
    )

    # Call the LLM with the critic system prompt.
    response = ask(prompt, system=CRITIC_PROMPT, max_tokens=200)

    # Extract and return the JSON verdict.
    return _extract_json(response)
