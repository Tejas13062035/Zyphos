# Z.Y.P.H.O.S — CURRENT STATE SNAPSHOT
## Date: 2026-07-17
## Purpose: Full context handoff for new chat sessions

---

## REPO
- **Name:** Zyphos (renamed from ZYPHOS-Z.Y.P.H.OS)
- **URL:** github.com/Tejas13062035/Zyphos
- **Status:** Public, professional README/LICENSE/CHANGELOG/.env.example in place
- Changelogs moved to `docs/changelogs/`

---

## LLM BACKEND (current)
```
core/llm.py
core/smart_executor.py → ask():
  1. Try ask_cerebras() (gpt-oss-120b) — PRIMARY
  2. Fallback to ask_groq() if Cerebras fails — avoids quota exhaustion
```
- max_tokens increased to 250 (was 100/150) — fixes JSON truncation on longer tool args
- Critic now truncates large results before evaluation — fixes false-fail retries on screenshot-heavy tasks

---

## FULL PLUGIN LIST (32 total)
calendar, clipboard, countries, dictionary, drive, file_organizer,
github_clone, github_stats, gmail, hello, joke, music, nasa,
network_scan, news, notes, port_scanner, qr, security, spotify,
system_stats, timer, translate, weather, webintel, whatsapp,
whatsapp_bulk, wigolo, wisdom, youtube, calculator, briefing

### Notable plugins added since last full changelog:
- **github_clone** — clone or zip-download any public GitHub repo
- **github_stats** — now supports ANY public repo/user (not just own), owner param added
- **wigolo** — ML-reranked web search, page fetch, multi-step research pipeline
- **webintel** — Jina Reader, YouTube transcripts, Exa semantic search, RSS via Agent Reach
- **wisdom** — philosophical quotes/stories via Cerebras; two-voice Socratic dialogue mode with batched TTS
- **calculator, dictionary, translate, qr** — 4 new utility plugins added together
  - translate switched from unreliable MyMemory API → Cerebras, added auto-speak
- **briefing** — combines weather + calendar + news into one spoken daily summary
- **event reminder** (separate script, not a plugin) — 30min/10min alerts before calendar events, dedupes within same check cycle, timestamp parsing bug fixed

---

## RELIABILITY / INFRA IMPROVEMENTS
- `--forget` flag — deletes memory entries matching a query, rebuilds FAISS index
- `--help` flag — full command reference
- `start_all.sh` — single script launches daemon + watchdog + event reminder together
- Watchdog now also monitors and auto-restarts the event reminder script
- Full system stress test script — covers all subsystems, auto-clears daemon queue and forgets test goals after running (keeps memory clean)
- Type hints, docstrings, and formatting cleanup pass across critic.py and smart_executor.py
- `.bashrc` backed up as reference in repo (secrets redacted)

---

## VOICE / TTS (confirmed from earlier this session)
- Edge TTS (en-GB-RyanNeural) — replaced pyttsx3
- Voice biometric auth via Resemblyzer — `--enroll`, threshold 0.70
- Sensitive tools gated: gmail, drive, calendar, notes, whatsapp, delete_file
- Auto-speak triggers on conversational goals ("tell me", "what is", etc.)
- Batched TTS generation added for wisdom dialogue mode (tight pacing between two voices)

---

## KNOWN WORKING PATTERNS
- Joke plugin: routes through JokeAPI directly (not LLM-generated), safe-mode off, count+category supported, speaks each joke sequentially with timestamped audio files (avoids permission conflicts)
- NASA plugin: 6 actions (apod, asteroids, earth, donki, image, eonet) — Mars Photos endpoint found dead/archived by NASA, worked around
- Countries plugin: Wikipedia REST API fallback since REST Countries v3.1/v3.2 deprecated mid-project
- GitHub plugin: works on any public repo now, e.g. confirmed working on torvalds/linux

---

## HOW TO CATCH UP A NEW CHAT SESSION
Run these and paste output:
```bash
cd ~/zyp && git log --oneline -30
ls ~/zyp/plugins/
cat ~/zyp/core/smart_executor.py | head -50
```
This gives enough context to reconstruct current state without needing to paste every file.

---

## NEXT LIKELY PRIORITIES (inferred, not confirmed)
- Continue expanding plugin ecosystem
- Possibly integrate wigolo/webintel into --research flow
- Main machine arrival (Jul-Aug 2026) — Phase 4 upgrade (Qwen2.5 7B local, Whisper medium, local vision)
- Ambient awareness (Phase 5) — wake word, webcam person detection
