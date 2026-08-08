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


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Z.Y.P.H.O.S</title>
<style>
  :root {
    --void: #050810;
    --core-blue: #2ee6ff;
    --core-blue-dim: #0f4a5c;
    --amber: #ff9d3d;
    --amber-dim: #5c3a0f;
    --chrome: #1a3a4a;
    --chrome-bright: #3a6a80;
    --text: #9fd8e8;
    --text-dim: #4a7080;
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0;
    padding: 0;
    background: var(--void);
    overflow: hidden;
    height: 100%;
    font-family: 'Courier New', ui-monospace, monospace;
  }

  #canvas-wrap { position: fixed; inset: 0; z-index: 1; }
  canvas { display: block; }

  #vignette {
    position: fixed; inset: 0; z-index: 2; pointer-events: none;
    background: radial-gradient(ellipse at center, transparent 40%, rgba(5,8,16,0.85) 100%);
  }

  #scanlines {
    position: fixed; inset: 0; z-index: 3; pointer-events: none;
    background: repeating-linear-gradient(0deg, rgba(46, 230, 255, 0.015) 0px, rgba(46, 230, 255, 0.015) 1px, transparent 1px, transparent 3px);
    opacity: 0.6;
  }

  .hud-panel {
    position: fixed;
    z-index: 5;
    background: linear-gradient(135deg, rgba(15, 35, 45, 0.35), rgba(10, 20, 30, 0.55));
    border: 1px solid var(--chrome);
    border-radius: 2px;
    backdrop-filter: blur(6px);
    color: var(--text);
    font-size: 11px;
    line-height: 1.5;
    box-shadow: 0 0 20px rgba(46, 230, 255, 0.06), inset 0 0 30px rgba(46,230,255,0.02);
  }

  .hud-panel::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, var(--core-blue), transparent);
    opacity: 0.5;
  }

  .hud-label {
    font-size: 9px;
    letter-spacing: 3px;
    color: var(--core-blue);
    text-transform: uppercase;
    margin-bottom: 8px;
    opacity: 0.8;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .hud-label::before {
    content: '';
    width: 4px; height: 4px;
    background: var(--core-blue);
    box-shadow: 0 0 6px var(--core-blue);
    border-radius: 50%;
  }

  #log-panel { flex: 1; position: relative; padding: 14px 16px; overflow-y: auto; min-height: 0; }
  #history-panel { flex: 1; position: relative; padding: 14px 16px; overflow-y: auto; min-height: 0; }

  .log-line, .history-line {
    color: var(--text-dim);
    margin: 3px 0;
    font-size: 10.5px;
    white-space: normal;
    word-break: break-word;
    overflow-wrap: break-word;
  }
  .history-goal { color: var(--amber); }

  #status-topleft { top: 24px; left: 24px; padding: 12px 16px; z-index: 5; }
  #status-topleft .state-text { font-size: 13px; letter-spacing: 2px; color: var(--core-blue); text-transform: uppercase; }
  #status-topleft .state-text.listening { color: var(--amber); }
  #status-topleft .sub { font-size: 10px; color: var(--text-dim); margin-top: 4px; }

  #control-bar {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, rgba(15, 35, 45, 0.5), rgba(10, 20, 30, 0.7));
    border: 1px solid var(--chrome);
    border-radius: 30px;
    padding: 8px 10px 8px 20px;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 30px rgba(46, 230, 255, 0.08);
    max-width: calc(100vw - 24px);
    box-sizing: border-box;
  }

  @media (max-width: 600px) {
    #control-bar {
      gap: 6px;
      padding: 6px 8px 6px 14px;
      bottom: 14px;
    }
    #goalInput { width: 38vw; min-width: 90px; font-size: 12px; }
    .hud-btn { width: 32px; height: 32px; font-size: 13px; }
  }

  #goalInput {
    background: transparent; border: none; outline: none;
    color: var(--text); font-family: inherit; font-size: 13px;
    width: 260px; letter-spacing: 0.5px;
  }
  #goalInput::placeholder { color: var(--text-dim); }

  .hud-btn {
    width: 38px; height: 38px; border-radius: 50%;
    border: 1px solid var(--chrome-bright);
    background: rgba(46, 230, 255, 0.05);
    color: var(--core-blue);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 15px;
    transition: all 0.2s ease;
  }
  .hud-btn:hover { background: rgba(46, 230, 255, 0.15); box-shadow: 0 0 12px rgba(46, 230, 255, 0.3); }
  .hud-btn.mic.recording {
    background: rgba(255, 157, 61, 0.2);
    border-color: var(--amber);
    color: var(--amber);
    animation: pulse-ring 1.4s infinite;
  }
  .hud-btn.conv.active {
    background: rgba(46, 230, 255, 0.2);
    border-color: var(--core-blue);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.4);
  }
  .hud-btn.cancel { color: #ff5555; border-color: #5c1a1a; }

  /* slide-out drawer for right panels */
  #right-section-wrap {
    transition: transform 0.35s ease;
    transform: translateX(0);
  }
  #right-section-wrap.drawer-closed {
    transform: translateX(calc(100% + 24px));
  }

  #drawerToggle {
    position: fixed;
    top: 50%;
    right: 24px;
    transform: translateY(-50%);
    z-index: 6;
    width: 32px;
    height: 56px;
    border-radius: 8px;
    border: 1px solid var(--chrome-bright);
    background: linear-gradient(135deg, rgba(15, 35, 45, 0.6), rgba(10, 20, 30, 0.8));
    color: var(--core-blue);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    backdrop-filter: blur(6px);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.1);
    transition: right 0.35s ease;
  }
  #drawerToggle.drawer-open {
    right: 308px;
  }
  .hud-btn.cancel:hover { background: rgba(255, 85, 85, 0.15); box-shadow: 0 0 12px rgba(255,85,85,0.3); }

  @keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(255, 157, 61, 0.5); }
    70% { box-shadow: 0 0 0 10px rgba(255, 157, 61, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 157, 61, 0); }
  }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--chrome-bright); }
