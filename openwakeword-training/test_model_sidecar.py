#!/usr/bin/env python3
"""Test a trained OpenWakeWord model via the Windows sidecar (no local mic in WSL).
Records short clips repeatedly, runs the model over 80ms windows within each."""
import sys
import time
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import requests
from openwakeword.model import Model

sys.path.insert(0, str(Path.home() / "zyp"))
from core.sidecar_url import get_sidecar_url

SIDECAR_URL = get_sidecar_url()
WIN_PATH = r"C:\zyphos_sidecar\chunk.wav"
WSL_PATH = Path("/mnt/c/zyphos_sidecar/chunk.wav")
CHUNK = 1280  # 80ms at 16kHz, what OpenWakeWord expects per prediction
CLIP_DURATION = 4  # seconds per recording round


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    print("Loading model...")
    start = time.time()
    oww_model = Model(wakeword_model_paths=[args.model])
    print(f"Model loaded in {time.time() - start:.2f}s")

    print(f"\nSay the wake word after each 'Recording...'. Threshold: {args.threshold}")
    print("Ctrl+C to stop\n")

    try:
        while True:
            WSL_PATH.unlink(missing_ok=True)
            print("Recording...", end=" ", flush=True)
            requests.post(f"{SIDECAR_URL}/record_chunk", json={"duration": CLIP_DURATION})

            deadline = time.time() + CLIP_DURATION + 8
            while time.time() < deadline and not WSL_PATH.exists():
                time.sleep(0.2)
            time.sleep(0.3)

            if not WSL_PATH.exists():
                print("no audio captured, retrying")
                continue

            audio, sr = sf.read(WSL_PATH, dtype="int16")
            print(f"got {len(audio)/sr:.1f}s, analyzing...")

            oww_model.reset()
            detected_any = False
            for i in range(0, len(audio) - CHUNK, CHUNK):
                window = audio[i:i + CHUNK]
                prediction = oww_model.predict(window)
                for model_name, score in prediction.items():
                    if score > args.threshold:
                        t = i / sr
                        print(f"  DETECTED at {t:.2f}s: {model_name} (score: {score:.3f})")
                        detected_any = True

            if not detected_any:
                print("  (no detection in this clip)")

    except KeyboardInterrupt:
        print("\nStopping...")


if __name__ == "__main__":
    main()
