#!/usr/bin/env python3
"""Record wake word samples via the Windows sidecar (WSL can't reach the mic).
Output matches record_samples.py: 16kHz mono 16-bit WAV, 2s, my_real_samples/."""
import sys
import time
import shutil
from pathlib import Path

import requests

sys.path.insert(0, str(Path.home() / "zyp"))
from core.sidecar_url import get_sidecar_url

SIDECAR_URL = get_sidecar_url()
WIN_PATH = r"C:\zyphos_sidecar\chunk.wav"
WSL_PATH = Path("/mnt/c/zyphos_sidecar/chunk.wav")
DURATION = 2
WAKE_WORD = "zyphos"
START_LAG = 0.6   # seconds for recorder.py to start up; tune if the word still clips

output_dir = Path("my_real_samples")
output_dir.mkdir(exist_ok=True)
count = len(list(output_dir.glob("*.wav")))

print(f'Recording samples of "{WAKE_WORD}". Existing: {count}')
print("Vary tone, speed, distance. Also say it inside natural sentences.")
print("ENTER = record, q + ENTER = quit\n")

while True:
    if input(f"[Sample {count + 1}] ENTER to record (q to quit): ").lower() == "q":
        break
    WSL_PATH.unlink(missing_ok=True)
    print("Get ready...", end=" ", flush=True)

    requests.post(f"{SIDECAR_URL}/record_chunk",
                  json={"duration": DURATION, "path": WIN_PATH})
    time.sleep(START_LAG)            # wait for the recorder to actually start
    requests.post(f"{SIDECAR_URL}/beep")
    print("SAY IT NOW (after the beep)")

    requests.post(f"{SIDECAR_URL}/record_chunk",
                  json={"duration": DURATION, "path": WIN_PATH})
    deadline = time.time() + 12
    while time.time() < deadline and not WSL_PATH.exists():
        time.sleep(0.25)
    time.sleep(0.5)  # let the write finish flushing

    if not WSL_PATH.exists():
        print("No file recorded, try again.\n")
        continue

    while (output_dir / f"{WAKE_WORD}_{count + 1:04d}.wav").exists():
        count += 1

    dest = output_dir / f"{WAKE_WORD}_{count + 1:04d}.wav"
    shutil.copy(WSL_PATH, dest)
    print(f"Saved: {dest}\n")
    count += 1

print(f"\nDone. {count} total samples in {output_dir}/")
