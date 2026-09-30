import os
import re
import requests
from core.quota_tracker import record_call

# -----------------------------------------------------------
# LOCAL MODEL ROUTING (Ollama, HP Omen - Ultra 7 255H / RTX 5050 8GB)
# Task-specific models, local-first, local-only. No cloud fallback.
#
# granite4.1 is the default, kept warm long — it's the tool-calling model
# and every CLI/voice goal routes through smart_execute() -> ask_tool(),
# so it's the actual hot path, not qwen3.5. qwen3.5 stays available for
# reasoning, vision, and code-adjacent quality, and is used explicitly
# and directly (not via ask_chat) anywhere warm, natural tone genuinely
# matters, like the ambient-awareness greeting flow — granite tends to
# break character with "as a digital entity..." caveats that don't fit
# a greeting.
# -----------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"   # native endpoint — needed for keep_alive control

MODEL_DEFAULT = "granite4.1:8b-q4_K_M"      # tool-calling + general chat — always-loaded default
MODEL_REASONING = "qwen3.5:9b"              # complex reasoning, vision, and warm/natural tone on demand
MODEL_CODE = "qwen2.5-coder:7b-instruct-q4_K_M"  # code generation / explanation

PROFILE_FILE = os.path.expanduser("~/zyp/state/user_profile.txt")
PERSONALITY_FILE = os.path.expanduser("~/zyp/state/personality.json")

LOCAL_UNAVAILABLE = "LLM_ERROR: local Ollama unavailable, no cloud fallback configured"


def load_profile():
    lines = []
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE) as f:
            lines.append(f.read().strip())
    if os.path.exists(PERSONALITY_FILE):
        import json
        with open(PERSONALITY_FILE) as f:
            data = json.load(f)
        for k, v in data.items():
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _strip_think_tags(text: str) -> str:
    """Some models wrap chain-of-thought in <think>...</think> before the
    real answer. Strip it so downstream JSON parsing / TTS doesn't choke on it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _ask_ollama(model: str, prompt: str, system: str, max_tokens: int,
                 strip_think: bool = False, keep_alive: str = "5m", think: bool = False):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "think": think,
            "options": {"num_predict": max_tokens},
        },
        timeout=120
    )
    r.raise_for_status()
    content = r.json()["message"]["content"]
    if strip_think:
        content = _strip_think_tags(content)
    return content.strip()


def ask_tool(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Tool-calling / plugin routing. Local, granite4.1. This is the real hot
    path — every CLI goal and voice command routes through here — so it's
    kept warm long."""
    record_call("ollama_tool")
    try:
        return _ask_ollama(MODEL_DEFAULT, prompt, system, max_tokens, keep_alive="30m")
    except Exception:
        return LOCAL_UNAVAILABLE


def ask_reasoning(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Complex multi-step planning / reasoning. Local qwen3.5:9b, swapped in
    on demand."""
    record_call("ollama_reasoning")
    try:
        return _ask_ollama(MODEL_REASONING, prompt, system, max_tokens,
                            strip_think=True, keep_alive="5m")
    except Exception:
        return LOCAL_UNAVAILABLE


def ask_chat(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Casual conversation, quotes, briefing chatter. Local granite4.1 (default,
    kept warm)."""
    record_call("ollama_chat")
    try:
        return _ask_ollama(MODEL_DEFAULT, prompt, system, max_tokens, keep_alive="30m")
    except Exception:
        return LOCAL_UNAVAILABLE


def ask_warm_chat(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Warm, natural conversational tone specifically — qwen3.5, swapped in
    on demand. Use this (not ask_chat) anywhere tone matters and granite's
    tendency to caveat 'as a digital entity...' would feel wrong, e.g. the
    ambient-awareness greeting flow."""
    record_call("ollama_warm_chat")
    try:
        return _ask_ollama(MODEL_REASONING, prompt, system, max_tokens, keep_alive="5m", think=False)
    except Exception:
        return LOCAL_UNAVAILABLE


def ask_vision(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Vision / OCR. Local qwen3.5:9b (multimodal), swapped in on demand.
    Thinking disabled — same reasoning-overhead problem as chat."""
    record_call("ollama_vision")
    try:
        return _ask_ollama(MODEL_REASONING, prompt, system, max_tokens, keep_alive="5m", think=False)
    except Exception:
        return LOCAL_UNAVAILABLE


def ask_code(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Code generation / explanation. Local qwen2.5-coder, swapped in on demand."""
    record_call("ollama_code")
    try:
        return _ask_ollama(MODEL_CODE, prompt, system, max_tokens, keep_alive="1m")
    except Exception:
        return LOCAL_UNAVAILABLE


def ask(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    """Default entry point. Local-only via granite4.1 (always-loaded default model)."""
    profile = load_profile()
    full_system = f"USER PROFILE:\n{profile}\n\n{system}" if profile else system
    return ask_chat(prompt, full_system, max_tokens)
