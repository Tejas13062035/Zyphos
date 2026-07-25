"""Goal‑chaining utilities.

The *chainer* asks a language model whether a goal is complete or whether an
additional action is required. It then executes the suggested action using the
smart executor and repeats the process up to ``max_steps`` times.
"""

import json
from typing import Any, Dict, List

from core.llm import ask
from core.smart_executor import smart_execute_with_critique

CHAINER_PROMPT = """You are a goal chaining engine for an AI agent called Zyphos.
You are given the original goal and the result of the last action taken.
Decide if the goal is fully complete, or if another action is needed.

Respond ONLY with a JSON object in one of these two formats:

If done:
{"done": true, "reason": "short reason"}

If another action is needed:
{"done": false, "next": "description of next action to take"}

No explanation outside the JSON."""


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from a string.

    The function looks for the opening ``{`` character and then parses until the
    matching closing ``}``. If parsing fails, a fallback dictionary indicating
    completion is returned.

    Args:
        text: The raw LLM response.

    Returns:
        A dictionary representing the parsed JSON.
    """
    start = text.find("{")
    if start == -1:
        return {"done": True, "reason": "no JSON in chainer response"}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0:
            try:
                return json.loads(text[start:i + 1])
            except json.JSONDecodeError:
                return {"done": True, "reason": "json parse failed"}
    return {"done": True, "reason": "incomplete json"}


def chain(original_goal: str, last_result: str, max_steps: int = 5) -> List[Dict[str, Any]]:
    """Run a goal‑chaining loop.

    The loop asks the LLM whether the original goal is complete. If not, it
    executes the suggested next action and repeats. The function returns a list
    of all steps taken.

    Args:
        original_goal: The initial goal description.
        last_result: Result of the previous action (may be empty on first call).
        max_steps: Maximum number of chaining iterations.

    Returns:
        A list of dictionaries, each containing ``action`` and ``result`` keys.
    """
    steps: List[Dict[str, Any]] = []
    current_action = original_goal
    current_result = last_result

    for step in range(max_steps):
        prompt = (
            f"Original goal: {original_goal}\n"
            f"Last action: {current_action}\n"
            f"Last result: {current_result}"
        )
        response = ask(prompt, system=CHAINER_PROMPT, max_tokens=200)
        verdict = _extract_json(response)

        if verdict.get("done"):
            reason = verdict.get("reason", "complete")
            print(f"[CHAIN] Done after {step + 1} step(s): {reason}")
            break

        next_action = verdict.get("next", "")
        if not next_action:
            print("[CHAIN] No next action returned, stopping.")
            break

        print(f"[CHAIN] Step {step + 2}: {next_action}")
        task = {"description": next_action}
        result = smart_execute_with_critique(task)
        steps.append(
            {"action": next_action, "result": result.get("result", "")}
        )
        current_action = next_action
        current_result = result.get("result", "")

    return steps