</style>
</head>
<body>

<div id="canvas-wrap"><canvas id="sphere"></canvas></div>
<div id="vignette"></div>
<div id="scanlines"></div>

<div class="hud-panel" id="status-topleft">
  <div class="state-text" id="stateText">{{ 'IDLE' if running else 'OFFLINE' }}</div>
  <div class="sub">daemon {{ 'running' if running else 'stopped' }} &mdash; pid {{ pid if running else 'none' }}</div>
</div>

<div class="hud-panel" id="right-section-wrap" style="position:fixed; top:24px; right:24px; bottom:110px; width:280px; z-index:5; background:none; border:none; box-shadow:none; backdrop-filter:none; display:flex; flex-direction:column; gap:16px; padding:0;">
  <div class="hud-panel" id="log-panel">
    <div class="hud-label">Daemon Log</div>
    <div id="logLines">
      {% for line in logs %}
        <div class="log-line">{{ line }}</div>
      {% endfor %}
    </div>
  </div>

  <div class="hud-panel" id="history-panel">
    <div class="hud-label">Goal History</div>
    <div id="historyLines">
      {% for e in memory %}
        <div class="history-line" style="margin-bottom:10px;">
          <span class="history-goal">&rarr; {{ e.goal }}</span><br>
          {% if e.tasks %}
            <span style="font-size:9.5px">{{ e.tasks[0].result if e.tasks[0].result is defined else '' }}</span>
          {% endif %}
        </div>
      {% endfor %}
    </div>
  </div>
</div>

<div id="drawerToggle" onclick="toggleDrawer()">&#9664;</div>

<div id="control-bar">
  <input type="text" id="goalInput" placeholder="enter goal..." onkeydown="if(event.key==='Enter') sendGoal()">
  <div class="hud-btn send" onclick="sendGoal()" title="Send">&#9654;</div>
  <div class="hud-btn mic" id="micBtn" onclick="toggleRecording()" title="Voice">&#127908;</div>
  <div class="hud-btn conv" id="convBtn" onclick="toggleConversationMode()" title="Conversation mode">&#128172;</div>
  <div class="hud-btn cancel" onclick="cancelGoal()" title="Cancel">&#10005;</div>
</div>

<script>
/* ============ Particle Sphere Core ============ */
const canvas = document.getElementById('sphere');
const ctx = canvas.getContext('2d');
let W, H, CX, CY;
function resize() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; CX = W/2; CY = H/2; }
window.addEventListener('resize', resize);
resize();

