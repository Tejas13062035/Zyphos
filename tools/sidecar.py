import requests

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def click(x, y):
    r = requests.post(f"{SIDECAR_URL}/click", json={"x": x, "y": y})
    return r.json()

def type_text(text):
    r = requests.post(f"{SIDECAR_URL}/type", json={"text": text})
    return r.json()

def screenshot():
    r = requests.get(f"{SIDECAR_URL}/screenshot")
    return r.json()

def scroll(x, y, amount=3):
    r = requests.post(f"{SIDECAR_URL}/scroll", json={"x": x, "y": y, "amount": amount})
    return r.json()

def drag(x1, y1, x2, y2, duration=0.5):
    r = requests.post(f"{SIDECAR_URL}/drag", json={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration})
    return r.json()

def hotkey(keys: list):
    r = requests.post(f"{SIDECAR_URL}/hotkey", json={"keys": keys})
    return r.json()

def _get_kokoro_url():
    return "http://localhost:8880/v1/audio/speech"

def speak(text: str, voice: str = None):
    if voice is None:
        from core.language_detect import get_voice_for_text
        voice = get_voice_for_text(text)
    return speak_kokoro(text, voice)

def speak_kokoro(text: str, voice: str = "bm_george"):
    import shutil
    import time
    from datetime import datetime
    timestamp = datetime.now().strftime("%H%M%S%f")
    audio_wsl = f"/tmp/zyp_tts_{timestamp}.mp3"
    audio_win_wsl = f"/mnt/c/zyphos_sidecar/zyp_tts_{timestamp}.mp3"
    audio_win = f"C:\\zyphos_sidecar\\zyp_tts_{timestamp}.mp3"

    response = requests.post(
        _get_kokoro_url(),
        json={"model": "kokoro", "input": text, "voice": voice, "response_format": "mp3"},
        timeout=(3, 60)
    )
    response.raise_for_status()
    with open(audio_wsl, "wb") as f:
        f.write(response.content)

    shutil.copy(audio_wsl, audio_win_wsl)
    r = requests.post(f"{SIDECAR_URL}/play", json={"path": audio_win})
    wait_time = max(2, len(text) / 15)
    time.sleep(wait_time)
    return r.json()
