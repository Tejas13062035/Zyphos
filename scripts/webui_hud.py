import os
import glob
import json
from flask import Flask, render_template_string, jsonify, request
from core.daemon import is_running, get_pid
from memory.store import recall

app = Flask(__name__)

GOAL_FILE = os.path.expanduser("~/zyp/state/pending_goals.txt")
LOG_FILE = os.path.expanduser("~/zyp/logs/daemon.log")
SMART_MODE_FILE = os.path.expanduser("~/zyp/state/smart_mode")
SIDECAR_URL = "http://127.0.0.1:5000"


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
    --void: #04070d;
    --core-blue: #2ee6ff;
    --core-blue-dim: rgba(46, 230, 255, 0.22);
    --amber: #ff9d3d;
    --crimson: #ff2e4c;
    --chrome: #1a3a4a;
    --chrome-bright: #3a758c;
    --text: #a8e4f2;
    --text-dim: #4d7a8a;
    --panel-bg: linear-gradient(135deg, rgba(12, 30, 42, 0.48), rgba(6, 14, 22, 0.76));
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0; padding: 0;
    background: var(--void);
    overflow: hidden;
    height: 100%;
    font-family: 'Courier New', ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text);
    user-select: none;
  }

  #canvas-wrap { position: fixed; inset: 0; z-index: 1; }
  canvas { display: block; }

  #cad-grid {
    position: fixed; inset: 0; z-index: 2; pointer-events: none;
    background-image:
      linear-gradient(rgba(46, 230, 255, 0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(46, 230, 255, 0.025) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(circle at center, black 30%, transparent 85%);
    -webkit-mask-image: radial-gradient(circle at center, black 30%, transparent 85%);
  }

  #vignette {
    position: fixed; inset: 0; z-index: 2; pointer-events: none;
    background: radial-gradient(ellipse at center, transparent 38%, rgba(3, 6, 12, 0.9) 100%);
  }

  #scanlines {
    position: fixed; inset: 0; z-index: 3; pointer-events: none;
    background:
      repeating-linear-gradient(0deg, rgba(46, 230, 255, 0.018) 0px, rgba(46, 230, 255, 0.018) 1px, transparent 1px, transparent 3px),
      radial-gradient(circle at 50% 50%, rgba(46, 230, 255, 0.03), transparent 70%);
    opacity: 0.7;
  }

  /* ============ COLLAPSIBLE TOP CORE & STATE DOCK ============ */
  #top-dock-wrap {
    position: fixed; top: 0; left: 50%;
    transform: translateX(-50%) translateY(0);
    z-index: 20;
    display: flex; flex-direction: column; align-items: center;
    padding-top: 14px;
    pointer-events: none;
    transition: transform 0.35s ease;
  }
  #top-dock-wrap.dock-closed {
    transform: translateX(-50%) translateY(calc(-100% + 34px));
  }

  #proto-dock {
    pointer-events: auto;
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    background: rgba(6, 14, 22, 0.88);
    border: 1px solid var(--chrome-bright);
    padding: 5px 10px;
    border-radius: 3px;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 25px rgba(0, 0, 0, 0.7), 0 0 12px rgba(46, 230, 255, 0.12);
    max-width: calc(100vw - 24px);
    clip-path: polygon(8px 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%, 0 8px);
    transition: transform 0.35s ease, opacity 0.25s ease;
  }
  #top-dock-wrap.dock-closed #proto-dock {
    opacity: 0;
    pointer-events: none;
    transform: translateY(-14px);
  }

  .proto-group {
    display: flex; align-items: center; gap: 4px;
    padding-right: 8px; border-right: 1px solid rgba(46, 230, 255, 0.2);
  }
  .proto-group:last-child { border-right: none; padding-right: 0; }
  .proto-tag {
    font-size: 8.5px; letter-spacing: 1.5px; color: var(--text-dim);
    text-transform: uppercase; margin-right: 2px;
  }
  .p-btn {
    background: rgba(46, 230, 255, 0.06);
    border: 1px solid rgba(46, 230, 255, 0.25);
    color: var(--text);
    font-family: inherit; font-size: 9px; letter-spacing: 1px;
    padding: 3px 7px; cursor: pointer;
    text-transform: uppercase; transition: all 0.15s ease;
  }
  .p-btn:hover { background: rgba(46, 230, 255, 0.18); color: #fff; }
  .p-btn.active {
    background: rgba(46, 230, 255, 0.25);
    border-color: var(--core-blue);
    color: #fff;
    box-shadow: 0 0 10px rgba(46, 230, 255, 0.35);
  }
  .p-btn.amber-btn { border-color: rgba(255, 157, 61, 0.45); color: var(--amber); }
  .p-btn.amber-btn:hover { background: rgba(255, 157, 61, 0.2); }

  #topDrawerToggle {
    pointer-events: auto;
    margin-top: 6px;
    width: 58px; height: 26px;
    border: 1px solid var(--chrome-bright);
    background: rgba(10, 22, 32, 0.9);
    color: var(--core-blue);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 12px;
    backdrop-filter: blur(6px);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.15);
    transition: background 0.2s ease;
  }
  #topDrawerToggle:hover { background: rgba(46, 230, 255, 0.2); }

  /* ============ BASE HUD PANELS & BOOT ANIMATION ============ */
  .hud-panel {
    position: fixed; z-index: 5;
    background: var(--panel-bg);
    border: 1px solid var(--chrome);
    backdrop-filter: blur(8px);
    color: var(--text);
    font-size: 11px; line-height: 1.5;
    box-shadow: 0 0 24px rgba(46, 230, 255, 0.06), inset 0 0 24px rgba(46, 230, 255, 0.03);
    transition: opacity 0.35s ease, transform 0.35s ease, border-color 0.3s ease, background 0.3s ease;
  }

  body.booting .hud-panel,
  body.booting #control-bar {
    opacity: 0;
    transform: scale(0.94) translateY(8px);
  }

  .hud-panel::before, .hud-panel::after {
    content: ''; position: absolute; pointer-events: none;
    transition: all 0.3s ease;
  }

  body.hud-workshop .hud-panel {
    clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px));
    border-color: rgba(46, 230, 255, 0.32);
  }
  body.hud-workshop .hud-panel::before {
    top: 0; left: 0; width: 100%; height: 2px;
    background: linear-gradient(90deg, var(--core-blue), rgba(46,230,255,0.15) 65%, transparent);
  }
  body.hud-workshop .hud-panel::after {
    bottom: 0; right: 0; width: 38%; height: 2px;
    background: var(--core-blue);
    box-shadow: 0 0 8px var(--core-blue);
  }

  body.hud-palladium .hud-panel {
    border: 1px solid rgba(46, 230, 255, 0.45);
    border-top: 2px solid var(--crimson);
    background: linear-gradient(180deg, rgba(35, 10, 18, 0.62) 0%, rgba(8, 18, 28, 0.82) 32%);
    clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%);
  }
  body.hud-palladium .hud-label {
    background: rgba(255, 46, 76, 0.16);
    border-left: 3px solid var(--crimson);
    padding: 3px 8px;
    color: #ff8a9a;
  }
  body.hud-palladium .hud-label-left::before {
    background: var(--crimson);
    box-shadow: 0 0 6px var(--crimson);
  }

  body.hud-holo .hud-panel {
    background: rgba(4, 12, 20, 0.18) !important;
    border-color: rgba(46, 230, 255, 0.14) !important;
    box-shadow: none !important;
    backdrop-filter: blur(2px) !important;
  }
  body.hud-holo .hud-panel::before {
    top: 0; left: 0; width: 42px; height: 1px;
    background: var(--amber);
    box-shadow: 0 0 8px var(--amber);
  }
  body.hud-holo .hud-label {
    border-bottom: 1px dashed rgba(255, 157, 61, 0.35);
    padding-bottom: 4px;
    color: var(--amber);
  }

  .hud-label {
    font-size: 9px; letter-spacing: 2.6px;
    color: var(--core-blue);
    text-transform: uppercase;
    margin-bottom: 8px;
    display: flex; align-items: center; justify-content: space-between;
    gap: 6px;
  }
  .hud-label-left { display: flex; align-items: center; gap: 6px; }
  .hud-label-left::before {
    content: ''; width: 5px; height: 5px;
    background: var(--core-blue);
    box-shadow: 0 0 6px var(--core-blue);
  }
  .hud-code { font-size: 8px; color: var(--text-dim); letter-spacing: 1.5px; }

  /* ============ LEFT TELEMETRY DRAWER & PANELS ============ */
  #left-section-wrap {
    position: fixed; top: 24px; left: 24px; bottom: 24px; width: 268px;
    z-index: 5; pointer-events: none;
    display: flex; flex-direction: column; justify-content: space-between;
    transition: transform 0.35s ease; transform: translateX(0);
  }
  #left-section-wrap.drawer-closed {
    transform: translateX(calc(-100% - 36px));
  }

  #status-topleft, #stability-panel {
    position: relative; width: 100%;
    padding: 12px 16px; pointer-events: auto;
  }
  #stability-panel { padding: 10px 14px; }

  #leftDrawerToggle {
    position: fixed; top: 50%; left: 24px; transform: translateY(-50%);
    z-index: 15; width: 30px; height: 58px;
    border: 1px solid var(--chrome-bright);
    background: rgba(10, 22, 32, 0.9);
    color: var(--core-blue);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 14px;
    backdrop-filter: blur(6px);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.15);
    transition: left 0.35s ease, background 0.2s ease;
  }
  #leftDrawerToggle:hover { background: rgba(46, 230, 255, 0.2); }
  #leftDrawerToggle.drawer-open { left: 300px; }

  .top-row-flex { display: flex; justify-content: space-between; align-items: baseline; }
  #status-topleft .state-text {
    font-size: 15px; font-weight: bold; letter-spacing: 3px;
    color: var(--core-blue); text-transform: uppercase;
    text-shadow: 0 0 10px rgba(46, 230, 255, 0.4);
  }
  #status-topleft .state-text.listening { color: var(--amber); text-shadow: 0 0 10px rgba(255,157,61,0.5); }
  #status-topleft .sub { font-size: 10px; color: var(--text-dim); margin-top: 2px; }

  #stark-clock {
    font-size: 12px; letter-spacing: 2px; color: var(--amber);
    font-weight: bold;
  }
  body.hud-palladium #stark-clock { color: var(--crimson); }

  #diag-module {
    margin-top: 10px; padding-top: 8px;
    border-top: 1px solid rgba(46, 230, 255, 0.15);
  }
  .diag-row {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 8.5px; letter-spacing: 1.5px; color: var(--text-dim);
    margin: 4px 0;
  }
  .seg-bar { display: flex; gap: 2px; width: 116px; }
  .seg-bar i {
    flex: 1; height: 5px; background: rgba(46, 230, 255, 0.14);
    display: block; transition: background 0.2s ease;
  }
  .seg-bar i.on { background: var(--core-blue); box-shadow: 0 0 4px var(--core-blue); }
  .seg-bar i.warn { background: var(--crimson); box-shadow: 0 0 4px var(--crimson); }

  #element-strip {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 9px; gap: 8px;
  }
  .elem-box-wrap { display: flex; gap: 6px; }
  .elem-box {
    width: 32px; height: 32px;
    border: 1px solid var(--core-blue);
    background: rgba(46, 230, 255, 0.08);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    font-size: 11px; font-weight: bold; color: var(--core-blue);
    line-height: 1.1;
  }
  .elem-box small { font-size: 7px; font-weight: normal; color: var(--text-dim); }
  .elem-box.alert {
    border-color: var(--amber); color: var(--amber); background: rgba(255, 157, 61, 0.08);
  }
  body.hud-palladium .elem-box.alert {
    border-color: var(--crimson); color: var(--crimson); background: rgba(255, 46, 76, 0.12);
  }
  #sparkCanvas {
    flex: 1; height: 32px;
    border: 1px solid rgba(46, 230, 255, 0.18);
    background: rgba(4, 10, 16, 0.5);
  }

  /* ============ BOTTOM-LEFT RADIAL GAUGES & STABILITY MODULE ============ */
  .radial-row {
    display: flex; align-items: center; justify-content: space-between;
    gap: 6px; margin-top: 4px;
  }
  .radial-item {
    display: flex; flex-direction: column; align-items: center;
    font-size: 8px; letter-spacing: 1.2px; color: var(--text-dim);
  }
  .stab-footer {
    display: flex; justify-content: space-between; align-items: baseline;
    margin-top: 6px; padding-top: 6px;
    border-top: 1px solid rgba(46, 230, 255, 0.14);
  }
  .stab-val {
    font-size: 16px; font-weight: bold; letter-spacing: 2px;
    color: var(--core-blue);
  }
  body.hud-palladium .stab-val { color: var(--crimson); }

  /* ============ RIGHT DRAWER PANELS (Logs & History) ============ */
  #right-section-wrap {
    position: fixed; top: 24px; right: 24px; bottom: 96px; width: 295px;
    z-index: 5; display: flex; flex-direction: column; gap: 14px;
    transition: transform 0.35s ease; transform: translateX(0);
  }
  #right-section-wrap.drawer-closed {
    transform: translateX(calc(100% + 36px));
  }

  #log-panel, #history-panel {
    flex: 1; position: relative; padding: 14px 16px;
    overflow-y: auto; min-height: 0;
  }

  .scan-bar {
    position: absolute; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--core-blue), transparent);
    box-shadow: 0 0 10px var(--core-blue);
    opacity: 0.35; pointer-events: none;
    animation: panelScan 5s linear infinite;
  }
  body.hud-palladium .scan-bar {
    background: linear-gradient(90deg, transparent, var(--crimson), transparent);
    box-shadow: 0 0 10px var(--crimson);
  }
  @keyframes panelScan {
    0% { top: 0%; opacity: 0; }
    10% { opacity: 0.45; }
    90% { opacity: 0.45; }
    100% { top: 98%; opacity: 0; }
  }

  .log-line, .history-line {
    color: var(--text-dim); margin: 4px 0;
    font-size: 10.5px; word-break: break-word;
    border-left: 1px solid rgba(46, 230, 255, 0.18);
    padding-left: 7px;
  }
  .history-goal { color: var(--amber); font-weight: bold; }

  #drawerToggle {
    position: fixed; top: 50%; right: 24px; transform: translateY(-50%);
    z-index: 15; width: 30px; height: 58px;
    border: 1px solid var(--chrome-bright);
    background: rgba(10, 22, 32, 0.9);
    color: var(--core-blue);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 14px;
    backdrop-filter: blur(6px);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.15);
    transition: right 0.35s ease, background 0.2s ease;
  }
  #drawerToggle:hover { background: rgba(46, 230, 255, 0.2); }
  #drawerToggle.drawer-open { right: 326px; }

  /* ============ BOTTOM CONTROL BAR ============ */
  #control-bar {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    z-index: 10; display: flex; align-items: center; gap: 10px;
    background: linear-gradient(135deg, rgba(12, 30, 42, 0.75), rgba(6, 14, 22, 0.9));
    border: 1px solid var(--chrome-bright);
    border-radius: 4px;
    padding: 7px 10px 7px 18px;
    backdrop-filter: blur(12px);
    box-shadow: 0 0 30px rgba(46, 230, 255, 0.12);
    max-width: calc(100vw - 24px);
    clip-path: polygon(10px 0, calc(100% - 10px) 0, 100% 10px, 100% calc(100% - 10px), calc(100% - 10px) 100%, 10px 100%, 0 calc(100% - 10px), 0 10px);
    transition: opacity 0.35s ease, transform 0.35s ease;
  }

  #goalInput {
    background: transparent; border: none; outline: none;
    color: var(--text); font-family: inherit; font-size: 13px;
    width: 230px; letter-spacing: 0.5px;
  }
  #goalInput::placeholder { color: var(--text-dim); }

  #voiceWaveCanvas {
    width: 60px; height: 26px;
    border-left: 1px solid rgba(46, 230, 255, 0.2);
    border-right: 1px solid rgba(46, 230, 255, 0.2);
  }

  .hud-btn {
    width: 36px; height: 36px; border-radius: 4px;
    border: 1px solid var(--chrome-bright);
    background: rgba(46, 230, 255, 0.06);
    color: var(--core-blue);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 14px; transition: all 0.2s ease;
  }
  .hud-btn:hover { background: rgba(46, 230, 255, 0.18); box-shadow: 0 0 12px rgba(46, 230, 255, 0.35); }
  .hud-btn.mic.recording {
    background: rgba(255, 157, 61, 0.2); border-color: var(--amber); color: var(--amber);
    animation: pulse-ring 1.4s infinite;
  }
  .hud-btn.conv.active {
    background: rgba(46, 230, 255, 0.22); border-color: var(--core-blue);
    box-shadow: 0 0 12px rgba(46, 230, 255, 0.4);
  }
  .hud-btn.cancel { color: var(--crimson); border-color: rgba(255, 46, 76, 0.45); }
  .hud-btn.cancel:hover { background: rgba(255, 46, 76, 0.15); box-shadow: 0 0 12px rgba(255, 46, 76, 0.35); }

  @keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(255, 157, 61, 0.5); }
    70% { box-shadow: 0 0 0 10px rgba(255, 157, 61, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 157, 61, 0); }
  }

  @media (max-width: 760px) {
    #stability-panel { display: none; }
    #proto-dock { padding: 4px 6px; }
    #left-section-wrap { top: 82px; width: 225px; }
    #leftDrawerToggle.drawer-open { left: 256px; }
    #goalInput { width: 32vw; min-width: 85px; font-size: 12px; }
  }

  @media (max-width: 400px) {
    #voiceWaveCanvas { display: none; }
    #goalInput { min-width: 70px; }
  }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--chrome-bright); }
