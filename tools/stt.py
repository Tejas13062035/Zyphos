import whisper
import requests
import time
import os

SIDECAR_URL = "http://127.0.0.1:5000"
AUDIO_PATH = "/mnt/c/zyphos_sidecar/audio.wav"
MODEL_SIZE = "small"
CONFIDENCE_THRESHOLD = 0.4  # reject transcription below this avg log prob
MAX_RECORD_ATTEMPTS = 3

model = None


def load_model():
    global model
    if model is None:
        print("STT: loading Whisper model...")
        model = whisper.load_model(MODEL_SIZE)
        print("STT: model ready")
    return model


def record(duration=5):
    r = requests.post(f"{SIDECAR_URL}/record", json={"duration": duration})
    if r.json().get("status") != "recording":
        raise RuntimeError("Sidecar record failed")
    print(f"STT: recording for {duration}s...")
    time.sleep(duration + 1)


def transcribe(path=None):
    if path is None:
        path = AUDIO_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"No audio file at {path}")
    m = load_model()
    print("STT: transcribing...")
    result = m.transcribe(path, language="en", fp16=False)
    text = result["text"].strip()

    # calculate average confidence from segments
    segments = result.get("segments", [])
    if segments:
        avg_logprob = sum(s["avg_logprob"] for s in segments) / len(segments)
        # log prob is negative — closer to 0 is more confident
        # convert to 0-1 scale: e^avg_logprob
        import math
        confidence = math.exp(avg_logprob)
    else:
        confidence = 1.0  # no segments = short audio, assume ok

    print(f"STT: heard → '{text}' (confidence: {confidence:.2f})")
    return text, confidence


def listen(duration=5, confirm=True):
    for attempt in range(MAX_RECORD_ATTEMPTS):
        record(duration)
        text, confidence = transcribe()

        if confidence < CONFIDENCE_THRESHOLD:
            print(f"STT: confidence too low ({confidence:.2f} < {CONFIDENCE_THRESHOLD}) — please speak again")
            if attempt < MAX_RECORD_ATTEMPTS - 1:
                continue
            else:
                answer = input(f"STT: max attempts reached. Accept '{text}' anyway? [y/n]: ").strip().lower()
                if answer == "y":
                    return text
                return None

        if confirm:
            answer = input(f"STT heard: '{text}' — execute? [y/n]: ").strip().lower()
            if answer != "y":
                print("STT: cancelled")
                return None

        return text

    return None
