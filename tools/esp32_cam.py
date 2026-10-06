import requests

ESP32_CAM_URL = "http://10.166.189.43/capture"
CAPTURE_PATH = "/tmp/zyp_esp32_cam.jpg"


def capture() -> str:
    """Fetch one JPEG frame from the ESP32-CAM over WiFi. Returns the local path."""
    response = requests.get(ESP32_CAM_URL, timeout=10)
    response.raise_for_status()
    with open(CAPTURE_PATH, "wb") as f:
        f.write(response.content)
    return CAPTURE_PATH