</style>
</head>
<body class="hud-workshop">

<div id="canvas-wrap"><canvas id="sphere"></canvas></div>
<div id="cad-grid"></div>
<div id="vignette"></div>
<div id="scanlines"></div>

<!-- COLLAPSIBLE TOP MODE & STATE SWITCHER DOCK -->
<div id="top-dock-wrap">
  <div id="proto-dock">
    <div class="proto-group">
      <span class="proto-tag">CORE:</span>
      <button class="p-btn active" id="pre-1" onclick="applyPreset(1)">1: Reactor + Sphere</button>
      <button class="p-btn" id="pre-2" onclick="applyPreset(2)">2: Palladium Sim</button>
      <button class="p-btn" id="pre-3" onclick="applyPreset(3)">3: 3D Holo CAD</button>
      <button class="p-btn" id="pre-4" onclick="applyPreset(4)">4: Classic Sphere</button>
    </div>
    <div class="proto-group">
      <span class="proto-tag">STATE:</span>
      <button class="p-btn" onclick="setState('idle')">Idle</button>
      <button class="p-btn" onclick="setState('listening')">Listen</button>
      <button class="p-btn" onclick="setState('processing')">Process</button>
      <button class="p-btn" onclick="setState('speaking')">Speak</button>
    </div>
    <div class="proto-group">
      <button class="p-btn amber-btn" onclick="triggerBootSequence()">&#9889; Boot Anim</button>
    </div>
  </div>
  <div id="topDrawerToggle" onclick="toggleTopDock()" title="Toggle Core & State Controls">&#9650;</div>