let currentState = 'idle';
let displayColor = { r: 46, g: 230, b: 255 };
const stateColors = {
  idle:       { r: 46,  g: 230, b: 255 },
  listening:  { r: 255, g: 157, b: 61  },
  processing: { r: 130, g: 200, b: 255 },
  speaking:   { r: 255, g: 200, b: 100 }
};
const stateSpeed = { idle: 0.0018, listening: 0.005, processing: 0.008, speaking: 0.004 };
const stateLabel = { idle: 'IDLE', listening: 'LISTENING', processing: 'PROCESSING', speaking: 'SPEAKING' };

function setState(s) {
  currentState = s;
  const el = document.getElementById('stateText');
  el.textContent = stateLabel[s];
  el.className = 'state-text' + (s === 'listening' ? ' listening' : '');
}

const RINGS = 48, POINTS_PER_RING = 230, NOISE_POINTS = 2400, FILAMENTS = 600, SPIKES = 150, THICK_ARCS = 10;

// batched rendering (single stroke call per ring/arc, one combined call for filaments/spikes) made
// density no longer the bottleneck — keep a mild reduction on very small screens just as a safety margin
const isMobile = Math.min(window.innerWidth, window.innerHeight) < 500 || /Mobi|Android/i.test(navigator.userAgent);
const DENSITY_SCALE = isMobile ? 0.7 : 1.0;
const R_RINGS = Math.round(RINGS * DENSITY_SCALE);
const R_POINTS_PER_RING = Math.round(POINTS_PER_RING * DENSITY_SCALE);
const R_NOISE_POINTS = Math.round(NOISE_POINTS * DENSITY_SCALE);
const R_FILAMENTS = Math.round(FILAMENTS * DENSITY_SCALE);
const R_SPIKES = Math.round(SPIKES * DENSITY_SCALE);
const R_THICK_ARCS = Math.max(4, Math.round(THICK_ARCS * DENSITY_SCALE));

let rings = [];
function buildRings() {
  rings = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let r = 0; r < R_RINGS; r++) {
    const tiltX = (Math.random() - 0.5) * Math.PI;
    const tiltY = (Math.random() - 0.5) * Math.PI;
    const radius = baseRadius * (0.45 + Math.random() * 1.05);
    const pts = [];
    const n = R_POINTS_PER_RING - Math.floor(r * 2.5);
    const wobble = Math.random() * 0.15;
    for (let i = 0; i < n; i++) { const a = (i/n)*Math.PI*2; pts.push({ a, jitter: (Math.random()-0.5)*10, wob: wobble }); }
    rings.push({ tiltX, tiltY, radius, pts, speed: (Math.random()-0.5)*0.7+0.35, phase: Math.random()*Math.PI*2, thin: Math.random()>0.5 });
  }
}
buildRings();

let noisePts = [];
function buildNoise() {
  noisePts = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let i = 0; i < R_NOISE_POINTS; i++) {
    const theta = Math.random()*Math.PI*2, phi = Math.acos(2*Math.random()-1);
    const r = baseRadius * (0.3 + Math.pow(Math.random(),1.6)*1.4);
    noisePts.push({ theta, phi, r, tw: Math.random()*Math.PI*2, sz: 0.5+Math.random()*1.1 });
  }
}
buildNoise();

let burstPts = [];
function buildBurst() {
  burstPts = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let i = 0; i < Math.round(900 * DENSITY_SCALE); i++) {
    const theta = Math.random()*Math.PI*2, phi = Math.acos(2*Math.random()-1);
    const r = baseRadius * (0.5 + Math.random()*0.9);
    burstPts.push({ theta, phi, r, sz: 0.5+Math.random()*0.9 });
  }
}
buildBurst();

let filaments = [];
function buildFilaments() {
  filaments = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let i = 0; i < R_FILAMENTS; i++) {
    const theta0 = Math.random()*Math.PI*2, phi0 = Math.acos(2*Math.random()-1);
    const r0 = baseRadius * (0.35 + Math.random()*1.1);
    const arcLen = 0.25 + Math.random()*0.6, dir = Math.random()*Math.PI*2;
    const segs = 5 + Math.floor(Math.random()*5);
    filaments.push({ theta0, phi0, r0, arcLen, dir, segs, spinOffset: Math.random()*Math.PI*2, speedMul: 0.5+Math.random()*0.9 });
  }
}
buildFilaments();

