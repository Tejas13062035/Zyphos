from flask import Flask, request, jsonify
import cv2
import pyttsx3
import subprocess
import pyautogui
import mss
import base64
import io
import pyperclip
from PIL import Image

import re

def strip_markdown_for_speech(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    return text

app = Flask(__name__)

@app.route("/wifi_info", methods=["GET"])
def wifi_info():
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True
    )
    return jsonify({"status": "ok", "info": result.stdout})

@app.route("/network_scan", methods=["POST"])
def network_scan():
    data = request.json
    base = data.get("target", "192.168.31")
    import socket
    from concurrent.futures import ThreadPoolExecutor

    def ping(ip):
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "500", ip],
            capture_output=True
        )
        if result.returncode == 0:
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except:
                hostname = "unknown"
            return {"ip": ip, "hostname": hostname}
        return None

    ips = [f"{base}.{i}" for i in range(1, 255)]
    found = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(ping, ips)
        for r in results:
            if r:
                found.append(r)

    return jsonify({"status": "ok", "hosts_found": len(found), "hosts": found})

@app.route("/clipboard/get", methods=["GET"])
def clipboard_get():
    content = pyperclip.paste()
    return jsonify({"status": "ok", "content": content})

@app.route("/clipboard/set", methods=["POST"])
def clipboard_set():
    data = request.json
    text = data.get("text", "")
    pyperclip.copy(text)
    return jsonify({"status": "ok", "text": text})

@app.route("/open_app", methods=["POST"])
def open_app():
    data = request.json
    app = data.get("app")
    subprocess.Popen(["powershell", "-c", f"Start-Process '{app}'"])
    import time
    time.sleep(1)
    pyautogui.hotkey('alt', 'tab')
    return jsonify({"status": "opened", "app": app})

@app.route("/open_url", methods=["POST"])
def open_url():
    data = request.json
    url = data.get("url", "https://google.com")
    subprocess.Popen(["powershell", "-c", f"Start-Process '{url}'"])
    return jsonify({"status": "opened", "url": url})

@app.route("/play_audio", methods=["POST"])
def play_audio():
    data = request.json
    path = data.get("path")
    print(f"PLAYING: {path}")
    proc = subprocess.Popen([r"C:\vlc\vlc.exe", "--intf", "dummy", "--play-and-exit", path])
    print(f"VLC PID: {proc.pid}")
    return jsonify({"status": "playing", "path": path})

@app.route("/stop_audio", methods=["POST"])
def stop_audio():
    subprocess.run(["taskkill", "/IM", "vlc.exe", "/F"], capture_output=True)
    return jsonify({"status": "stopped"})

@app.route("/webcam", methods=["GET"])
def webcam():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return jsonify({"error": "no camera found"})
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return jsonify({"error": "failed to capture frame"})
    _, buffer = cv2.imencode(".jpg", frame)
    img_base64 = base64.b64encode(buffer).decode("utf-8")
    return jsonify({"image": img_base64})

@app.route("/record_chunk", methods=["POST"])
def record_chunk():
    data = request.json
    duration = data.get("duration", 2)
    path = r"C:\zyphos_sidecar\chunk.wav"
    subprocess.Popen(["python", r"C:\zyphos_sidecar\recorder.py", str(duration), path])
    return jsonify({"status": "recording", "duration": duration, "path": path})

@app.route("/record", methods=["POST"])
def record():
    data = request.json
    duration = data.get("duration", 5)
    subprocess.Popen(["python", r"C:\zyphos_sidecar\recorder.py", str(duration)])
    return jsonify({"status": "recording", "duration": duration})

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "online"})

@app.route("/click", methods=["POST"])
def click():
    data = request.json
    x = data["x"]
    y = data["y"]
    pyautogui.click(x, y)
    return jsonify({"status": "clicked", "x": x, "y": y})

@app.route("/type", methods=["POST"])
def type_text():
    data = request.json
    text = data["text"]
    pyautogui.write(text)
    return jsonify({"status": "typed", "text": text})

@app.route("/screenshot", methods=["GET"])
def screenshot():
    from datetime import datetime
    import os

    save_dir = "C:/zyphos_sidecar/screenshots"
    os.makedirs(save_dir, exist_ok=True)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)

    img_pil = Image.frombytes("RGB", img.size, img.rgb)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{save_dir}/screenshot_{timestamp}.png"
    img_pil.save(filename)

    buffer = io.BytesIO()
    img_pil.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return jsonify({"image": img_base64, "saved": filename})

@app.route("/scroll", methods=["POST"])
def scroll():
    data = request.json
    x = data["x"]
    y = data["y"]
    amount = data.get("amount", 3)  # positive = up, negative = down
    pyautogui.scroll(amount, x=x, y=y)
    return jsonify({"status": "scrolled", "x": x, "y": y, "amount": amount})

@app.route("/drag", methods=["POST"])
def drag():
    data = request.json
    x1, y1 = data["x1"], data["y1"]
    x2, y2 = data["x2"], data["y2"]
    duration = data.get("duration", 0.5)
    pyautogui.moveTo(x1, y1)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return jsonify({"status": "dragged", "from": [x1, y1], "to": [x2, y2]})

@app.route("/hotkey", methods=["POST"])
def hotkey():
    data = request.json
    keys = data["keys"]  # e.g. ["ctrl", "c"] or ["alt", "tab"]
    pyautogui.hotkey(*keys)
    return jsonify({"status": "hotkey_sent", "keys": keys})

@app.route("/speak", methods=["POST"])
def speak():
    import asyncio
    import edge_tts
    import os
    import tempfile
    from playsound import playsound

    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "en-GB-RyanNeural")

    if not text:
        return jsonify({"status": "error", "message": "no text provided"})

    text = strip_markdown_for_speech(text)

    try:
        tmp_path = os.path.join(tempfile.gettempdir(), f"zyphos_tts_{os.getpid()}_{abs(hash(text))}.mp3")

        async def generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp_path)

        asyncio.run(generate())
        playsound(tmp_path)
        os.remove(tmp_path)

        return jsonify({"status": "spoken", "text": text, "voice": voice})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/play", methods=["POST"])
def play():
    from playsound import playsound
    data = request.json
    path = data.get("path", "")
    playsound(path)
    return jsonify({"status": "playing", "path": path})

@app.route("/speak_batch", methods=["POST"])
def speak_batch():
    import asyncio
    import edge_tts
    import os
    import tempfile
    from playsound import playsound

    data = request.json
    lines = data.get("lines", [])  # list of {"text": ..., "voice": ...}

    if not lines:
        return jsonify({"status": "error", "message": "no lines provided"})

    try:
        temp_dir = tempfile.gettempdir()
        paths = [os.path.join(temp_dir, f"zyphos_batch_{os.getpid()}_{i}.mp3") for i in range(len(lines))]

        async def generate_all():
            tasks = []
            for line, path in zip(lines, paths):
                clean_text = strip_markdown_for_speech(line["text"])
                communicate = edge_tts.Communicate(clean_text, line.get("voice", "en-GB-RyanNeural"))
                tasks.append(communicate.save(path))
            await asyncio.gather(*tasks)

        asyncio.run(generate_all())

        for path in paths:
            playsound(path)
            os.remove(path)

        return jsonify({"status": "spoken_batch", "count": len(lines)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

app.run(host="0.0.0.0", port=5000)