</div>

<!-- LEFT TELEMETRY & DIAGNOSTIC DRAWER -->
<div id="left-section-wrap">
  <div class="hud-panel" id="status-topleft">
    <div class="hud-label">
      <span class="hud-label-left">Core Telemetry</span>
      <span class="hud-code">QP1_50500_SIM</span>
    </div>
    <div class="top-row-flex">
      <div class="state-text" id="stateText">{{ 'IDLE' if running else 'OFFLINE' }}</div>
      <div id="stark-clock">07:23:14</div>
    </div>
    <div class="sub" id="daemonSub">daemon {{ 'running' if running else 'stopped' }} &mdash; pid {{ pid if running else 'none' }}</div>

    <div id="diag-module">
      <div class="diag-row">
        <span>COMPATIBILITY</span>
        <div class="seg-bar" id="bar-compat"></div>
      </div>
      <div class="diag-row">
        <span>STABILITY</span>
        <div class="seg-bar" id="bar-stab"></div>
      </div>
      <div class="diag-row">
        <span>REACTIVITY</span>
        <div class="seg-bar" id="bar-react"></div>
      </div>
      <div id="element-strip">
        <div class="elem-box-wrap">
          <div class="elem-box">Zp<small>46</small></div>
          <div class="elem-box alert">Pd<small>24%</small></div>
        </div>
        <canvas id="sparkCanvas" width="126" height="32"></canvas>
      </div>
    </div>
  </div>

  <div class="hud-panel" id="stability-panel">
    <div class="hud-label">
      <span class="hud-label-left">Diagnostic Matrix</span>
      <span class="hud-code">MK-IV</span>
    </div>
    <div class="radial-row">
      <div class="radial-item">
        <canvas id="radCanvas1" width="64" height="64"></canvas>
        <span>CORE SYNC</span>
      </div>
      <div class="radial-item">
        <canvas id="radCanvas2" width="64" height="64"></canvas>
        <span>NEURAL LOAD</span>
      </div>
      <div class="radial-item">
        <canvas id="radCanvas3" width="64" height="64"></canvas>
        <span>TOXICITY</span>
      </div>
    </div>
    <div class="stab-footer">
      <span style="font-size:9px; color:var(--text-dim); letter-spacing:1.5px;">HEALTH STABILITY</span>
      <span class="stab-val" id="stabReadout">94%</span>
    </div>
  </div>
</div>

<div id="leftDrawerToggle" onclick="toggleLeftDrawer()" title="Toggle Telemetry Panels">&#9664;</div>

<!-- RIGHT LOG & GOAL HISTORY DRAWER -->
<div id="right-section-wrap">
  <div class="hud-panel" id="log-panel">
    <div class="scan-bar"></div>
    <div class="hud-label">
      <span class="hud-label-left">Daemon Log</span>
      <span class="hud-code">VOL.03</span>
    </div>
    <div id="logLines">
      {% for line in logs %}
        <div class="log-line">{{ line }}</div>
      {% endfor %}
    </div>
  </div>

  <div class="hud-panel" id="history-panel">
    <div class="scan-bar" style="animation-delay: -2.5s;"></div>
    <div class="hud-label">
      <span class="hud-label-left">Goal History</span>
      <span class="hud-code">MEM.10</span>
    </div>
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

<div id="drawerToggle" onclick="toggleDrawer()" title="Toggle Logs & Goal History">&#9654;</div>

<!-- BOTTOM CONTROL BAR -->
<div id="control-bar">
  <input type="text" id="goalInput" placeholder="enter directive..." onkeydown="if(event.key==='Enter') sendGoal()">
  <canvas id="voiceWaveCanvas" width="60" height="26"></canvas>
  <div class="hud-btn send" onclick="sendGoal()" title="Send">&#9654;</div>
  <div class="hud-btn mic" id="micBtn" onclick="toggleRecording()" title="Voice">&#127908;</div>
  <div class="hud-btn conv" id="convBtn" onclick="toggleConversationMode()" title="Conversation mode">&#128172;</div>
  <div class="hud-btn cancel" onclick="cancelGoal()" title="Cancel">&#10005;</div>
</div>

<script>
/* ============ 1. GLOBAL STATE & DOM REFERENCES ============ */
const isMobile = Math.min(window.innerWidth, window.innerHeight) < 500 || /Mobi|Android/i.test(navigator.userAgent);

