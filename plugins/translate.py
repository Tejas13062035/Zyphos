import requests
from core.llm import ask_cerebras

TOOL_NAME = "translate"
TOOL_DESCRIPTION = "translates text to another language"
TOOL_ARGS = {"text": "str", "target_lang": "str (e.g. 'Spanish', 'French', 'Hindi', 'German')"}

def _speak(text):
    try:
        requests.post("http://127.0.0.1:5000/speak", json={"text": text}, timeout=5)
    except Exception:
        pass

def run(args: dict) -> dict:
    text = args.get("text", "").strip()
    target_lang = args.get("target_lang", "English").strip()

    if not text:
        return {"status": "error", "result": "no text provided"}

    prompt = f"Translate this text to {target_lang}. Respond with ONLY the translation, nothing else:\n\n{text}"

    try:
        result = ask_cerebras(prompt, system="You are a precise translator. Respond only with the translation, no explanations.", max_tokens=300)

        if result.startswith("LLM_ERROR"):
            return {"status": "error", "result": f"translation failed: {result}"}

        _speak(result.strip())
        return {"status": "ok", "result": result.strip()}
    except Exception as e:
        return {"status": "error", "result": f"translate failed: {e}"}
