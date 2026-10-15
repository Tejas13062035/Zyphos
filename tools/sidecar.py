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

def speak_kokoro(text: str, voice: str = "am_onyx"):
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
    r = requests.post(f"{SIDECAR_URL}/play", json={"path": audio_win})   # blocks until playback finishes
    return r.json()


import queue
import re
import threading
import time


def _kokoro_file(text: str, voice: str) -> str:
    """Generate speech for one chunk of text. Returns the Windows path of the mp3."""
    import shutil
    from datetime import datetime
    ts = datetime.now().strftime("%H%M%S%f")
    wsl_tmp = f"/tmp/zyp_tts_{ts}.mp3"
    win_wsl = f"/mnt/c/zyphos_sidecar/zyp_tts_{ts}.mp3"
    win = f"C:\\zyphos_sidecar\\zyp_tts_{ts}.mp3"
    r = requests.post(
        _get_kokoro_url(),
        json={"model": "kokoro", "input": text, "voice": voice, "response_format": "mp3"},
        timeout=(3, 120),
    )
    r.raise_for_status()
    with open(wsl_tmp, "wb") as f:
        f.write(r.content)
    shutil.copy(wsl_tmp, win_wsl)
    return win


speak_timing = {}   # filled by speak_fast: seconds until the first sentence started playing


def speak_fast(text: str, voice: str = None):
    """Speak sentence by sentence: sentence 2 is generated while sentence 1 plays."""
    if voice is None:
        from core.language_detect import get_voice_for_text
        voice = get_voice_for_text(text)
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not parts:
        return
    speak_timing.clear()
    t_start = time.time()
    q = queue.Queue()

    def producer():
        try:
            for part in parts:
                q.put(_kokoro_file(part, voice))
        except Exception as e:
            print(f"[speak_fast] generation failed: {e}")
        finally:
            q.put(None)

    threading.Thread(target=producer, daemon=True).start()
    while True:
        path = q.get()
        if path is None:
            break
        if "first_audio_s" not in speak_timing:
            speak_timing["first_audio_s"] = round(time.time() - t_start, 2)   # first sentence is ready and is sent to play
        requests.post(f"{SIDECAR_URL}/play", json={"path": path})