const BASE_RADIUS_SCALE = 0.200;
const INNER_CORE_SCALE = 0.0375;

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

let activePreset = 1;
let bootSpinBoost = 0;
let rotation = 0;
let pulsePhase = 0;

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let conversationMode = false;
let audioCtx = null;
let analyser = null;
let freqData = null;
let liveMicEnergy = 0;

const micBtn = document.getElementById('micBtn');
const convBtn = document.getElementById('convBtn');
const rightWrap = document.getElementById('right-section-wrap');
const drawerToggle = document.getElementById('drawerToggle');
const leftWrap = document.getElementById('left-section-wrap');
const leftDrawerToggle = document.getElementById('leftDrawerToggle');
const topDockWrap = document.getElementById('top-dock-wrap');
const topDrawerToggle = document.getElementById('topDrawerToggle');

let drawerOpen = !isMobile;
let leftDrawerOpen = !isMobile;
let topDockOpen = !isMobile;

/* ============ 2. STANDALONE PREVIEW FALLBACK ============ */
(function initPreviewFallback() {
  const st = document.getElementById('stateText');
  const openTag = '{' + '{';
  if (st && st.textContent.indexOf(openTag) !== -1) {
    st.textContent = 'IDLE';
    document.getElementById('daemonSub').innerHTML = 'daemon running &mdash; pid 4819';
    document.getElementById('logLines').innerHTML = [
      '[19:42:02] CORE: Z.Y.P.H.O.S daemon initialized (pid 4819)',
      '[19:42:04] STT: Whisper audio pipeline ready (16kHz mono)',
      '[19:42:09] MEM: Loaded 10 historical goal vectors',
      '[19:42:15] NET: Tailscale TLS listener bound :1367',
      '[19:42:21] WATCHDOG: Smart mode active — awaiting directive'
    ].map(l => '<div class="log-line">' + l + '</div>').join('');
    document.getElementById('historyLines').innerHTML = [
      { g: 'Compile local LLM weights & run latency benchmark', r: 'Completed in 4.2s — 68.4 tok/s avg' },
      { g: 'Scan system thermal & GPU VRAM telemetry', r: 'VRAM 6.1/16GB | Core 54°C nominal' },
      { g: 'Sync Zenodo preprint metadata repository', r: '4 records verified — DOI checksums OK' }
    ].map(item =>
      '<div class="history-line" style="margin-bottom:10px;">' +
        '<span class="history-goal">&rarr; ' + item.g + '</span><br>' +
        '<span style="font-size:9.5px">' + item.r + '</span>' +
      '</div>'
    ).join('');
  }
})();

/* ============ 3. LEFT, RIGHT & TOP DRAWER TOGGLES ============ */
function applyDrawerState() {
  rightWrap.classList.toggle('drawer-closed', !drawerOpen);
  drawerToggle.classList.toggle('drawer-open', drawerOpen);
  drawerToggle.innerHTML = drawerOpen ? '&#9654;' : '&#9664;';
}
function toggleDrawer() {
  drawerOpen = !drawerOpen;
  applyDrawerState();
}

function applyLeftDrawerState() {
  leftWrap.classList.toggle('drawer-closed', !leftDrawerOpen);
  leftDrawerToggle.classList.toggle('drawer-open', leftDrawerOpen);
  leftDrawerToggle.innerHTML = leftDrawerOpen ? '&#9664;' : '&#9654;';
}
function toggleLeftDrawer() {
  leftDrawerOpen = !leftDrawerOpen;
  applyLeftDrawerState();
}

function applyTopDockState() {
  topDockWrap.classList.toggle('dock-closed', !topDockOpen);
  topDrawerToggle.innerHTML = topDockOpen ? '&#9650;' : '&#9660;';
}
function toggleTopDock() {
  topDockOpen = !topDockOpen;
  applyTopDockState();
}

applyDrawerState();
applyLeftDrawerState();
applyTopDockState();

/* ============ 4. HUD DIAGNOSTIC BARS, CLOCK & RADIAL GAUGES ============ */
function buildSegBar(id, total, active, warnFrom) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const seg = document.createElement('i');
    if (i < active) seg.className = (i >= warnFrom) ? 'warn' : 'on';
    el.appendChild(seg);
  }
}
buildSegBar('bar-compat', 14, 12, 14);
buildSegBar('bar-stab', 14, 12, 13);
buildSegBar('bar-react', 14, 13, 9);

setInterval(() => {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const clk = document.getElementById('stark-clock');
  if (clk) clk.textContent = pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
}, 250);

const sparkCtx = document.getElementById('sparkCanvas').getContext('2d');
const waveCtx = document.getElementById('voiceWaveCanvas').getContext('2d');
const radCtxs = [
  document.getElementById('radCanvas1').getContext('2d'),
  document.getElementById('radCanvas2').getContext('2d'),
  document.getElementById('radCanvas3').getContext('2d')
];
let sparkHistory = Array.from({length: 32}, () => 0.4 + Math.random()*0.3);

function connectMicVisualizer(stream) {
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    src.connect(analyser);
    freqData = new Uint8Array(analyser.frequencyBinCount);
  } catch (e) {
    console.warn("WebAudio visualizer unavailable:", e);
  }
}

function drawRadialGauge(rCtx, val, labelPct, colorStr, rotOffset) {
  rCtx.clearRect(0, 0, 64, 64);
  const cx = 32, cy = 32, r = 24;
  rCtx.strokeStyle = 'rgba(46, 230, 255, 0.14)';
  rCtx.lineWidth = 3.5;
  rCtx.beginPath();
  rCtx.arc(cx, cy, r, 0, Math.PI * 2);
  rCtx.stroke();

  rCtx.strokeStyle = colorStr;
  rCtx.lineWidth = 3.5;
  rCtx.beginPath();
  rCtx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * (val / 100)));
  rCtx.stroke();

  rCtx.save();
  rCtx.translate(cx, cy);
  rCtx.rotate(rotOffset);
  rCtx.strokeStyle = colorStr;
  rCtx.lineWidth = 1;
  rCtx.setLineDash([3, 4]);
  rCtx.beginPath();
  rCtx.arc(0, 0, r - 6, 0, Math.PI * 2);
  rCtx.stroke();
  rCtx.restore();

  rCtx.fillStyle = '#d4f6ff';
  rCtx.font = 'bold 10px Courier New';
  rCtx.textAlign = 'center';
  rCtx.textBaseline = 'middle';
  rCtx.fillText(labelPct + '%', cx, cy);
}

