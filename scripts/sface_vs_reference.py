#!/usr/bin/env python3
"""Read-only: how well does SFace match your enrolled reference photos against door frames?
Needs the models that scripts/bench_faces.py downloaded into state/models/.

  python3 scripts/face_debug.py 12            # walk in from the door toward your chair
  python3 scripts/sface_vs_reference.py       # reads state/face_debug/*.jpg
  python3 scripts/sface_vs_reference.py state/walk1 state/walk2 extra.jpg
"""
import json
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "state" / "models"
PERSONS = ROOT / "memory" / "persons"
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
SFACE = MODELS / "face_recognition_sface_2021dec.onnx"
THRESHOLDS = (0.30, 0.363, 0.45, 0.55)


def main():
    for m in (YUNET, SFACE):
        if not m.exists():
            sys.exit(f"missing {m.name}: run scripts/bench_faces.py once first (it downloads the models)")
    detector = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.8, 0.3, 5000)
    rec = cv2.FaceRecognizerSF.create(str(SFACE), "")

    def faces_in(bgr):
        detector.setInputSize((bgr.shape[1], bgr.shape[0]))
        _, f = detector.detect(bgr)
        return [] if f is None else list(f)

    def embed(bgr, row):
        return rec.feature(rec.alignCrop(bgr, row))

    def cos(a, b):
        return float(rec.match(a, b, cv2.FaceRecognizerSF_FR_COSINE))

    def sharp(bgr, row):
        x, y, w, h = [int(v) for v in row[:4]]
        crop = bgr[max(0, y):max(0, y) + h, max(0, x):max(0, x) + w]
        if crop.size == 0:
            return 0.0
        return float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

    # --- enrolled people, embedded from their reference photos
    enrolled = {}
    for js in sorted(PERSONS.glob("*.json")):
        name = json.loads(js.read_text()).get("name", js.stem)
        photo = js.with_suffix(".jpg")
        bgr = cv2.imread(str(photo)) if photo.exists() else None
        faces = faces_in(bgr) if bgr is not None else []
        if not faces:
            print(f"! {name}: no face found in the reference photo {photo.name}, skipping")
            continue
        best = max(faces, key=lambda r: r[3])
        enrolled[name] = embed(bgr, best)
    if not enrolled:
        sys.exit("no usable enrolled people found in memory/persons/")
    print("enrolled:", ", ".join(enrolled))
    names = list(enrolled)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            print(f"  reference vs reference ({names[i]} / {names[j]}), two DIFFERENT people: "
                  f"{cos(enrolled[names[i]], enrolled[names[j]]):.2f}")

    # --- frames
    args = [Path(a) for a in sys.argv[1:]] or [ROOT / "state" / "face_debug"]
    paths = []
    for a in args:
        paths += sorted(a.glob("*.jpg")) if a.is_dir() else [a]
    print(f"\n{'frame':<24}{'face_px':>8}{'score':>7}{'sharp':>8}   similarity to each enrolled person")
    sims = {n: [] for n in names}
    frames_with_face = 0
    for p in paths:
        bgr = cv2.imread(str(p))
        if bgr is None:
            continue
        faces = faces_in(bgr)
        if faces:
            frames_with_face += 1
        for row in faces:
            e = embed(bgr, row)
            s = {n: cos(enrolled[n], e) for n in names}
            for n in names:
                sims[n].append(s[n])
            print(f"{p.parent.name + '/' + p.name:<24}{int(row[3]):>8}{float(row[-1]):>7.2f}{sharp(bgr, row):>8.0f}   "
                  + "  ".join(f"{n}={s[n]:.2f}" for n in names))

    print(f"\n{frames_with_face} of {len(paths)} frames contained a face")
    for n in names:
        v = sims[n]
        if not v:
            continue
        counts = "  ".join(f">={t}: {sum(x >= t for x in v)}/{len(v)}" for t in THRESHOLDS)
        print(f"{n:<20} min {min(v):.2f}  median {st.median(v):.2f}  max {max(v):.2f}   {counts}")
    print("\nIf every face in these frames is YOU, then your own row shows how well you match at the door,")
    print("and the other person's row shows how high a different person scores.")


if __name__ == "__main__":
    main()
