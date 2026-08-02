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
    app.run(host="0.0.0.0", port=9191, debug=False)
