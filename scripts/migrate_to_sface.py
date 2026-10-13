#!/usr/bin/env python3
"""Add SFace embeddings to your enrolled people WITHOUT touching their existing dlib data,
so going back is just unsetting ZYPHOS_FACE_BACKEND. Dry run unless you pass --apply.

  python3 scripts/migrate_to_sface.py                                    # dry run, reference photos only
  python3 scripts/migrate_to_sface.py --add Tejas state/walk1 state/walk2 --apply

--add NAME PATH...  extra photos of NAME (folders of .jpg or single files). Use frames taken by the door camera:
                    embeddings from the same camera match its blurry frames better. Only frames with exactly
                    one face are used, so make sure NAME is the only person in them.
"""
import argparse
import json
import os
import shutil
import statistics as st
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.face_recognition_backend import PERSONS_DIR, THRESHOLD_SFACE, detect_and_embed  # noqa: E402

MAX_EXTRA = 8          # extra embeddings kept per person, spread from sharpest to blurriest
EXTRA_SCORE_MIN = 0.85  # detector confidence needed for an extra frame


def faces_of(path):
    bgr = cv2.imread(str(path))
    if bgr is None:
        return []
    faces, _, _ = detect_and_embed(bgr)
    return faces


def gather_extras(paths):
    found = []
    for p in paths:
        p = Path(p)
        files = sorted(p.glob("*.jpg")) if p.is_dir() else [p]
        for f in files:
            faces = faces_of(f)
            if len(faces) == 1 and faces[0]["score"] >= EXTRA_SCORE_MIN:
                found.append(faces[0])
    found.sort(key=lambda d: -d["sharp"])
    if len(found) > MAX_EXTRA:
        idx = sorted(set(np.linspace(0, len(found) - 1, MAX_EXTRA).round().astype(int)))
        found = [found[i] for i in idx]
    return found


def cos(a, b):
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    ap.add_argument("--add", nargs="+", action="append", metavar="NAME_OR_PATH",
                    help="NAME followed by folders or images of that person")
    args = ap.parse_args()
    extras_for = {}
    for entry in args.add or []:
        extras_for.setdefault(entry[0].lower(), []).extend(entry[1:])

    persons = Path(PERSONS_DIR)
    plan = {}          # name -> (json_path, [embeddings], notes)
    for js in sorted(persons.glob("*.json")):
        data = json.loads(js.read_text())
        name = data.get("name", js.stem)
        embs, notes = [], []
        ref = js.with_suffix(".jpg")
        ref_faces = faces_of(ref) if ref.exists() else []
        if ref_faces:
            best = max(ref_faces, key=lambda d: d["loc"][2] - d["loc"][0])
            embs.append(best["emb"])
            notes.append(f"reference photo (sharp {best['sharp']:.0f})")
        else:
            notes.append("no face found in the reference photo")
        extra = gather_extras(extras_for.get(name.lower(), []))
        for d in extra:
            embs.append(d["emb"])
        if extra:
            notes.append(f"{len(extra)} extra frames (sharp {min(d['sharp'] for d in extra):.0f}"
                         f" to {max(d['sharp'] for d in extra):.0f})")
        plan[name] = (js, embs, notes)

    unmatched = set(extras_for) - {n.lower() for n in plan}
    for u in sorted(unmatched):
        print(f"! --add {u}: no enrolled person with that name (enrolled: {', '.join(plan) or 'nobody'})")

    print("SFace embeddings that would be stored:")
    for name, (js, embs, notes) in plan.items():
        line = f"  {name}: {len(embs)} embeddings; " + "; ".join(notes)
        if len(embs) >= 2:
            sims = [cos(embs[i], embs[j]) for i in range(len(embs)) for j in range(i + 1, len(embs))]
            line += f"; own spread min {min(sims):.2f} median {st.median(sims):.2f}"
        print(line)

    names = [n for n in plan if plan[n][1]]
    risky = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            worst = max(cos(a, b) for a in plan[names[i]][1] for b in plan[names[j]][1])
            flag = ""
            if worst >= THRESHOLD_SFACE - 0.1:
                flag, risky = "   <-- too close to the match threshold, review before applying", True
            print(f"  closest pair across {names[i]} / {names[j]}: {worst:.2f}{flag}")

    if not args.apply:
        print("\ndry run: nothing written. Add --apply to store these.")
        return
    if risky:
        sys.exit("\nnot applying: two different people look alike to SFace in these embeddings.")
    wrote = 0
    for name, (js, embs, _) in plan.items():
        if not embs:
            continue
        data = json.loads(js.read_text())
        bak = js.with_name(js.name + ".bak")
        if not bak.exists():
            shutil.copy(js, bak)
        data["sface_embeddings"] = [np.asarray(e, dtype=np.float32).round(5).tolist() for e in embs]
        data["sface_meta"] = {"count": len(embs), "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        tmp = js.with_name(js.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, js)
        wrote += 1
        print(f"  wrote {js.name} (backup: {bak.name})")
    print(f"\nupdated {wrote} people. Their dlib data is untouched. Switch with:  export ZYPHOS_FACE_BACKEND=sface")


if __name__ == "__main__":
    main()