let spikes = [];
function buildSpikes() {
  spikes = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let i = 0; i < R_SPIKES; i++) {
    const theta = Math.random()*Math.PI*2, phi = Math.acos(2*Math.random()-1);
    const len = baseRadius * (0.15 + Math.random()*0.55);
    const startR = baseRadius * (0.85 + Math.random()*0.3);
    spikes.push({ theta, phi, len, startR, tw: Math.random()*Math.PI*2 });
  }
}
buildSpikes();

let thickArcs = [];
function buildThickArcs() {
  thickArcs = [];
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * 0.20;
  for (let i = 0; i < R_THICK_ARCS; i++) {
    const tiltX = (Math.random()-0.5)*Math.PI, tiltY = (Math.random()-0.5)*Math.PI*0.6;
    const radius = baseRadius * (1.0 + Math.random()*0.55);
    const startA = Math.random()*Math.PI*2, sweep = Math.PI*(0.5+Math.random()*1.1);
    thickArcs.push({ tiltX, tiltY, radius, startA, sweep, speed: (Math.random()-0.5)*0.7+0.35, phase: Math.random()*Math.PI*2, width: 1.4+Math.random()*1.8 });
  }
}
buildThickArcs();

window.addEventListener('resize', () => { buildRings(); buildNoise(); buildBurst(); buildFilaments(); buildSpikes(); buildThickArcs(); });

let rotation = 0, pulsePhase = 0;

function project(x, y, z) { const fov = 480; const scale = fov/(fov+z); return { x: CX + x*scale, y: CY + y*scale, scale }; }
function rotatePoint(x, y, z, ry, rx) {
  let cosY=Math.cos(ry), sinY=Math.sin(ry);
  let x1 = x*cosY - z*sinY, z1 = x*sinY + z*cosY;
  let cosX=Math.cos(rx), sinX=Math.sin(rx);
  let y1 = y*cosX - z1*sinX, z2 = y*sinX + z1*cosX;
  return { x: x1, y: y1, z: z2 };
}

function blobPathFactory(ctx) {
  return function blobPath(cx, cy, baseR, seed, wobbleAmt, segments) {
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const a = (i/segments)*Math.PI*2;
      const n = Math.sin(a*3+seed+pulsePhase*1.5)*0.5 + Math.sin(a*5+seed*1.7-rotation*2)*0.3 + Math.sin(a*2-seed*0.6+pulsePhase)*0.4;
      const r = baseR*(1+n*wobbleAmt);
      const x = cx+Math.cos(a)*r, y = cy+Math.sin(a)*r;
      if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.closePath();
  };
}
const blobPath = blobPathFactory(ctx);

