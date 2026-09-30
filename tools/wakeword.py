import time
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import requests
from openwakeword.model import Model

from core.sidecar_url import get_sidecar_url

WIN_PATH = r"C:\zyphos_sidecar\chunk.wav"
WSL_PATH = Path("/mnt/c/zyphos_sidecar/chunk.wav")
MODEL_PATH = str(Path.home() / "zyp" / "state" / "models" / "zyphos.onnx")
CHUNK = 1280  # 80ms at 16kHz
CLIP_DURATION = 3
THRESHOLD = 0.5
COOLDOWN_SECONDS = 3  # avoid re-triggering repeatedly on one long utterance

_model = None


def _get_model():
    global _model
    if _model is None:
        print("WAKEWORD: loading zyphos.onnx...")
        _model = Model(wakeword_model_paths=[MODEL_PATH])
        print("WAKEWORD: ready")
    return _model


def _record_clip():
    WSL_PATH.unlink(missing_ok=True)
    sidecar_url = get_sidecar_url()
    requests.post(f"{sidecar_url}/record_chunk", json={"duration": CLIP_DURATION})

    deadline = time.time() + CLIP_DURATION + 8
    while time.time() < deadline and not WSL_PATH.exists():
        time.sleep(0.15)
    time.sleep(0.3)

    if not WSL_PATH.exists():
        return None
    audio, sr = sf.read(WSL_PATH, dtype="int16")
    return audio


def listen_loop(on_wake):
    model = _get_model()
    print(f"WAKEWORD: listening for 'zyphos' (threshold {THRESHOLD})...")
    last_trigger = 0

    while True:
        audio = _record_clip()
        if audio is None:
            continue

        model.reset()
        triggered = False
        for i in range(0, len(audio) - CHUNK, CHUNK):
            prediction = model.predict(audio[i:i + CHUNK])
            for name, score in prediction.items():
                if score > THRESHOLD:
                    triggered = True

        if triggered and (time.time() - last_trigger) > COOLDOWN_SECONDS:
            print("WAKEWORD: triggered")
            last_trigger = time.time()
            on_wake()


def start(on_wake):
    t = threading.Thread(target=listen_loop, args=(on_wake,), daemon=True)
    t.start()
    return t
