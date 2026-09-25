import requests
import base64
import os

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()
WEBCAM_PATH = "/tmp/zyp_webcam.jpg"

def capture():
    r = requests.get(f"{SIDECAR_URL}/webcam")
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    img_bytes = base64.b64decode(data["image"])
    with open(WEBCAM_PATH, "wb") as f:
        f.write(img_bytes)
    return WEBCAM_PATH

def look_around(prompt="What do you see?"):
    path = capture()
    from tools.vision import analyze_screenshot
    return analyze_screenshot(path, prompt)