function draw() {
  ctx.clearRect(0, 0, W, H);
  const target = stateColors[currentState];
  const easeSpeed = 0.04;
  displayColor.r += (target.r - displayColor.r) * easeSpeed;
  displayColor.g += (target.g - displayColor.g) * easeSpeed;
  displayColor.b += (target.b - displayColor.b) * easeSpeed;
  const c = displayColor;
  const speed = stateSpeed[currentState];
  rotation += speed;
  pulsePhase += 0.03;

  const pulse = currentState === 'speaking' ? 0.7+Math.sin(pulsePhase*4)*0.3
              : currentState === 'listening' ? 0.8+Math.sin(pulsePhase*2)*0.2
              : 0.85+Math.sin(pulsePhase)*0.15;

  const coreR = Math.min(W, H) * 0.05 * pulse;

  const haloGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR*7);
  haloGrad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},0.35)`);
  haloGrad.addColorStop(0.25, `rgba(${c.r},${c.g},${c.b},0.12)`);
  haloGrad.addColorStop(0.6, `rgba(${c.r},${c.g},${c.b},0.04)`);
  haloGrad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = haloGrad;
  blobPath(CX, CY, coreR*7, 1.3, 0.16, 48);
  ctx.fill();

  const coronaGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR*3);
  coronaGrad.addColorStop(0, `rgba(${Math.min(255,c.r+60)},${Math.min(255,c.g+40)},${Math.min(255,c.b+30)},0.75)`);
  coronaGrad.addColorStop(0.4, `rgba(${c.r},${c.g},${c.b},0.35)`);
  coronaGrad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = coronaGrad;
  blobPath(CX, CY, coreR*3, 4.2, 0.22, 40);
  ctx.fill();

  ctx.save();
  ctx.translate(CX, CY);
  const surfR = coreR*1.15;
  const surfaceArcs = isMobile ? 10 : 26;
  for (let i = 0; i < surfaceArcs; i++) {
    const a0 = (i/surfaceArcs)*Math.PI*2 + rotation*1.8;
    const wobble = Math.sin(pulsePhase*2+i)*0.15;
    const rx = surfR*(0.85+wobble*0.3), ry = surfR*(0.5+Math.abs(Math.sin(a0*0.5))*0.4);
    ctx.strokeStyle = `rgba(${Math.min(255,c.r+30)},${Math.min(255,c.g+30)},${Math.min(255,c.b+30)},${0.18+Math.abs(wobble)*0.4})`;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.ellipse(0, 0, rx, ry, a0, 0, Math.PI*2);
    ctx.stroke();
  }
  ctx.restore();

  const hotGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR*0.5);
  hotGrad.addColorStop(0, `rgba(255,255,255,${0.95*pulse})`);
  hotGrad.addColorStop(0.5, `rgba(${Math.min(255,c.r+80)},${Math.min(255,c.g+80)},${Math.min(255,c.b+60)},${0.85*pulse})`);
  hotGrad.addColorStop(1, `rgba(${c.r},${c.g},${c.b},0)`);
  ctx.fillStyle = hotGrad;
  blobPath(CX, CY, coreR*0.5, 7.8, 0.09, 32);
  ctx.fill();

  // rings — batched: one path + one stroke per ring (was one stroke per segment — the real perf cost)
  rings.forEach(ring => {
    const ry = rotation*ring.speed + ring.phase, rx = ring.tiltX;
    const baseAlpha = ring.thin ? 0.16 : 0.24;
    const wobbleAmt = ring.radius*0.02;

    // average depth across the ring to pick one representative alpha/brightness (sacrifices per-segment
    // depth shading for a single batched stroke call — the big perf win)
    let avgDepth = 0;
    const projected = ring.pts.map(p => {
      const ow = Math.sin(pulsePhase*1.3+p.a*3+ring.phase)*wobbleAmt;
      const rr = ring.radius+p.jitter+ow;
      const x0 = Math.cos(p.a)*rr, y0 = Math.sin(p.a)*rr*Math.cos(ring.tiltY), z0 = Math.sin(p.a)*rr*Math.sin(ring.tiltY);
      const rp = rotatePoint(x0,y0,z0,ry,rx);
      const depth = (rp.z+ring.radius)/(ring.radius*2);
      avgDepth += depth;
      return project(rp.x, rp.y, rp.z);
    });
    avgDepth /= projected.length;

    if (!isMobile) {
      const glowAlpha = baseAlpha*(0.2+avgDepth*0.8)*0.5;
      ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${glowAlpha*pulse})`;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      projected.forEach((pt, i) => { if (i===0) ctx.moveTo(pt.x,pt.y); else ctx.lineTo(pt.x,pt.y); });
      ctx.stroke();
    }

    const bright = avgDepth > 0.75;
    const alpha = baseAlpha*(0.2+avgDepth*0.8);
    ctx.strokeStyle = bright
      ? `rgba(${Math.min(255,c.r+50)},${Math.min(255,c.g+50)},${Math.min(255,c.b+40)},${alpha*1.3*pulse})`
      : `rgba(${c.r},${c.g},${c.b},${alpha*pulse})`;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    projected.forEach((pt, i) => { if (i===0) ctx.moveTo(pt.x,pt.y); else ctx.lineTo(pt.x,pt.y); });
    ctx.stroke();
  });

  // thick arcs — batched single stroke per arc
  thickArcs.forEach(ta => {
    const ry = rotation*ta.speed + ta.phase, rx = ta.tiltX;
    const steps = isMobile ? 24 : 60;
    let avgDepth = 0;
    const pts = [];
    for (let i = 0; i <= steps; i++) {
      const a = ta.startA + (i/steps)*ta.sweep;
      const x0 = Math.cos(a)*ta.radius, y0 = Math.sin(a)*ta.radius*Math.cos(ta.tiltY), z0 = Math.sin(a)*ta.radius*Math.sin(ta.tiltY);
      const rp = rotatePoint(x0,y0,z0,ry,rx);
      const depth = (rp.z+ta.radius)/(ta.radius*2);
      avgDepth += depth;
      pts.push(project(rp.x, rp.y, rp.z));
    }
    avgDepth /= pts.length;
    const alpha = (0.12+avgDepth*0.35);
    ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${alpha*pulse})`;
    ctx.lineWidth = ta.width;
    ctx.beginPath();
    pts.forEach((pt, i) => { if (i===0) ctx.moveTo(pt.x,pt.y); else ctx.lineTo(pt.x,pt.y); });
    ctx.stroke();
  });

  // filaments — all combined into ONE path with disconnected subpaths, ONE stroke call total
  ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${0.28*pulse})`;
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  filaments.forEach(f => {
    const spin = rotation*f.speedMul + f.spinOffset;
    for (let s = 0; s <= f.segs; s++) {
      const t = s/f.segs;
      const theta = f.theta0 + Math.cos(f.dir)*f.arcLen*t + spin;
      const phi = f.phi0 + Math.sin(f.dir)*f.arcLen*t*0.6;
      const r = f.r0*(1+Math.sin(t*Math.PI)*0.08);
      const x0 = r*Math.sin(phi)*Math.cos(theta), y0 = r*Math.cos(phi), z0 = r*Math.sin(phi)*Math.sin(theta);
      const rp = rotatePoint(x0,y0,z0,0,0.25);
      const proj = project(rp.x, rp.y, rp.z);
      if (s===0) ctx.moveTo(proj.x, proj.y); else ctx.lineTo(proj.x, proj.y);
    }
  });
  ctx.stroke();

  // spikes — all combined into ONE path, ONE stroke call total
  ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${0.3*pulse})`;
  ctx.lineWidth = 0.7;
  ctx.beginPath();
  spikes.forEach(sp => {
    const theta = sp.theta + rotation*0.9, phi = sp.phi;
    const flicker = 0.5+Math.sin(pulsePhase*3+sp.tw)*0.5;
    const x0 = sp.startR*Math.sin(phi)*Math.cos(theta), y0 = sp.startR*Math.cos(phi), z0 = sp.startR*Math.sin(phi)*Math.sin(theta);
    const r1 = sp.startR + sp.len*flicker;
    const x1 = r1*Math.sin(phi)*Math.cos(theta), y1 = r1*Math.cos(phi), z1 = r1*Math.sin(phi)*Math.sin(theta);
    const rp0 = rotatePoint(x0,y0,z0,0,0.25), rp1 = rotatePoint(x1,y1,z1,0,0.25);
    const p0 = project(rp0.x,rp0.y,rp0.z), p1 = project(rp1.x,rp1.y,rp1.z);
    ctx.moveTo(p0.x,p0.y); ctx.lineTo(p1.x,p1.y);
  });
  ctx.stroke();

  noisePts.forEach(p => {
    const x0 = p.r*Math.sin(p.phi)*Math.cos(p.theta+rotation*0.7);
    const y0 = p.r*Math.cos(p.phi);
    const z0 = p.r*Math.sin(p.phi)*Math.sin(p.theta+rotation*0.7);
    const rp = rotatePoint(x0,y0,z0,rotation*0.4,0.3);
    const proj = project(rp.x, rp.y, rp.z);
    const tw = 0.3+Math.sin(pulsePhase*2+p.tw)*0.3+0.4;
    const depth = (rp.z+p.r)/(p.r*2);
    ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${tw*depth*pulse*0.75})`;
    ctx.fillRect(proj.x, proj.y, p.sz*proj.scale, p.sz*proj.scale);
  });

  const burstStrength = Math.max(0, (pulse-0.75)/0.25);
  if (burstStrength > 0.01) {
    burstPts.forEach(p => {
      const x0 = p.r*Math.sin(p.phi)*Math.cos(p.theta+rotation*0.7);
      const y0 = p.r*Math.cos(p.phi);
      const z0 = p.r*Math.sin(p.phi)*Math.sin(p.theta+rotation*0.7);
      const rp = rotatePoint(x0,y0,z0,rotation*0.4,0.3);
      const proj = project(rp.x, rp.y, rp.z);
      const depth = (rp.z+p.r)/(p.r*2);
      ctx.fillStyle = `rgba(${Math.min(255,c.r+40)},${Math.min(255,c.g+40)},${Math.min(255,c.b+30)},${burstStrength*depth*0.6})`;
      ctx.fillRect(proj.x, proj.y, p.sz*proj.scale, p.sz*proj.scale);
    });
  }

  requestAnimationFrame(draw);
}
draw();