function drawMiniGraphs(c) {
  if (isRecording && analyser && freqData) {
    analyser.getByteFrequencyData(freqData);
    let sum = 0;
    for (let i = 0; i < freqData.length; i++) sum += freqData[i];
    liveMicEnergy = (sum / (freqData.length * 255));
  } else {
    liveMicEnergy = currentState === 'speaking' ? 0.55 + Math.sin(pulsePhase * 5) * 0.35
                  : currentState === 'processing' ? 0.45 + Math.sin(pulsePhase * 3) * 0.25
                  : 0.12;
  }

  sparkHistory.push(0.2 + Math.random() * 0.3 + liveMicEnergy * 0.45);
  if (sparkHistory.length > 32) sparkHistory.shift();

  sparkCtx.clearRect(0, 0, 126, 32);
  sparkCtx.strokeStyle = `rgba(${c.r},${c.g},${c.b},0.85)`;
  sparkCtx.lineWidth = 1.4;
  sparkCtx.beginPath();
  sparkHistory.forEach((v, i) => {
    const x = (i / 31) * 126, y = 30 - Math.min(1, v) * 26;
    if (i === 0) sparkCtx.moveTo(x, y); else sparkCtx.lineTo(x, y);
  });
  sparkCtx.stroke();

  waveCtx.clearRect(0, 0, 60, 26);
  const bars = 12;
  for (let i = 0; i < bars; i++) {
    let norm = 0.2;
    if (isRecording && freqData) {
      norm = Math.max(0.12, freqData[i % freqData.length] / 255);
    } else {
      const amp = currentState === 'idle' ? 0.22 : 0.85;
      norm = Math.abs(Math.sin(pulsePhase * 3.2 + i * 0.65)) * amp;
    }
    const h = Math.max(3, norm * 22);
    waveCtx.fillStyle = `rgba(${c.r},${c.g},${c.b},0.85)`;
    waveCtx.fillRect(4 + i * 4.5, 13 - h / 2, 2.8, h);
  }

  const colStr = `rgba(${c.r},${c.g},${c.b},0.9)`;
  const warnCol = activePreset === 2 ? 'rgba(255, 46, 76, 0.9)' : colStr;
  const g1 = Math.round(92 + Math.sin(pulsePhase) * 4);
  const g2 = Math.round(48 + liveMicEnergy * 42);
  const g3 = activePreset === 2 ? Math.round(24 + Math.sin(pulsePhase * 0.8) * 2) : 12;
  drawRadialGauge(radCtxs[0], g1, g1, colStr, rotation * 2);
  drawRadialGauge(radCtxs[1], g2, g2, colStr, -rotation * 3);
  drawRadialGauge(radCtxs[2], g3, g3, warnCol, rotation * 1.5);
}

/* ============ 5. PRESET & STATE CONTROLLERS ============ */
function setState(s) {
  currentState = s;
  const el = document.getElementById('stateText');
  el.textContent = stateLabel[s];
  el.className = 'state-text' + (s === 'listening' ? ' listening' : '');
}

function applyPreset(n) {
  activePreset = n;
  document.querySelectorAll('#proto-dock .p-btn[id^="pre-"]').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('pre-' + n);
  if (btn) btn.classList.add('active');

  document.body.classList.remove('hud-workshop', 'hud-palladium', 'hud-holo');
  const stabEl = document.getElementById('stabReadout');

  if (n === 1) {
    document.body.classList.add('hud-workshop');
    if (stabEl) stabEl.textContent = '94%';
    buildSegBar('bar-stab', 14, 12, 13);
  } else if (n === 2) {
    document.body.classList.add('hud-palladium');
    if (stabEl) stabEl.textContent = '67%';
    buildSegBar('bar-stab', 14, 7, 5);
  } else if (n === 3) {
    document.body.classList.add('hud-holo');
    if (stabEl) stabEl.textContent = '99%';
    buildSegBar('bar-stab', 14, 14, 14);
  } else {
    document.body.classList.add('hud-workshop');
    if (stabEl) stabEl.textContent = '96%';
    buildSegBar('bar-stab', 14, 13, 14);
  }
}

function triggerBootSequence() {
  document.body.classList.add('booting');
  bootSpinBoost = 0.048;
  setTimeout(() => {
    document.body.classList.remove('booting');
  }, 220);
}

/* ============ 6. CORE & RING ENGINE ============ */
const canvas = document.getElementById('sphere');
const ctx = canvas.getContext('2d');
let W, H, CX, CY;
function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
  CX = W / 2;
  CY = H / 2;
}
window.addEventListener('resize', resize);
resize();

const RINGS = 62;
const POINTS_PER_RING = 240;
const NOISE_POINTS = 4400;
const CORE_GRANULES = 900;
const FILAMENTS = 950;
const SPIKES = 310;
const THICK_ARCS = 20;

const DENSITY_SCALE = isMobile ? 0.65 : 1.0;
const R_RINGS = Math.round(RINGS * DENSITY_SCALE);
const R_POINTS_PER_RING = Math.round(POINTS_PER_RING * DENSITY_SCALE);
const R_NOISE_POINTS = Math.round(NOISE_POINTS * DENSITY_SCALE);
const R_CORE_GRANULES = Math.round(CORE_GRANULES * DENSITY_SCALE);
const R_FILAMENTS = Math.round(FILAMENTS * DENSITY_SCALE);
const R_SPIKES = Math.round(SPIKES * DENSITY_SCALE);
const R_THICK_ARCS = Math.max(8, Math.round(THICK_ARCS * DENSITY_SCALE));

let rings = [], noisePts = [], coreGranules = [], burstPts = [], filaments = [], spikes = [], thickArcs = [], holoNodes = [];

function buildGeometry() {
  const baseRadius = Math.min(window.innerWidth, window.innerHeight) * BASE_RADIUS_SCALE;

  rings = [];
  for (let r = 0; r < R_RINGS; r++) {
    const tiltX = (Math.random() - 0.5) * Math.PI;
    const tiltY = (Math.random() - 0.5) * Math.PI;
    const radius = baseRadius * (0.56 + Math.random() * 1.18);
    const pts = [];
    const n = Math.max(80, R_POINTS_PER_RING - Math.floor(r * 1.8));
    const wobble = Math.random() * 0.18;
    for (let i = 0; i < n; i++) {
      pts.push({ a: (i / n) * Math.PI * 2, jitter: (Math.random() - 0.5) * 10.5, wob: wobble });
    }
    rings.push({
      tiltX, tiltY, radius, pts,
      speed: (Math.random() - 0.5) * 0.75 + 0.35,
      phase: Math.random() * Math.PI * 2,
      thin: Math.random() > 0.55
    });
  }

  noisePts = [];
  for (let i = 0; i < R_NOISE_POINTS; i++) {
    const theta = Math.random() * Math.PI * 2, phi = Math.acos(2 * Math.random() - 1);
    const r = baseRadius * (0.42 + Math.pow(Math.random(), 1.35) * 1.42);
    noisePts.push({
      theta, phi, r,
      tw: Math.random() * Math.PI * 2,
      sz: 1.0 + Math.random() * 2.0,
      hot: Math.random() > 0.82
    });
  }

  coreGranules = [];
  for (let i = 0; i < R_CORE_GRANULES; i++) {
    const theta = Math.random() * Math.PI * 2, phi = Math.acos(2 * Math.random() - 1);
    const r = baseRadius * (0.02 + Math.pow(Math.random(), 1.9) * 0.21);
    coreGranules.push({
      theta, phi, r,
      tw: Math.random() * Math.PI * 2,
      sz: 1.2 + Math.random() * 2.2,
      speedMul: 1.2 + Math.random() * 1.5
    });
  }

  burstPts = [];
  for (let i = 0; i < Math.round(1800 * DENSITY_SCALE); i++) {
    const theta = Math.random() * Math.PI * 2, phi = Math.acos(2 * Math.random() - 1);
    const r = baseRadius * (0.52 + Math.random() * 1.12);
    burstPts.push({ theta, phi, r, sz: 1.05 + Math.random() * 1.8 });
  }

  filaments = [];
  for (let i = 0; i < R_FILAMENTS; i++) {
    const theta0 = Math.random() * Math.PI * 2, phi0 = Math.acos(2 * Math.random() - 1);
    const r0 = baseRadius * (0.45 + Math.random() * 1.20);
    const arcLen = 0.28 + Math.random() * 0.68, dir = Math.random() * Math.PI * 2;
    const segs = 5 + Math.floor(Math.random() * 5);
    filaments.push({ theta0, phi0, r0, arcLen, dir, segs, spinOffset: Math.random() * Math.PI * 2, speedMul: 0.5 + Math.random() * 0.95 });
  }

  spikes = [];
  for (let i = 0; i < R_SPIKES; i++) {
    const theta = Math.random() * Math.PI * 2, phi = Math.acos(2 * Math.random() - 1);
    const len = baseRadius * (0.55 + Math.random() * 1.45);
    const startR = baseRadius * (0.64 + Math.random() * 0.56);
    spikes.push({ theta, phi, len, startR, tw: Math.random() * Math.PI * 2 });
  }

  thickArcs = [];
  for (let i = 0; i < R_THICK_ARCS; i++) {
    const tiltX = (Math.random() - 0.5) * Math.PI, tiltY = (Math.random() - 0.5) * Math.PI * 0.65;
    const radius = baseRadius * (0.92 + Math.random() * 0.76);
    const startA = Math.random() * Math.PI * 2, sweep = Math.PI * (0.55 + Math.random() * 1.15);
    thickArcs.push({
      tiltX, tiltY, radius, startA, sweep,
      speed: (Math.random() - 0.5) * 0.75 + 0.35,
      phase: Math.random() * Math.PI * 2,
      width: 2.5 + Math.random() * 3.0
    });
  }

  const labels = ['SYS.CORE // 01', 'MEM.VEC // 10', 'STT.PIPE // 48K', 'ARC.STATOR // MK4', 'TLS.NODE // 1367', 'PALLADIUM // 24%'];
  holoNodes = labels.map((lbl, idx) => ({
    theta: (idx / labels.length) * Math.PI * 2,
    phi: 0.9 + (idx % 3 - 1) * 0.45,
    r: baseRadius * (1.42 + (idx % 2) * 0.24),
    label: lbl
  }));
}
buildGeometry();
let _lastW = window.innerWidth;
window.addEventListener('resize', () => {
  if (window.innerWidth === _lastW) return;
  _lastW = window.innerWidth;
  buildGeometry();
});

