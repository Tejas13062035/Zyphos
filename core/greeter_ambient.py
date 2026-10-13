import random
import time

from core.llm import ask_chat as _ask_default
from tools import sidecar as _sidecar
from tools.sidecar import speak_fast as speak

# qwen3.5:9b can't stay loaded next to granite on 8 GB of VRAM, so a greeting on it cost ~24 s per cold start.
# The default model stays loaded, and this prompt keeps the tone natural.
GREETER_SYSTEM = (
    "You are Zyphos, a warm, friendly voice assistant in the user's home. "
    "Speak naturally, like a person greeting someone at the door. Never mention being an AI, "
    "a digital entity, or a program. Reply with only the words to be spoken: no quotes, no emojis."
)


def ask_chat(prompt, max_tokens=60):
    return _ask_default(prompt, system=GREETER_SYSTEM, max_tokens=max_tokens)


# ---- personal greetings ---------------------------------------------------------------------------
# Keyed by the LOWERCASE enrolled name. These lines are spoken as written, with no LLM call, so there is
# no model-loading delay. One is picked at random for the time of day, never the same one twice in a row.
# Keep each line to one or two sentences: the speech starts as soon as the first sentence is ready.
# To give someone else their own greeting, add another entry with their lowercase name.
PERSONAL_GREETINGS = {
    "tejas": {
        "morning": [
            "Good morning, sir. Systems are up, and so are you.",
            "Morning, Boss. Fresh day, clean slate. What are we building?",
            "Rise and shine, Boss. Let's make today count.",
            "Good morning, sir. All services are running. What do you want to work on today, sir.",
            "Morning, sir. Coffee first, then conquer the world.",
        ],
        "afternoon": [
            "Good afternoon, sir. Hope the morning treated you well.",
            "Afternoon, sir. Stay sharp, the day is still young.",
            "Welcome back, sir. Shall we pick up where we left off?",
            "Good Afternoon, sir. How is the build going?",
            "Good afternoon, sir. A quick water break, then back to it?",
        ],
        "evening": [
            "Good evening, sir. How did today go?",
            "Good Evening, sir. What did we get done today?",
            "Welcome back, sir. Wind down, but keep thinking.",
            "Good evening sir. Everything is running smoothly. How was your day?",
            "Good Evening, sir. Anything you want to wrap up before tonight?",
        ],
        "night": [
            "It is late, sir. The code will still be here tomorrow. Get some rest",
            "Burning the midnight oil, sir? Don't forget to sleep, it will affect your performance negatively sir.",
            "Welcome back, sir. Remember, A little rest makes tomorrow's code better. Have a good night sir",
            "Night shift, sir? Hydrate, and wrap up soon. Sleep is also important sir",
            "Late night, sir. Let me keep watch while you finish up.",
        ],
    },
}
# True = let the LLM write the personal greeting instead (varies more, but is slower and needs the model loaded).
# If the LLM fails, the lines above are used.
PERSONAL_USE_LLM = False
PERSONAL_STYLE = (
    "Greet {name} the way a loyal, witty assistant greets the person who built it, as he walks in this {period}. "
    "Greet {name} the way J.A.R.V.I.S. from Marvel Cinematic Universe (M.C.U.) greets Ironman when he returns"
    "Call him 'sir'. Keep it short, natural, spoken out loud: one or two sentences."
)
_last_personal = {}


def _period() -> str:
    """Time of day for personal greetings: morning 5-11, afternoon 12-16, evening 17-21, night 22-4."""
    hour = time.localtime().tm_hour
    if hour >= 22 or hour < 5:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def _personal_greeting(name: str):
    """A greeting just for this person, or None if they have none."""
    by_period = PERSONAL_GREETINGS.get((name or "").strip().lower())
    if not by_period:
        return None
    period = _period()
    if PERSONAL_USE_LLM:
        text = ask_chat(PERSONAL_STYLE.format(name=name, period=period), max_tokens=60)
        if text and not text.startswith("LLM_ERROR"):
            return text
    lines = by_period.get(period) or [l for group in by_period.values() for l in group]
    last = _last_personal.get(name)
    choices = [l for l in lines if l != last] or lines
    pick = random.choice(choices)
    _last_personal[name] = pick
    return pick


def _time_of_day() -> str:
    hour = time.localtime().tm_hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


def generate_greeting(watch_result: dict) -> str:
    """Takes the dict from the face check and produces the greeting text. People with a personal greeting
    get it straight away; everyone else gets one written by the LLM (a pure text task, no vision)."""
    status = watch_result["status"]
    tod = _time_of_day()

    if status == "known":
        category = watch_result.get("category", "known")
        name = watch_result["name"]

        personal = _personal_greeting(name)
        if personal:
            return personal

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
    """Generate and speak the appropriate greeting for a face-check result."""
    t0 = time.time()
    text = generate_greeting(watch_result)
    t_text = time.time() - t0
    if not text or text.startswith("LLM_ERROR"):          # Ollama down: never read the error aloud
        status, name = watch_result.get("status"), watch_result.get("name")
        if status == "known" and name:
            text = f"Welcome back, {name}. How's your day going? Hope you are having a wonderfull day."
        elif status == "unknown":
            text = "Hello there, hope you are having a great day. By The Way, I don't think we've met before, can you tell me your name?"
        else:
            text = "Hello."
    t1 = time.time()
    speak(text)
    first = getattr(_sidecar, "speak_timing", {}).get("first_audio_s")
    print(f"[greeter] text {t_text:.1f}s | first audio {first}s after that | whole utterance {time.time() - t1:.1f}s"
          f" | {text!r}", flush=True)
    return text