/* ============ Real backend wiring ============ */
function sendGoal() {
  const goal = document.getElementById('goalInput').value.trim();
  if (!goal) return;
  fetch('/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({goal})})
    .then(() => { document.getElementById('goalInput').value = ''; setState('processing'); pollGoalStatus(goal, false); });
}

function cancelGoal() {
  fetch('/cancel', {method: 'POST'});
  setState('idle');
  conversationMode = false;
  convBtn.classList.remove('active');
}

let mediaRecorder = null, audioChunks = [], isRecording = false;
const micBtn = document.getElementById('micBtn');
const convBtn = document.getElementById('convBtn');
let conversationMode = false;

function toggleConversationMode() {
  conversationMode = !conversationMode;
  convBtn.classList.toggle('active', conversationMode);
}

async function toggleRecording() {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 48000, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000 });
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        sendVoiceCommand(blob);
      };
      mediaRecorder.start();
      isRecording = true;
      micBtn.classList.add('recording');
      setState('listening');
    } catch (err) {
      alert('Mic access failed: ' + err.message);
    }
  } else {
    mediaRecorder.stop();
    isRecording = false;
    micBtn.classList.remove('recording');
  }
}

function sendVoiceCommand(blob) {
  setState('processing');
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');
  fetch('/voice_command', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'error') { alert('Voice command failed: ' + data.message); setState('idle'); return; }
      if (data.text) pollGoalStatus(data.text, conversationMode);
    })
    .catch(err => { setState('idle'); alert('Upload failed: ' + err.message); });
}