function project(x, y, z) {
  const fov = 480;
  const scale = fov / (fov + z);
  return { x: CX + x * scale, y: CY + y * scale, scale };
}

function rotatePoint(x, y, z, ry, rx) {
  let cosY = Math.cos(ry), sinY = Math.sin(ry);
  let x1 = x * cosY - z * sinY, z1 = x * sinY + z * cosY;
  let cosX = Math.cos(rx), sinX = Math.sin(rx);
  let y1 = y * cosX - z1 * sinX, z2 = y * sinX + z1 * cosX;
  return { x: x1, y: y1, z: z2 };
}

const blobPath = (function(ctx) {
  return function(cx, cy, baseR, seed, wobbleAmt, segments) {
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      const n = Math.sin(a * 3 + seed + pulsePhase * 1.6) * 0.42
              + Math.sin(a * 5 + seed * 1.7 - rotation * 2.2) * 0.28
              + Math.sin(a * 2 - seed * 0.6 + pulsePhase) * 0.30
              + Math.sin(a * 9 + seed * 2.3 + pulsePhase * 2.8) * 0.16
              + Math.cos(a * 13 - rotation * 3.5 + seed) * 0.10;
      const r = baseR * (1 + n * wobbleAmt);
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
  };
})(ctx);

function drawArcReactorOverlay(c, pulse) {
  if (activePreset === 4) return;
  const baseR = Math.min(W, H) * BASE_RADIUS_SCALE;
  ctx.save();
  ctx.translate(CX, CY);

  const outerCadR = baseR * 1.52;
  ctx.save();
  ctx.rotate(rotation * 0.35);
  ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},0.34)`;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < 72; i++) {
    const a = (i / 72) * Math.PI * 2;
    const len = (i % 6 === 0) ? 16 : 7;
    ctx.moveTo(Math.cos(a) * outerCadR, Math.sin(a) * outerCadR);
    ctx.lineTo(Math.cos(a) * (outerCadR + len), Math.sin(a) * (outerCadR + len));
  }
  ctx.stroke();
  ctx.restore();

  const coilR = baseR * 1.25 * (0.96 + pulse * 0.04);
  ctx.save();
  ctx.rotate(-rotation * 0.45);
  const coils = 10;
  for (let i = 0; i < coils; i++) {
    const a0 = (i / coils) * Math.PI * 2;
    const a1 = a0 + (Math.PI * 2 / coils) * 0.58;
    ctx.strokeStyle = activePreset === 3
      ? `rgba(255, 157, 61, ${0.46 * pulse})`
      : `rgba(${c.r},${c.g},${c.b},${0.46 * pulse})`;
    ctx.lineWidth = 6.0;
    ctx.beginPath();
    ctx.arc(0, 0, coilR, a0, a1);
    ctx.stroke();
  }
  ctx.restore();

  if (activePreset === 2) {
    ctx.fillStyle = 'rgba(255, 46, 76, 0.95)';
    ctx.font = 'bold 13px Courier New';
    ctx.textAlign = 'center';
    ctx.fillText('PALLADIUM TOXICITY: 24%', 0, -outerCadR - 20);
  }

  ctx.restore();
}

function drawHoloCallouts(c) {
  if (activePreset !== 1 && activePreset !== 3) return;
  ctx.save();
  ctx.font = '9px Courier New';
  holoNodes.forEach((hn, idx) => {
    const theta = hn.theta + rotation * 0.45;
    const x0 = hn.r * Math.sin(hn.phi) * Math.cos(theta);
    const y0 = hn.r * Math.cos(hn.phi);
    const z0 = hn.r * Math.sin(hn.phi) * Math.sin(theta);
    const rp = rotatePoint(x0, y0, z0, 0, 0.25);
    if (rp.z > 60) return;
    const proj = project(rp.x, rp.y, rp.z);

    const col = (activePreset === 3 && idx % 2 === 0)
      ? 'rgba(255, 157, 61, 0.82)'
      : `rgba(${c.r},${c.g},${c.b},0.78)`;

    ctx.strokeStyle = col;
    ctx.fillStyle = col;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.arc(proj.x, proj.y, 3, 0, Math.PI * 2);
    ctx.moveTo(proj.x + 3, proj.y - 3);
    ctx.lineTo(proj.x + 22, proj.y - 18);
    ctx.lineTo(proj.x + 96, proj.y - 18);
    ctx.stroke();

    ctx.fillText(hn.label, proj.x + 24, proj.y - 21);
  });
  ctx.restore();
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  const target = stateColors[currentState];
  const easeSpeed = 0.04;
  displayColor.r += (target.r - displayColor.r) * easeSpeed;
  displayColor.g += (target.g - displayColor.g) * easeSpeed;
  displayColor.b += (target.b - displayColor.b) * easeSpeed;
  const c = {
    r: Math.round(displayColor.r),
    g: Math.round(displayColor.g),
    b: Math.round(displayColor.b)
  };

  if (bootSpinBoost > 0.0002) bootSpinBoost *= 0.94;
  else bootSpinBoost = 0;

  const speed = stateSpeed[currentState] + bootSpinBoost;
  rotation += speed;
  pulsePhase += 0.032;

  const micBoost = isRecording ? liveMicEnergy * 0.38 : 0;
  const pulse = currentState === 'speaking' ? 0.72 + Math.sin(pulsePhase * 4) * 0.3
              : currentState === 'listening' ? 0.82 + Math.sin(pulsePhase * 2) * 0.22 + micBoost
              : 0.86 + Math.sin(pulsePhase) * 0.15;

  const coreR = Math.min(W, H) * INNER_CORE_SCALE * pulse;

  // 1. Distorted Outer Halo Blob
  const haloGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR * 6.8);
  haloGrad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},0.40)`);
  haloGrad.addColorStop(0.25, `rgba(${c.r},${c.g},${c.b},0.14)`);
  haloGrad.addColorStop(0.6, `rgba(${c.r},${c.g},${c.b},0.04)`);
  haloGrad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = haloGrad;
  blobPath(CX, CY, coreR * 6.8, 1.3, 0.18, 56);
  ctx.fill();

  // 2. Distorted Corona Blob + Textured Contour Crusts
  const coronaGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR * 2.8);
  coronaGrad.addColorStop(0, `rgba(${Math.min(255,c.r+70)},${Math.min(255,c.g+50)},${Math.min(255,c.b+35)},0.88)`);
  coronaGrad.addColorStop(0.45, `rgba(${c.r},${c.g},${c.b},0.40)`);
  coronaGrad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = coronaGrad;
  blobPath(CX, CY, coreR * 2.8, 4.2, 0.25, 56);
  ctx.fill();

  for (let layer = 1; layer <= 5; layer++) {
    const layerR = coreR * (0.58 + layer * 0.36);
    blobPath(CX, CY, layerR, layer * 2.1, 0.24 + layer * 0.03, 64);
    ctx.strokeStyle = layer % 2 === 0
      ? `rgba(255, 255, 255, ${(0.38 - layer * 0.05) * pulse})`
      : `rgba(${Math.min(255,c.r+50)},${Math.min(255,c.g+50)},${Math.min(255,c.b+40)},${(0.52 - layer * 0.06) * pulse})`;
    ctx.lineWidth = 1.8 - layer * 0.2;
    ctx.stroke();
  }

  // 3. Dense Intersecting Core Surface Ellipses & Internal Vortex Web
  ctx.save();
  ctx.translate(CX, CY);
  const surfR = coreR * 1.28;
  const surfaceArcs = isMobile ? 24 : 54;
  for (let i = 0; i < surfaceArcs; i++) {
    const a0 = (i / surfaceArcs) * Math.PI * 2 + rotation * 2.1;
    const wobble = Math.sin(pulsePhase * 2.4 + i * 0.9) * 0.22;
    const rx = surfR * (0.75 + wobble * 0.38);
    const ry = surfR * (0.35 + Math.abs(Math.sin(a0 * 0.7 + pulsePhase * 0.5)) * 0.55);
    ctx.strokeStyle = (i % 5 === 0)
      ? `rgba(255, 255, 255, ${(0.36 + Math.abs(wobble) * 0.45) * pulse})`
      : `rgba(${Math.min(255,c.r+45)},${Math.min(255,c.g+45)},${Math.min(255,c.b+40)},${0.28 + Math.abs(wobble) * 0.5})`;
    ctx.lineWidth = (i % 4 === 0) ? 1.45 : 0.85;
    ctx.beginPath();
    ctx.ellipse(0, 0, rx, ry, a0, 0, Math.PI * 2);
    ctx.stroke();
  }

  const tendrils = isMobile ? 16 : 36;
  for (let t = 0; t < tendrils; t++) {
    const aStart = (t / tendrils) * Math.PI * 2 - rotation * 3.2;
    const rMid = coreR * (0.46 + (t % 3) * 0.32);
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.30 * pulse})`;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.arc(
      Math.cos(aStart) * coreR * 0.22,
      Math.sin(aStart) * coreR * 0.22,
      rMid,
      aStart,
      aStart + Math.PI * 0.85
    );
    ctx.stroke();
  }
  ctx.restore();

  // 4. White-Hot Distorted Nucleus Blob + Cellular Core Granules
  const hotGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR * 0.74);
  hotGrad.addColorStop(0, `rgba(255,255,255,${0.98*pulse})`);
  hotGrad.addColorStop(0.55, `rgba(${Math.min(255,c.r+95)},${Math.min(255,c.g+95)},${Math.min(255,c.b+75)},${0.92*pulse})`);
  hotGrad.addColorStop(1, `rgba(${c.r},${c.g},${c.b},0)`);
  ctx.fillStyle = hotGrad;
  blobPath(CX, CY, coreR * 0.74, 7.8, 0.16, 48);
  ctx.fill();

  coreGranules.forEach(cg => {
    const spin = rotation * cg.speedMul;
    const x0 = cg.r * Math.sin(cg.phi) * Math.cos(cg.theta + spin);
    const y0 = cg.r * Math.cos(cg.phi);
    const z0 = cg.r * Math.sin(cg.phi) * Math.sin(cg.theta + spin);
    const rp = rotatePoint(x0, y0, z0, -rotation * 1.4, 0.45);
    const proj = project(rp.x, rp.y, rp.z);
    const alpha = (0.45 + Math.sin(pulsePhase * 4 + cg.tw) * 0.45) * pulse;
    ctx.fillStyle = cg.sz > 2.4
      ? `rgba(255, 255, 255, ${alpha})`
      : `rgba(${Math.min(255,c.r+70)},${Math.min(255,c.g+70)},${Math.min(255,c.b+60)},${alpha})`;
    const s = cg.sz * proj.scale;
    ctx.fillRect(proj.x - s * 0.5, proj.y - s * 0.5, s, s);
  });

  // 5. 3D Jittered Orbital Rings
  rings.forEach((ring, rIdx) => {
    const ry = rotation * ring.speed + ring.phase, rx = ring.tiltX;
    const baseAlpha = ring.thin ? 0.25 : 0.40;
    const wobbleAmt = ring.radius * 0.024;

    let avgDepth = 0;
    const projected = ring.pts.map(p => {
      const ow = Math.sin(pulsePhase * 1.3 + p.a * 3 + ring.phase) * wobbleAmt;
      const rr = ring.radius + p.jitter + ow;
      const x0 = Math.cos(p.a) * rr, y0 = Math.sin(p.a) * rr * Math.cos(ring.tiltY), z0 = Math.sin(p.a) * rr * Math.sin(ring.tiltY);
      const rp = rotatePoint(x0, y0, z0, ry, rx);
      const depth = (rp.z + ring.radius) / (ring.radius * 2);
      avgDepth += depth;
      return project(rp.x, rp.y, rp.z);
    });
    avgDepth /= projected.length;

    const useAmberHolo = (activePreset === 3 && rIdx % 4 === 0);
    const rrCol = useAmberHolo ? 255 : c.r;
    const ggCol = useAmberHolo ? 157 : c.g;
    const bbCol = useAmberHolo ? 61  : c.b;

    if (!isMobile) {
      const glowAlpha = baseAlpha * (0.25 + avgDepth * 0.75) * 0.62;
      ctx.strokeStyle = `rgba(${rrCol},${ggCol},${bbCol},${glowAlpha*pulse})`;
      ctx.lineWidth = ring.thin ? 2.8 : 4.0;
      ctx.beginPath();
      projected.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
      ctx.stroke();
    }

    const bright = avgDepth > 0.70;
    const alpha = baseAlpha * (0.25 + avgDepth * 0.8);
    ctx.strokeStyle = bright
      ? `rgba(${Math.min(255,rrCol+65)},${Math.min(255,ggCol+65)},${Math.min(255,bbCol+55)},${Math.min(1, alpha*1.4*pulse)})`
      : `rgba(${rrCol},${ggCol},${bbCol},${alpha*pulse})`;
    ctx.lineWidth = ring.thin ? 1.1 : 1.75;
    ctx.beginPath();
    projected.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
    ctx.stroke();
  });

  // 6. 3D Sweeping Thick Arcs
  thickArcs.forEach(ta => {
    const ry = rotation * ta.speed + ta.phase, rx = ta.tiltX;
    const steps = isMobile ? 28 : 64;
    let avgDepth = 0;
    const pts = [];
    for (let i = 0; i <= steps; i++) {
      const a = ta.startA + (i / steps) * ta.sweep;
      const x0 = Math.cos(a) * ta.radius, y0 = Math.sin(a) * ta.radius * Math.cos(ta.tiltY), z0 = Math.sin(a) * ta.radius * Math.sin(ta.tiltY);
      const rp = rotatePoint(x0, y0, z0, ry, rx);
      const depth = (rp.z + ta.radius) / (ta.radius * 2);
      avgDepth += depth;
      pts.push(project(rp.x, rp.y, rp.z));
    }
    avgDepth /= pts.length;
    const alpha = (0.20 + avgDepth * 0.45);

    if (!isMobile) {
      ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${alpha * 0.38 * pulse})`;
      ctx.lineWidth = ta.width * 2.2;
      ctx.beginPath();
      pts.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
      ctx.stroke();
    }

    ctx.strokeStyle = `rgba(${Math.min(255,c.r+45)},${Math.min(255,c.g+45)},${Math.min(255,c.b+35)},${alpha*pulse})`;
    ctx.lineWidth = ta.width;
    ctx.beginPath();
    pts.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
    ctx.stroke();
  });

  // 7. 3D Filaments
  ctx.strokeStyle = activePreset === 2
    ? `rgba(255, 46, 76, ${0.52 * pulse})`
    : `rgba(${c.r},${c.g},${c.b},${0.38 * pulse})`;
  ctx.lineWidth = activePreset === 2 ? 1.25 : 1.05;
  ctx.beginPath();
  filaments.forEach(f => {
    const spin = rotation * f.speedMul + f.spinOffset;
    for (let s = 0; s <= f.segs; s++) {
      const t = s / f.segs;
      const theta = f.theta0 + Math.cos(f.dir) * f.arcLen * t + spin;
      const phi = f.phi0 + Math.sin(f.dir) * f.arcLen * t * 0.6;
      const r = f.r0 * (1 + Math.sin(t * Math.PI) * 0.08);
      const x0 = r * Math.sin(phi) * Math.cos(theta), y0 = r * Math.cos(phi), z0 = r * Math.sin(phi) * Math.sin(theta);
      const rp = rotatePoint(x0, y0, z0, 0, 0.25);
      const proj = project(rp.x, rp.y, rp.z);
      if (s === 0) ctx.moveTo(proj.x, proj.y); else ctx.lineTo(proj.x, proj.y);
    }
  });
  ctx.stroke();

  // 8. Extended Straight Radial Lines (Spikes)
  ctx.strokeStyle = activePreset === 2
    ? `rgba(255, 70, 95, ${0.58 * pulse})`
    : `rgba(${c.r},${c.g},${c.b},${0.45 * pulse})`;
  ctx.lineWidth = 1.35;
  ctx.beginPath();
  spikes.forEach(sp => {
    const theta = sp.theta + rotation * 0.9, phi = sp.phi;
    const flicker = 0.6 + Math.sin(pulsePhase * 3 + sp.tw) * 0.4;
    const x0 = sp.startR * Math.sin(phi) * Math.cos(theta), y0 = sp.startR * Math.cos(phi), z0 = sp.startR * Math.sin(phi) * Math.sin(theta);
    const r1 = sp.startR + sp.len * flicker;
    const x1 = r1 * Math.sin(phi) * Math.cos(theta), y1 = r1 * Math.cos(phi), z1 = r1 * Math.sin(phi) * Math.sin(theta);
    const rp0 = rotatePoint(x0, y0, z0, 0, 0.25), rp1 = rotatePoint(x1, y1, z1, 0, 0.25);
    const p0 = project(rp0.x, rp0.y, rp0.z), p1 = project(rp1.x, rp1.y, rp1.z);
    ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y);
  });
  ctx.stroke();

  // 9. High-Density Thick 3D Noise Particle Cloud
  noisePts.forEach(p => {
    const x0 = p.r * Math.sin(p.phi) * Math.cos(p.theta + rotation * 0.7);
    const y0 = p.r * Math.cos(p.phi);
    const z0 = p.r * Math.sin(p.phi) * Math.sin(p.theta + rotation * 0.7);
    const rp = rotatePoint(x0, y0, z0, rotation * 0.4, 0.3);
    const proj = project(rp.x, rp.y, rp.z);
    const tw = 0.35 + Math.sin(pulsePhase * 2 + p.tw) * 0.3 + 0.4;
    const depth = (rp.z + p.r) / (p.r * 2);
    const a = Math.min(1, tw * depth * pulse * 0.85);
    ctx.fillStyle = p.hot
      ? `rgba(${Math.min(255,c.r+70)},${Math.min(255,c.g+70)},${Math.min(255,c.b+60)},${a})`
      : `rgba(${c.r},${c.g},${c.b},${a})`;
    const s = p.sz * proj.scale;
    ctx.fillRect(proj.x, proj.y, s, s);
  });

  // 10. High-Density Pulse Burst Particles
  const burstStrength = Math.max(0, (pulse - 0.74) / 0.26);
  if (burstStrength > 0.01) {
    burstPts.forEach(p => {
      const x0 = p.r * Math.sin(p.phi) * Math.cos(p.theta + rotation * 0.7);
      const y0 = p.r * Math.cos(p.phi);
      const z0 = p.r * Math.sin(p.phi) * Math.sin(p.theta + rotation * 0.7);
      const rp = rotatePoint(x0, y0, z0, rotation * 0.4, 0.3);
      const proj = project(rp.x, rp.y, rp.z);
      const depth = (rp.z + p.r) / (p.r * 2);
      ctx.fillStyle = `rgba(${Math.min(255,c.r+60)},${Math.min(255,c.g+60)},${Math.min(255,c.b+45)},${burstStrength*depth*0.75})`;
      const s = p.sz * proj.scale;
      ctx.fillRect(proj.x, proj.y, s, s);
    });
  }

  // 11. Outer Arc Reactor CAD Rings, Extended 3D Callouts & HUD Mini-Graphs
  drawArcReactorOverlay(c, pulse);
  drawHoloCallouts(c);
  drawMiniGraphs(c);

  requestAnimationFrame(draw);
}

