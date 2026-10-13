#!/usr/bin/env python3
"""Read-only benchmark: your current face pipeline (dlib) vs OpenCV YuNet + SFace, on saved frames.
Changes nothing in Zyphos. Downloads two model files into state/models/ the first time.

  python3 scripts/bench_faces.py                      # uses state/face_debug/*.jpg, then state/captures/*.jpg
  python3 scripts/bench_faces.py frame1.jpg frame2.jpg
"""
import statistics as st
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "state" / "models"
ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
FILES = {
    "yunet": ("face_detection_yunet_2023mar.onnx", f"{ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx", 100_000),
    "sface": ("face_recognition_sface_2021dec.onnx", f"{ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx", 10_000_000),
}
MAX_FRAMES = 12


def get_model(key):
    name, url, min_bytes = FILES[key]
    path = MODELS / name
    if not path.exists() or path.stat().st_size < min_bytes:
        MODELS.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name} ...")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            sys.exit(f"could not download {name}: {e}\nDownload it by hand from {url}\nand save it as {path}")
    size = path.stat().st_size
    if size < min_bytes:   # a few hundred bytes means a git-LFS pointer, not the model
        sys.exit(f"{name} is only {size} bytes - the download is not the real model. Get it from the opencv_zoo repo by hand.")
    return str(path)


def ms(values):
    return f"{st.median(values) * 1000:.0f} ms (min {min(values) * 1000:.0f}, max {max(values) * 1000:.0f})" if values else "n/a"


def main():
    args = [Path(a) for a in sys.argv[1:]]
    paths = []
    for a in args:
        paths += sorted(a.glob("*.jpg")) if a.is_dir() else [a]
    if not paths:
        for d in ("face_debug", "captures"):
            paths += sorted((ROOT / "state" / d).glob("*.jpg"))
    paths = paths[:MAX_FRAMES]
    if not paths:
        sys.exit("no frames found: run scripts/face_debug.py first, or pass image paths")

    yunet_path, sface_path = get_model("yunet"), get_model("sface")
    detector = cv2.FaceDetectorYN.create(yunet_path, "", (320, 320), 0.8, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(sface_path, "")
    try:
        import face_recognition
    except ImportError:
        face_recognition = None
        print("(face_recognition not importable here: skipping the dlib columns)")

    print(f"opencv {cv2.__version__}, {len(paths)} frames\n")
    print(f"{'frame':<22}{'size':<11}{'dlib faces':<22}{'yunet faces (px, score)'}")
    t_dlib_det, t_dlib_emb, t_yn_det, t_sf_emb = [], [], [], []
    embeddings, dlib_embs = [], []
    first = True
    for p in paths:
        bgr = cv2.imread(str(p))
        if bgr is None:
            continue
        h, w = bgr.shape[:2]

        d_desc = "-"
        if face_recognition is not None:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            t = time.time(); locs = face_recognition.face_locations(rgb); dt = time.time() - t
            if locs:
                t = time.time(); enc = face_recognition.face_encodings(rgb, known_face_locations=locs); de = time.time() - t
                t_dlib_emb.append(de)
                if len(locs) == 1:
                    dlib_embs.append(enc[0])
            if not first:
                t_dlib_det.append(dt)
            d_desc = f"{len(locs)} {[b - t_ for (t_, r, b, l) in locs]}"

        detector.setInputSize((w, h))
        t = time.time(); _, faces = detector.detect(bgr); dt = time.time() - t
        faces = [] if faces is None else faces
        if not first:
            t_yn_det.append(dt)
        for f in faces[:1]:
            t = time.time(); feat = recognizer.feature(recognizer.alignCrop(bgr, f)); de = time.time() - t
            t_sf_emb.append(de)
            if len(faces) == 1:
                embeddings.append(feat)
        y_desc = f"{len(faces)} {[(int(f[3]), round(float(f[-1]), 2)) for f in faces]}"
        print(f"{p.name:<22}{f'{w}x{h}':<11}{d_desc:<22}{y_desc}")
        first = False   # the first frame is a warm-up and is left out of the timings

    print("\nper-frame cost (first frame excluded as warm-up):")
    print(f"  dlib   detect : {ms(t_dlib_det)}")
    print(f"  dlib   embed  : {ms(t_dlib_emb)}")
    print(f"  YuNet  detect : {ms(t_yn_det)}")
    print(f"  SFace  embed  : {ms(t_sf_emb)}")

    if len(embeddings) >= 2:
        sims = [float(recognizer.match(embeddings[i], embeddings[j], cv2.FaceRecognizerSF_FR_COSINE))
                for i in range(len(embeddings)) for j in range(i + 1, len(embeddings))]
        print(f"\nSFace cosine similarity between your own frames (higher = more alike): "
              f"min {min(sims):.2f}  median {st.median(sims):.2f}  max {max(sims):.2f}")
        print("  OpenCV suggests 0.363 as the same-person threshold; a threshold well below your 'min' is safe for you.")
    if len(dlib_embs) >= 2:
        d = [float(np.linalg.norm(dlib_embs[i] - dlib_embs[j])) for i in range(len(dlib_embs)) for j in range(i + 1, len(dlib_embs))]
        print(f"dlib distance between your own frames (lower = more alike): min {min(d):.2f}  median {st.median(d):.2f}  max {max(d):.2f}")


if __name__ == "__main__":
    main()
