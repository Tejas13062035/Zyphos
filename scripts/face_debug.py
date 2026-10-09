import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import face_recognition
from tools import esp32_cam

OUT = ROOT / "state" / "face_debug"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10

OUT.mkdir(parents=True, exist_ok=True)
for i in range(N):
    t0 = time.time()
    src = esp32_cam.capture()
    dt = time.time() - t0
    dst = OUT / f"frame_{i:02d}.jpg"
    shutil.copy(src, dst)
    img = face_recognition.load_image_file(str(dst))
    h, w = img.shape[:2]
    faces = face_recognition.face_locations(img)
    sizes = [f"{b - t}px" for (t, r, b, l) in faces]
    print(f"{i:02d}: {w}x{h}  brightness={img.mean():.0f}/255  faces={len(faces)} {sizes}  capture={dt:.1f}s")
    time.sleep(0.5)
print(f"frames saved in {OUT}")
