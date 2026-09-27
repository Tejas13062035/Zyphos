import os
import base64
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_VISION_MODEL = "qwen3.5:9b"
OLLAMA_VISION_FALLBACK = "qwen3-vl:8b-instruct-q4_K_M"


def _ask_ollama_vision(model: str, image_data: str, prompt: str, keep_alive: str, num_ctx: int = 4096) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_data]
                }
            ],
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_predict": 500, "num_ctx": num_ctx}
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def analyze_screenshot(image_path: str, prompt: str = "What do you see on this screen?") -> str:
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    try:
        return _ask_ollama_vision(OLLAMA_VISION_MODEL, image_data, prompt, keep_alive="30m", num_ctx=4096)
    except Exception:
        # local-only fallback — no cloud, ever. Smaller context so it fits fully on GPU.
        return _ask_ollama_vision(OLLAMA_VISION_FALLBACK, image_data, prompt, keep_alive="1m", num_ctx=2048)


def look(prompt: str = "What do you see on this screen?") -> dict:
    from tools.sidecar import screenshot
    result = screenshot()
    image_b64 = result.get("image", "")
    if not image_b64:
        return {"error": "no screenshot"}
    tmp_path = "/tmp/zyp_vision.png"
    with open(tmp_path, "wb") as f:
        f.write(base64.b64decode(image_b64))
    description = analyze_screenshot(tmp_path, prompt)
    return {"status": "ok", "description": description}
