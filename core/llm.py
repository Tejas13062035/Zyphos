import os
import re
import requests
from core.quota_tracker import record_call

# -----------------------------------------------------------
# LOCAL MODEL ROUTING (Ollama, HP Omen - Ultra 7 255H / RTX 5050 8GB)
# Task-specific models, local-first. Falls back to cloud (Cerebras)
# only if Ollama is unreachable or the local call errors out.
# -----------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"   # native endpoint — needed for keep_alive control

MODEL_TOOL = "granite4.1:8b-q4_K_M"       # plugin / tool-calling routing
MODEL_DEFAULT = "qwen3.5:9b"              # general, reasoning, chitchat, vision — always-loaded default
MODEL_CODE = "qwen2.5-coder:7b-instruct-q4_K_M"  # code generation / explanation

PROFILE_FILE = os.path.expanduser("~/zyp/state/user_profile.txt")
PERSONALITY_FILE = os.path.expanduser("~/zyp/state/personality.json")


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
                 strip_think: bool = False, keep_alive: str = "5m"):
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
    """Tool-calling / plugin routing. Fast, local, granite4.1. Short keep_alive
    so it evicts fast and qwen3.5 reclaims VRAM."""
    record_call("ollama_tool")
    try:
        return _ask_ollama(MODEL_TOOL, prompt, system, max_tokens, keep_alive="1m")
    except Exception:
        return ask_cerebras(prompt, system, max_tokens)


def ask_reasoning(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Complex multi-step planning / reasoning. Local qwen3.5:9b (default model,
    kept warm)."""
    record_call("ollama_reasoning")
    try:
        return _ask_ollama(MODEL_DEFAULT, prompt, system, max_tokens,
                            strip_think=True, keep_alive="30m")
    except Exception:
        return ask_cerebras(prompt, system, max_tokens)


def ask_chat(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Casual conversation, quotes, briefing chatter. Local qwen3.5:9b (default,
    kept warm)."""
    record_call("ollama_chat")
    try:
        return _ask_ollama(MODEL_DEFAULT, prompt, system, max_tokens, keep_alive="30m")
    except Exception:
        return ask_cerebras(prompt, system, max_tokens)


def ask_vision(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Vision / OCR. Local qwen3.5:9b (default, multimodal, kept warm)."""
    record_call("ollama_vision")
    try:
        return _ask_ollama(MODEL_DEFAULT, prompt, system, max_tokens, keep_alive="30m")
    except Exception:
        return ask_cerebras(prompt, system, max_tokens)


def ask_code(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Code generation / explanation. Local qwen2.5-coder. Short keep_alive
    so it evicts fast and qwen3.5 reclaims VRAM."""
    record_call("ollama_code")
    try:
        return _ask_ollama(MODEL_CODE, prompt, system, max_tokens, keep_alive="1m")
    except Exception:
        return ask_cerebras(prompt, system, max_tokens)


def ask_cerebras(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Cloud fallback when local Ollama is unreachable or errors out."""
    record_call("cerebras")
    try:
        import os
        from cerebras.cloud.sdk import Cerebras
        client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="gpt-oss",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM_ERROR: {e}"


def ask(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    """Default entry point. Local-first via qwen3.5:9b (always-loaded default
    model), cloud fallback if Ollama's down."""
    profile = load_profile()
    full_system = f"USER PROFILE:\n{profile}\n\n{system}" if profile else system
    return ask_chat(prompt, full_system, max_tokens)





