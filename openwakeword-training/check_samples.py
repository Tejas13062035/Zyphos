import sys
import wave
import shutil
from pathlib import Path

import numpy as np

SAMPLES = Path("my_real_samples")
REJECT = Path("my_real_samples_rejected")
FRAME = 320       # 20 ms at 16 kHz
EDGE_FRAMES = 5   # first/last 100 ms


def analyze(path):
    with wave.open(str(path), "rb") as wf:
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)
    if len(data) < FRAME * 10:
        return ["too short"]

    n = len(data) // FRAME
    rms = np.sqrt((data[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1))

    if np.abs(data).max() < 1500:
        return ["silent / too quiet"]

    problems = []
    if (np.abs(data) >= 32000).mean() > 0.01:
        problems.append("clipping (too loud)")

    active = rms > max(3 * np.median(rms), 0.15 * rms.max())
    if active.sum() < 8:
        problems.append("almost no speech")
    if active[:EDGE_FRAMES].any():
        problems.append("speech at very start (word cut at start?)")
    if active[-EDGE_FRAMES:].any():
        problems.append("speech at very end (word cut at end?)")
    return problems


files = sorted(SAMPLES.glob("*.wav"))
flagged = {}
for f in files:
    problems = analyze(f)
    if problems:
        flagged[f] = problems

for f, problems in flagged.items():
    print(f"{f.name}: {', '.join(problems)}")

print(f"\n{len(flagged)} flagged out of {len(files)}")

if "--move" in sys.argv and flagged:
    REJECT.mkdir(exist_ok=True)
    for f in flagged:
        shutil.move(str(f), REJECT / f.name)
    print(f"Moved {len(flagged)} clips to {REJECT}/ (nothing deleted)")