/* ============ 7. BACKEND WIRING ============ */
function sendGoal() {
  const goal = document.getElementById('goalInput').value.trim();
  if (!goal) return;
  fetch('/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({goal})})
    .then(() => { document.getElementById('goalInput').value = ''; setState('processing'); pollGoalStatus(goal, false); })
    .catch(() => { document.getElementById('goalInput').value = ''; setState('processing'); });
}

function cancelGoal() {
  fetch('/cancel', {method: 'POST'}).catch(() => {});
  setState('idle');
  conversationMode = false;
  convBtn.classList.remove('active');
}

function toggleConversationMode() {
  conversationMode = !conversationMode;
  convBtn.classList.toggle('active', conversationMode);
}

async function toggleRecording() {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: false } });
      connectMicVisualizer(stream);
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000 });
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
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
  if (window.location.protocol === 'file:') return;
  fetch(window.location.pathname)
    .then(r => r.text())
    .then(html => {
      const parser = new DOMParser();
      const newDoc = parser.parseFromString(html, "text/html");
      const blockTag = '{' + '%';
      ["logLines", "historyLines"].forEach(id => {
        const oldEl = document.getElementById(id);
        const newEl = newDoc.getElementById(id);
        if (oldEl && newEl && newEl.textContent.indexOf(blockTag) === -1) {
          oldEl.innerHTML = newEl.innerHTML;
        }
      });
    })
    .catch(err => console.error("refresh failed", err));
}
setInterval(refreshPanels, 5000);

