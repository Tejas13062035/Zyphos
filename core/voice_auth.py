import os
import numpy as np
import requests
import time

VOICEPRINT_FILE = os.path.expanduser("~/zyp/state/voiceprint.npy")
from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()
AUDIO_PATH = "/mnt/c/zyphos_sidecar/audio.wav"
THRESHOLD = 0.70  # similarity threshold, tune if needed

def _get_encoder():
    from resemblyzer import VoiceEncoder
    return VoiceEncoder()

def _record(duration=4):
    r = requests.post(f"{SIDECAR_URL}/record", json={"duration": duration})
    time.sleep(duration + 1)

def _get_embedding(encoder, path):
    from resemblyzer import preprocess_wav
    from pathlib import Path
    wav = preprocess_wav(Path(path))
    return encoder.embed_utterance(wav)

def enroll():
    print("VOICE AUTH: Starting enrollment...")
    print("VOICE AUTH: You will record 3 samples. Speak naturally each time.")
    encoder = _get_encoder()
    embeddings = []
    for i in range(3):
        print(f"VOICE AUTH: Sample {i+1}/3 — speak now...")
        _record(duration=4)
        emb = _get_embedding(encoder, AUDIO_PATH)
        embeddings.append(emb)
        print(f"VOICE AUTH: Sample {i+1} recorded.")
        time.sleep(1)
    voiceprint = np.mean(embeddings, axis=0)
    np.save(VOICEPRINT_FILE, voiceprint)
    print("VOICE AUTH: Enrollment complete. Voiceprint saved.")
    return True

def verify(duration=4) -> bool:
    if not os.path.exists(VOICEPRINT_FILE):
        print("VOICE AUTH: No voiceprint found. Run --enroll first.")
        return False
    encoder = _get_encoder()
    stored = np.load(VOICEPRINT_FILE)
    print("VOICE AUTH: Speak now to verify...")
    _record(duration=duration)
    try:
        current = _get_embedding(encoder, AUDIO_PATH)
        similarity = np.dot(stored, current) / (np.linalg.norm(stored) * np.linalg.norm(current))
        print(f"VOICE AUTH: Similarity score: {similarity:.3f}")
        if similarity >= THRESHOLD:
            print("VOICE AUTH: Identity verified.")
            return True
        else:
            print("VOICE AUTH: Identity not verified.")
            return False
    except Exception as e:
        print(f"VOICE AUTH: Error — {e}")
        return False

def is_enrolled() -> bool:
    return os.path.exists(VOICEPRINT_FILE)
