import whisper
import requests
import time
import os
import threading

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()
CHUNK_PATH = "/mnt/c/zyphos_sidecar/chunk.wav"
WAKE_WORDS = ["zyphos", "arise", "zyph", "zyfos", "ziphos", "syphos", "wake up"]
CHUNK_DURATION = 2

model = None

def load_model():
    global model
    if model is None:
        print("WAKEWORD: loading Whisper model...")
        model = whisper.load_model("base")
        print("WAKEWORD: ready")
    return model

def record_chunk():
    requests.post(f"{SIDECAR_URL}/record_chunk", json={"duration": CHUNK_DURATION})
    time.sleep(CHUNK_DURATION + 0.5)

def transcribe_chunk():
    if not os.path.exists(CHUNK_PATH):
        return ""
    try:
        m = load_model()
        result = m.transcribe(CHUNK_PATH, language="en", fp16=False)
        return result["text"].strip().lower()
    except Exception:
        return ""

def detected(text):
    return any(w in text for w in WAKE_WORDS)

def listen_loop(on_wake):
    print(f"WAKEWORD: listening for {WAKE_WORDS}...")
    while True:
        record_chunk()
        text = transcribe_chunk()
        if text and len(text) > 3:
            print(f"WAKEWORD: heard → {text}")
        if detected(text):
            print("WAKEWORD: triggered")
            on_wake()

def start(on_wake):
    t = threading.Thread(target=listen_loop, args=(on_wake,), daemon=True)
    t.start()
    return t
