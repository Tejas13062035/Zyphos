#!/usr/bin/env python3
"""Wake-word distance test using the REAL pipeline:
Windows sidecar mic -> chunk.wav -> openWakeWord (zyphos.onnx).

Usage (from ~/zyp, venv active, PYTHONPATH set):
    python scripts/wake_distance_test.py LABEL [DIST_M ...]
    e.g. python scripts/wake_distance_test.py laptop_mic 1 2 3 4 5

LABEL names the mic being tested (laptop_mic, m1a, ...). Results are appended
to logs/wake_distance_test.csv so you can compare mics later.
Stop any running wake-word listener first, it uses the same sidecar recorder.
"""
import csv
import datetime
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import tools.wakeword as ww

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "logs" / "wake_distance_test.csv"
THRESHOLDS = (0.3, 0.5, 0.7)
REFRACTORY_CHUNKS = 19      # ~1.5 s between counted events (chunk = 80 ms)
WORDS = 5                   # times to say the wake word per distance
SPEAK_SECONDS = 30
SILENCE_SECONDS = 8
COUNTDOWN = 10


def record(seconds):
    """One continuous clip through the same path the live listener uses."""
    ww.CLIP_DURATION = seconds
    audio = ww._record_clip()
    if audio is None:
        sys.exit("ERROR: sidecar returned no audio (is the Windows sidecar running?)")
    sr = sf.info(str(ww.WSL_PATH)).samplerate
    if audio.ndim > 1:
        audio = audio[:, 0]
    return audio.astype(np.int16), sr


def level_stats(audio, sr):
    frame = max(1, sr // 10)  # 100 ms
    n = len(audio) // frame
    if n == 0:
        return -99.0, -99.0
    x = audio[: n * frame].astype(np.float32).reshape(n, frame) / 32768.0
    db = 20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-9)
    return float(np.median(db)), float(np.percentile(db, 95))   # noise floor, speech peak


def scores_for(model, audio):
    model.reset()
    out = []
    for i in range(0, len(audio) - ww.CHUNK, ww.CHUNK):
        pred = model.predict(audio[i:i + ww.CHUNK])
        out.append(max(pred.values()) if pred else 0.0)
    return np.array(out) if out else np.zeros(1)


def count_events(scores, thr):
    """Rising-edge events above thr, at least ~1.5 s apart."""
    events, last, above = 0, -10 ** 9, False
    for i, s in enumerate(scores):
        now_above = s > thr
        if now_above and not above and i - last > REFRACTORY_CHUNKS:
            events += 1
            last = i
        above = now_above
    return events


def countdown(msg, secs):
    print(msg)
    for s in range(secs, 0, -1):
        print(f"  starting in {s:2d} s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 30, end="\r")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    label = sys.argv[1]
    distances = [float(d) for d in sys.argv[2:]] or [1, 2, 3, 4, 5]

    running = subprocess.run(["pgrep", "-af", "zyphos.py --wakeword"],
                             capture_output=True, text=True).stdout.strip()
    if running:
        print("WARNING: a wake-word listener is running and will fight for the mic:\n" + running)
        print("Stop it first, then rerun.")
        sys.exit(1)

    print(f"Loading model... (mic label: {label})")
    model = ww._get_model()
    CSV_PATH.parent.mkdir(exist_ok=True)
    new_file = not CSV_PATH.exists()
    f = open(CSV_PATH, "a", newline="")
    w = csv.writer(f)
    if new_file:
        w.writerow(["time", "label", "distance_m", "sr", "noise_db", "speech_db", "snr_db",
                    "peak_score"] + [f"events@{t}" for t in THRESHOLDS] + ["words_spoken"])

    # 1. silence baseline: noise floor + false triggers
    countdown(f"\nSTEP 1: stay SILENT for {SILENCE_SECONDS} s (room noise baseline).", COUNTDOWN // 2)
    audio, sr = record(SILENCE_SECONDS)
    if sr != 16000:
        print(f"WARNING: sidecar sample rate is {sr}, openWakeWord expects 16000.")
    noise_db, _ = level_stats(audio, sr)
    sc = scores_for(model, audio)
    fa = {t: count_events(sc, t) for t in THRESHOLDS}
    print(f"  noise floor {noise_db:.1f} dBFS | false triggers in silence: "
          + ", ".join(f"@{t}: {fa[t]}" for t in THRESHOLDS))
    w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), label, 0, sr,
                round(noise_db, 1), "", "", round(float(sc.max()), 3)]
               + [fa[t] for t in THRESHOLDS] + [0])

    # 2. per-distance runs
    results = []
    for d in distances:
        countdown(f"\nSTEP: stand {d:g} m from the mic, face it, speak at a normal volume.\n"
                  f"Recording {SPEAK_SECONDS} s. Say 'Zyphos' {WORDS} times, about 5 s apart.", COUNTDOWN)
        print("\a>>> RECORDING NOW <<<", flush=True)
        audio, sr = record(SPEAK_SECONDS)
        noise, speech = level_stats(audio, sr)
        sc = scores_for(model, audio)
        ev = {t: count_events(sc, t) for t in THRESHOLDS}
        snr = speech - noise
        results.append((d, ev, float(sc.max()), snr))
        print(f"  {d:g} m: peak score {sc.max():.2f} | events " +
              ", ".join(f"@{t}: {ev[t]}/{WORDS}" for t in THRESHOLDS) +
              f" | level {speech:.0f} dBFS, SNR {snr:.0f} dB")
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), label, d, sr,
                    round(noise, 1), round(speech, 1), round(snr, 1), round(float(sc.max()), 3)]
                   + [ev[t] for t in THRESHOLDS] + [WORDS])
        f.flush()

    f.close()
    print("\n=== SUMMARY (" + label + ") ===")
    print("dist  peak  hits@0.5  hits@0.3  SNR")
    for d, ev, peak, snr in results:
        print(f"{d:>4g}  {peak:4.2f}  {ev[0.5]}/{WORDS}       {ev[0.3]}/{WORDS}       {snr:3.0f} dB")
    print(f"\nFalse triggers in silence @0.5: {fa[0.5]}  (should be 0)")
    print(f"Saved to {CSV_PATH}")


if __name__ == "__main__":
    main()
