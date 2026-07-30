import os
import requests
from core.quota_tracker import record_call

# -----------------------------------------------------------
# BACKEND SWITCH
# Set ZYPHOS_BACKEND=llama in your shell or .env to use
# Llama 3.1 8B on the main machine.
# Default: phi (current machine, LM Studio)
# -----------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "hermes3:3b"

# Main machine: change OLLAMA_MODEL to "qwen2.5:7b" when ready

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

def ask(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    profile = load_profile()
    full_system = f"USER PROFILE:\n{profile}\n\n{system}" if profile else system
    return ask_cerebras(prompt, full_system, max_tokens)

def ask_groq(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    record_call("grok")
    try:
        import os
        from groq import Groq
        from dotenv import load_dotenv
        load_dotenv(os.path.expanduser("~/zyp/.env"))
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM_ERROR: {e}"

def ask_gemini(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    record_call("gemini")
    try:
        from google import genai
        from google.genai import types
        from dotenv import load_dotenv
        load_dotenv(os.path.expanduser("~/zyp/.env"))
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            max_output_tokens=max_tokens
        )
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        return f"LLM_ERROR: {e}"

def ask_cerebras(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    record_call("cerebras")
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.expanduser("~/zyp/.env"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        r = requests.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('CEREBRAS_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-oss-120b",
                "messages": messages,
                "max_tokens": max_tokens,
                "reasoning_effort": "low"  # minimize reasoning tokens for short/simple prompts
            },
            timeout=30
        )
        data = r.json()
        message = data["choices"][0]["message"]
        content = message.get("content", "")
        # some reasoning models put the real answer in 'reasoning' if content is empty/cut off
        if not content or not content.strip():
            content = message.get("reasoning", "")
        if not content:
            return f"LLM_ERROR: empty content, raw: {str(data)[:200]}"
        return content.strip()
    except Exception as e:
        return f"LLM_ERROR: {e}, raw: {r.text[:200] if 'r' in dir() else ''}"