function pollGoalStatus(goalText, relisten) {
  const interval = setInterval(() => {
    fetch('/goal_status', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({goal: goalText}) })
      .then(r => r.json())
      .then(data => {
        if (!data.pending) {
          clearInterval(interval);
          setState('idle');
          refreshPanels();
          if (relisten && conversationMode) setTimeout(() => toggleRecording(), 500);
        }
      })
      .catch(() => { clearInterval(interval); setState('idle'); });
  }, 1000);
}

function refreshPanels() {
  fetch(window.location.pathname)
    .then(r => r.text())
    .then(html => {
      const parser = new DOMParser();
      const newDoc = parser.parseFromString(html, "text/html");
      ["logLines", "historyLines"].forEach(id => {
        const oldEl = document.getElementById(id);
        const newEl = newDoc.getElementById(id);
        if (oldEl && newEl) oldEl.innerHTML = newEl.innerHTML;
      });
    })
    .catch(err => console.error("refresh failed", err));
}
setInterval(refreshPanels, 5000);

/* ============ Drawer toggle for right-side panels (mobile: default closed, desktop: default open) ============ */
const rightWrap = document.getElementById('right-section-wrap');
const drawerToggle = document.getElementById('drawerToggle');
let drawerOpen = !isMobile;

function applyDrawerState() {
  rightWrap.classList.toggle('drawer-closed', !drawerOpen);
  drawerToggle.classList.toggle('drawer-open', drawerOpen);
  drawerToggle.innerHTML = drawerOpen ? '&#9654;' : '&#9664;';
}
function toggleDrawer() {
  drawerOpen = !drawerOpen;
  applyDrawerState();
}
applyDrawerState();
</script>

</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML,
        running=is_running(),
        pid=get_pid(),
        pending=get_pending(),
        logs=get_last_logs(),
        memory=list(reversed(recall(10)))
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
        sp.run(["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path], capture_output=True, check=True)
    except sp.CalledProcessError as e:
        os.remove(webm_path)
        return jsonify({"status": "error", "message": f"ffmpeg conversion failed: {e.stderr.decode()[:200]}"})

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
    return jsonify({"pending": goal in pending})


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
        app.run(host="0.0.0.0", port=1367, debug=False, threaded=True, ssl_context=(cert_path, key_path))
    else:
        print("WARNING: TLS cert not found, falling back to HTTP")
        app.run(host="0.0.0.0", port=1367, debug=False, threaded=True)
