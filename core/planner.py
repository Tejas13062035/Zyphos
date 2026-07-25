"""Simple keyword‑based planner.

The planner parses a textual goal into a list of task dictionaries. Each task
contains an ``id``, a human‑readable ``description``, and placeholder fields
for ``status`` and ``result``. The implementation is deliberately lightweight
and intended for quick prototyping.
"""

import uuid
from typing import Any, Dict, List


def plan(goal: str) -> List[Dict[str, Any]]:
    """Convert a natural‑language goal into a list of task dictionaries.

    The parser looks for a handful of known keywords (e.g., ``click``,
    ``type``, ``screenshot``) and builds corresponding task descriptions.
    Unrecognised words are ignored.

    Args:
        goal: The goal string supplied by the user.

    Returns:
        A list of task dictionaries ready for execution.
    """
    words = goal.lower().split()
    tasks: List[Dict[str, Any]] = []
    i = 0
    while i < len(words):
        word = words[i]

        if word == "click" and i + 2 < len(words):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"click {words[i+1]} {words[i+2]}",
                    "status": "pending",
                    "result": None,
                }
            )
            i += 3
            continue

        if word == "type" and i + 1 < len(words):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"type {' '.join(words[i+1:])}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "screenshot":
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "screenshot",
                    "status": "pending",
                    "result": None,
                }
            )
            i += 1
            continue

        if word == "scroll" and i + 2 < len(words):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"scroll {words[i+1]} {words[i+2]}",
                    "status": "pending",
                    "result": None,
                }
            )
            i += 3
            continue

        if word == "drag" and i + 4 < len(words):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"drag {words[i+1]} {words[i+2]} {words[i+3]} {words[i+4]}",
                    "status": "pending",
                    "result": None,
                }
            )
            i += 5
            continue

        if word == "hotkey":
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"hotkey {' '.join(words[i+1:])}",
                    "status": "pending",
                    "result": None,
                }
            )
            break  # Fixed infinite loop – stop after adding the hotkey task

        if word == "search" and i + 1 < len(words):
            query = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"search {query}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "play" and i + 1 < len(words):
            query = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"play {query}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "stop":
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "stop music",
                    "status": "pending",
                    "result": None,
                }
            )
            i += 1
            continue

        if word == "open":
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"open {' '.join(words[i+1:])}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word in ("network", "scan"):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "network scan",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word in ("speak", "say"):
            text = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"speak {text}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "write" and i + 1 < len(words):
            text = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"type {text}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word in ("email", "gmail"):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"email {' '.join(words[i+1:])}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "drive":
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"drive {' '.join(words[i+1:])}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "read" and i + 1 < len(words) and "email" in words[i+1:]:
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "email read",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "remember" and i + 1 < len(words):
            fact = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"remember {fact}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "forget" and i + 1 < len(words):
            key = " ".join(words[i+1:])
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": f"forget {key}",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word == "what" and "know" in words and "me" in words:
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "what do you know about me",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word in ("calendar", "schedule", "events"):
            tasks.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "description": "calendar list",
                    "status": "pending",
                    "result": None,
                }
            )
            break

        if word in ("joke", "jokes"):
            count = 1
            for p in words:
                if p.isdigit():
                    count = int(p)
                    break
            for _ in range(count):
                tasks.append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "description": "joke",
                        "status": "pending",
                        "result": None,
                    }
                )
            i += len(words)  # consume rest
            break

        # If none of the above matched, move to the next word.
        i += 1

    return tasks
