import time
from core.llm import ask_warm_chat as ask_chat
from tools.sidecar import speak


def _time_of_day() -> str:
    hour = time.localtime().tm_hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


def generate_greeting(watch_result: dict) -> str:
    """Takes the dict from watch_until_resolved() and produces the actual
    greeting text via qwen3.5 (ask_chat) — no vision model involved here,
    this is a pure text task."""
    status = watch_result["status"]
    tod = _time_of_day()

    if status == "known":
        category = watch_result.get("category", "known")
        name = watch_result["name"]

        if category == "close":
            prompt = (
                f"Greet {name} warmly as they walk into the room this {tod}. "
                f"Also ask how their day has been so far. Keep it short, natural, "
                f"spoken out loud — one or two sentences."
            )
        else:
            prompt = (
                f"Greet {name} normally as they walk into the room this {tod}. "
                f"Keep it short, natural, spoken out loud — one sentence."
            )
        return ask_chat(prompt, max_tokens=60)

    elif status == "unknown":
        prompt = (
            f"Greet someone you don't recognize who just walked into the room "
            f"this {tod}, then ask their name. Keep it short, friendly, natural, "
            f"spoken out loud — one or two sentences."
        )
        return ask_chat(prompt, max_tokens=60)

    else:  # "gave_up" — no face ever resolved
        prompt = (
            f"Say a brief, casual good {tod} greeting to whoever's in the room, "
            f"without addressing anyone by name since you couldn't get a clear look. "
            f"One short sentence."
        )
        return ask_chat(prompt, max_tokens=40)


def greet(watch_result: dict):
    """Generate and speak the appropriate greeting for a watch_until_resolved() result."""
    text = generate_greeting(watch_result)
    speak(text)
    return text

