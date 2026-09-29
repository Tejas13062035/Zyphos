import wave
from pathlib import Path

import numpy as np

FRAME = 320  # 20 ms at 16 kHz


def load(path):
    with wave.open(str(path), "rb") as wf:
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)


flagged = 0
files = sorted(Path("my_real_samples").glob("*.wav"))
for f in files:
    d = load(f)
    n = len(d) // FRAME
    rms = np.sqrt((d[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1))
    peak = rms.max()
    start_edge = rms[:5].max() / peak   # first 100 ms vs. loudest moment
    end_edge = rms[-5:].max() / peak    # last 100 ms vs. loudest moment

    verdict = ""
    if start_edge > 0.4:
        verdict += " CUT-START?"
    if end_edge > 0.4:
        verdict += " CUT-END?"
    if verdict:
        flagged += 1
    if verdict or f.name == "zyphos_0001.wav":
        print(f"{f.name}  start={start_edge:.2f}  end={end_edge:.2f}{verdict}")

print(f"\n{flagged} flagged out of {len(files)}")
