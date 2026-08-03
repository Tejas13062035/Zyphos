# Z.Y.P.H.O.S — Roadmap

Living document tracking what's built, what's in progress, and what's planned. Updated August 2026.

---

## ✅ Phase 1 — Core Skeleton
- CLI entry point, keyword planner/executor
- Persistent state, task queue
- Basic filesystem and shell tools

## ✅ Phase 2 — Perception & Control
- Windows sidecar (click, type, screenshot, scroll, drag, hotkey)
- Multi-goal queue, scheduling (`--schedule`)
- Always-on daemon with auto-start, watchdog

## ✅ Phase 3 — Intelligence
- Smart planner + smart executor (LLM-driven)
- Self-critique loop, goal chaining
- FAISS semantic memory
- Plugin system (36+ plugins and growing)
- Multi-backend LLM routing (Cerebras primary, Groq/Gemini fallback, Ollama offline)
- Voice: Whisper STT, Edge TTS, voice biometric auth (Resemblyzer)
- `--research` upgraded with ML-reranked search (wigolo) and web intelligence (webintel)
- Self-diagnostics: `--doctor`, `--diagnose`, quota tracking, session stats
- Human-supervised auto-fix pipeline (`core/autofix.py`) — Tier 1 known-pattern fixes auto-tested and auto-committed, Tier 2 (high-risk files) always requires review
- Plugin smoke test suite (`tests/test_plugins.py`)
- Multi-language TTS with automatic language detection

## ✅ Remote Access & Infrastructure (Aug 2026 — not in original roadmap)
- Tailscale-based remote access from any device, anywhere
- Web UI dashboard reachable remotely, with live goal queue, logs, and history
- CANCEL button — stops both the running goal and any in-progress audio playback instantly
- Fully self-healing background stack: daemon + watchdog + web UI + event reminder, all auto-restarting on crash or terminal close
- Migrated WSL1 → WSL2 (mirrored networking mode) for reliable boot-time auto-start
- Windows Task Scheduler integration — full stack starts automatically at login, no terminal needed
- Moved WSL install off the nearly-full C: drive onto D: (900+ GB free)

---

## 🔜 Near-term (current machine, in progress)

- [ ] **Remote voice commands** — record voice from phone's browser over Tailscale, transcribe via Whisper on the home PC, execute and speak the response back
- [ ] **Turn-based conversation mode** — after Zyphos replies, automatically re-listen for the next turn, creating a natural back-and-forth loop without repeated tapping
- [ ] **`docs/wsl_setup_notes.md`** — document the WSL2 migration and networking fixes for future reference

## 🔜 On new laptop arrival (Ryzen 7 260, RTX 5050, hardware upgrade)

- [ ] **Local LLM upgrade** — Qwen2.5 7B (fast, reliable JSON) as default, Hermes 8B for complex agentic/chaining tasks, both via Ollama on GPU
- [ ] **Local vision** — moondream2, replacing Groq API dependency for screen/webcam understanding
- [ ] **Whisper medium** — better STT accuracy than the current `small` model
- [ ] **Kokoro TTS** — higher quality, fully local voice synthesis (replacing Edge TTS's cloud dependency)
- [ ] **Wake word detection** — always-on "Zyphos" trigger from anywhere, no terminal or manual `--listen` needed (background service + global hotkey fallback on Windows)
- [ ] **`memory/persons/`** — structured per-person memory (name, relationship, preferences, last interaction) as the foundation for ambient awareness
- [ ] **Ambient awareness** — webcam-based person detection and face recognition; greet people by name when they enter the room (Jarvis/Pepper-scene style)
- [ ] **Full voice demo video** — proper mic quality finally makes a real voice-command demo recording possible for the README/portfolio
- [ ] **Dedicated home-server role** — the current HP Pavilion becomes the always-on Zyphos host once the new laptop takes over as the daily driver

## 🔮 Longer-term / exploratory

- [ ] **True live streaming conversation** — voice activity detection, continuous audio, no tapping — the actual "on a call" experience, once hardware and latency allow
- [ ] **Home & environment control** — smart plugs (lights, fans), phone notification integration
- [ ] **Proactive suggestions** — Zyphos notices patterns in usage/memory and surfaces them unprompted
- [ ] **Fine-tuned Zyphos model** — QLoRA fine-tune on real usage logs once enough training data has accumulated, so responses feel personally tuned rather than generic
- [ ] **Multi-machine sidecar** — control more than one physical machine from a single Zyphos instance

---

## Explicitly deprioritized / decided against

- **GitHub Actions CI** — the sidecar/Windows dependency can't be replicated in a cloud runner, so automated CI wouldn't actually validate the parts that matter most; skipped in favor of the local smoke test suite instead.
- **Fully autonomous self-modification** — considered and deliberately scoped back to a human-supervised two-tier system (`core/autofix.py`). Only low-risk, pattern-matched fixes can auto-commit after passing tests; anything touching auth, API keys, or messaging always requires a human review, since automated tests can catch crashes but not subtle correctness or security regressions.
