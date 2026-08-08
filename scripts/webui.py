import os
import json
from flask import Flask, render_template_string, jsonify, request
from core.daemon import is_running, get_pid
from memory.store import recall

app = Flask(__name__)

GOAL_FILE = os.path.expanduser("~/zyp/state/pending_goals.txt")
LOG_FILE = os.path.expanduser("~/zyp/logs/daemon.log")
SMART_MODE_FILE = os.path.expanduser("~/zyp/state/smart_mode")


def get_pending():
    if not os.path.exists(GOAL_FILE):
        return []
    with open(GOAL_FILE, "r") as f:
        return [g.strip() for g in f.readlines() if g.strip()]


def get_last_logs(n=20):
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    return [l.strip() for l in lines[-n:]]


def get_backend_info():
    llm = os.environ.get("ZYPHOS_BACKEND", "phi").upper()
    vision = os.environ.get("ZYPHOS_VISION_BACKEND", "groq").upper()
    smart = os.path.exists(SMART_MODE_FILE)
    return llm, vision, smart


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Z.Y.P.H.O.S</title>
    <style>
        body { background: #0a0a0a; color: #e0e0e0; font-family: monospace; padding: 20px; }
        h1 { color: #00ffcc; letter-spacing: 4px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        .panel { background: #111; border: 1px solid #333; border-radius: 6px; padding: 16px; }
        .panel h3 { margin: 0 0 10px 0; font-size: 12px; letter-spacing: 2px; color: #888; }
        .running { color: #00ff88; }
        .stopped { color: #ff4444; }
        .log-line { font-size: 12px; color: #aaa; margin: 2px 0; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; color: #888; border-bottom: 1px solid #333; padding: 6px; }
        td { padding: 6px; border-bottom: 1px solid #1a1a1a; vertical-align: top; }
        td:first-child { color: #555; white-space: nowrap; }
        td:nth-child(2) { color: #00ccff; }
        .task-list { margin: 4px 0 0 0; padding: 0; list-style: none; }
        .task-list li { font-size: 11px; color: #666; margin: 2px 0; }
        .task-list li span { color: #444; }
        input { background: #1a1a1a; border: 1px solid #333; color: #fff; padding: 8px 12px; font-family: monospace; width: 70%; border-radius: 4px; }
        button { background: #00ffcc; color: #000; border: none; padding: 8px 16px; font-family: monospace; font-weight: bold; border-radius: 4px; cursor: pointer; margin-left: 8px; }
        .pid { color: #888; font-size: 13px; }
        .pending-item { color: #ffcc00; font-size: 13px; margin: 2px 0; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; margin-top: 4px; }
        .badge-blue { background: #003366; color: #00ccff; }
        .badge-green { background: #003322; color: #00ff88; }
        .badge-yellow { background: #332200; color: #ffcc00; }
    </style>
</head>
<body>
    <h1>Z.Y.P.H.O.S</h1>
    <div style="margin-bottom: 16px;">
        <input type="text" id="goalInput" placeholder="enter goal..." onkeydown="if(event.key==='Enter') sendGoal()">
        <button onclick="sendGoal()">SEND</button>
        <button id="micBtn" onclick="toggleRecording()" style="background:#ffcc00;">🎤</button>
        <button id="convBtn" onclick="toggleConversationMode()" style="background:#444; color:#fff;">💬 OFF</button>
        <button onclick="cancelGoal()" style="background:#ff4444; color:#fff;">CANCEL</button>
    </div>
    <div class="grid3">
        <div class="panel" id="daemon-status">
            <h3>DAEMON</h3>
            <span class="{{ 'running' if running else 'stopped' }}">
                {{ 'RUNNING' if running else 'STOPPED' }}
            </span>
            <span class="pid"> — PID {{ pid if running else 'none' }}</span>
        </div>
        <div class="panel">
            <h3>BACKENDS</h3>
            <span class="badge badge-blue">LLM: {{ llm_backend }}</span>
            <span class="badge badge-green">VISION: {{ vision_backend }}</span>
            <span class="badge {{ 'badge-green' if smart_mode else 'badge-yellow' }}">
                SMART: {{ 'ON' if smart_mode else 'OFF' }}
            </span>
        </div>
        <div class="panel" id="pending-queue">
            <h3>PENDING QUEUE</h3>
            {% if pending %}
                {% for g in pending %}
                    <div class="pending-item">→ {{ g }}</div>
                {% endfor %}
            {% else %}
                <span style="color:#444">none</span>
            {% endif %}
        </div>
    </div>
    <div class="panel" id="daemon-log" style="margin-bottom: 16px;">
        <h3>DAEMON LOG</h3>
        {% for line in logs %}
            <div class="log-line">{{ line }}</div>
        {% endfor %}
    </div>
    <div class="panel" id="goal-history">
        <h3>GOAL HISTORY</h3>
        <table>
            <tr><th>Time</th><th>Goal</th><th>Tasks</th></tr>
            {% for e in memory %}
            <tr>
                <td>{{ e.timestamp[:19] }}</td>
                <td>
                    {{ e.goal }}
                    {% if e.tasks %}
                    <ul class="task-list">
                        {% for t in e.tasks %}
                        <li>
                            → {{ t.description if t.description is defined else t }}
                            {% if t.result is defined and t.result %}
                            <span>— {{ t.result[:80] }}{% if t.result|length > 80 %}...{% endif %}</span>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                    {% endif %}
                </td>
                <td style="color:#555">{{ e.tasks|length }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <script>
        function sendGoal() {
            const goal = document.getElementById('goalInput').value.trim();
            if (!goal) return;
            fetch('/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({goal})})
            .then(() => { document.getElementById('goalInput').value = ''; });
        }
        function cancelGoal() {
            fetch('/cancel', {method: 'POST'});
        }

        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;

        async function toggleRecording() {
            const micBtn = document.getElementById('micBtn');
            if (!isRecording) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            sampleRate: 48000,
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        }
                    });
                    mediaRecorder = new MediaRecorder(stream, {
                        mimeType: 'audio/webm;codecs=opus',
                        audioBitsPerSecond: 128000
                    });
                    audioChunks = [];
                    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                    mediaRecorder.onstop = () => {
                        const blob = new Blob(audioChunks, { type: 'audio/webm' });
                        stream.getTracks().forEach(t => t.stop());
                        sendVoiceCommand(blob);
                    };
                    mediaRecorder.start();
                    isRecording = true;
                    micBtn.style.background = '#ff4444';
                    micBtn.textContent = '⏹';
                } catch (err) {
                    alert('Mic access failed: ' + err.message);
                }
            } else {
                mediaRecorder.stop();
                isRecording = false;
                micBtn.style.background = '#ffcc00';
                micBtn.textContent = '🎤';
            }
        }

        let conversationMode = false;

        function toggleConversationMode() {
            conversationMode = !conversationMode;
            const btn = document.getElementById('convBtn');
            btn.textContent = conversationMode ? '💬 ON' : '💬 OFF';
            btn.style.background = conversationMode ? '#00ffcc' : '#444';
            btn.style.color = conversationMode ? '#000' : '#fff';
        }

        function sendVoiceCommand(blob) {
            const micBtn = document.getElementById('micBtn');
            micBtn.textContent = '...';
            const formData = new FormData();
            formData.append('audio', blob, 'recording.webm');
            fetch('/voice_command', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    micBtn.textContent = '🎤';
                    if (data.status === 'error') {
                        alert('Voice command failed: ' + data.message);
                        return;
                    }
                    if (conversationMode && data.text) {
                        pollGoalStatus(data.text);
                    }
                })
                .catch(err => {
                    micBtn.textContent = '🎤';
                    alert('Upload failed: ' + err.message);
                });
        }

        function pollGoalStatus(goalText) {
            const interval = setInterval(() => {
                fetch('/goal_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({goal: goalText})
                })
                .then(r => r.json())
                .then(data => {
                    if (!data.pending) {
                        clearInterval(interval);
                        if (conversationMode) {
                            setTimeout(() => toggleRecording(), 500);
                        }
                    }
                })
                .catch(() => clearInterval(interval));
            }, 1000);
        }
    </script>
    <script>
function refreshDashboard() {
    fetch(window.location.pathname)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, "text/html");

            // only update the panels, not the whole page — leaves your typed input alone
            const panelsToUpdate = ["daemon-status", "pending-queue", "daemon-log", "goal-history"];
            panelsToUpdate.forEach(id => {
                const oldEl = document.getElementById(id);
                const newEl = newDoc.getElementById(id);
                if (oldEl && newEl) {
                    oldEl.innerHTML = newEl.innerHTML;
                }
            });
        })
        .catch(err => console.error("refresh failed", err));
}
setInterval(refreshDashboard, 3000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    llm_backend, vision_backend, smart_mode = get_backend_info()
    return render_template_string(HTML,
        running=is_running(),
        pid=get_pid(),
        pending=get_pending(),
        logs=get_last_logs(),
        memory=list(reversed(recall(10))),
        llm_backend=llm_backend,
        vision_backend=vision_backend,
        smart_mode=smart_mode
    )

@app.route("/send", methods=["POST"])
def send_goal():
    goal = request.json.get("goal", "").strip()
    if goal:
        with open(GOAL_FILE, "a") as f:
            f.write(goal + "\n")
    return jsonify({"status": "sent"})

@app.route("/voice_command", methods=["POST"])
def voice_command():
    import sys
    import tempfile
    import subprocess as sp
    sys.path.insert(0, os.path.expanduser("~/zyp"))
    from tools.stt import transcribe

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"status": "error", "message": "no audio uploaded"})

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        audio_file.save(tmp_in.name)
        webm_path = tmp_in.name

    wav_path = webm_path.replace(".webm", ".wav")
    try:
        sp.run(
            ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, check=True
        )
    except sp.CalledProcessError as e:
        os.remove(webm_path)
        return jsonify({"status": "error", "message": f"ffmpeg conversion failed: {e.stderr.decode()[:200]}"})

    import shutil
    debug_path = os.path.expanduser("~/zyp/state/last_voice_command.wav")
    shutil.copy(wav_path, debug_path)

    try:
        text, confidence = transcribe(wav_path)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        os.remove(webm_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)

    if not text:
        return jsonify({"status": "error", "message": "no speech detected"})

    with open(GOAL_FILE, "a") as f:
        f.write(text + "\n")

    return jsonify({"status": "sent", "text": text, "confidence": round(confidence, 2)})

@app.route("/goal_status", methods=["POST"])
def goal_status():
    goal = request.json.get("goal", "").strip()
    pending = get_pending()
    still_pending = goal in pending
    return jsonify({"pending": still_pending})

@app.route("/cancel", methods=["POST"])
def cancel_goal():
    import requests
    from core.cancel_flag import request_cancel
    request_cancel()
    try:
        requests.post("http://127.0.0.1:5000/stop_audio", timeout=3)
    except Exception as e:
        print(f"CANCEL: failed to reach sidecar stop_audio: {e}")
    return jsonify({"status": "cancel requested"})

if __name__ == "__main__":
    cert_path = os.path.expanduser("~/zyp/certs/desktop-8m9899c.tail05f2a2.ts.net.crt")
    key_path = os.path.expanduser("~/zyp/certs/desktop-8m9899c.tail05f2a2.ts.net.key")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        app.run(host="0.0.0.0", port=9191, debug=False, ssl_context=(cert_path, key_path))
    else:
        print("WARNING: TLS cert not found, falling back to HTTP")
        app.run(host="0.0.0.0", port=9191, debug=False)