/* ============ 8. START RENDER LOOP ============ */
draw();
triggerBootSequence();
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
        requests.post(f"{SIDECAR_URL}/stop_audio", timeout=3)
    except Exception as e:
        print(f"CANCEL: failed to reach sidecar stop_audio: {e}")
    return jsonify({"status": "cancel requested"})


if __name__ == "__main__":
    cert_dir = os.path.expanduser("~/zyp/certs")
    candidates = [
        "the_endgame_lap.tail05f2a2.ts.net",
        "the-endgame-lap.tail05f2a2.ts.net",
    ]

    cert_path, key_path = None, None
    for name in candidates:
        c = os.path.join(cert_dir, f"{name}.crt")
        k = os.path.join(cert_dir, f"{name}.key")
        if os.path.exists(c) and os.path.exists(k):
            cert_path, key_path = c, k
            break

    if not cert_path:
        crts = glob.glob(os.path.join(cert_dir, "*.crt"))
        if crts:
            c = crts[0]
            k = c[:-4] + ".key"
            if os.path.exists(k):
                cert_path, key_path = c, k

    if cert_path and key_path:
        print(f"TLS active using: {os.path.basename(cert_path)}")
        app.run(host="0.0.0.0", port=1367, debug=False, threaded=True, ssl_context=(cert_path, key_path))
    else:
        print("WARNING: TLS cert not found in ~/zyp/certs, falling back to HTTP")
        app.run(host="0.0.0.0", port=1367, debug=False, threaded=True)
