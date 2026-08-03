# Z.Y.P.H.O.S — SESSION CHANGELOG
## Period: Late July – Early August 2026
## Purpose: Full context handoff — this session ran very long, use this to resume in a new chat

---

## STARTING STATE (beginning of this session)
- Phase 3 complete: smart executor/planner, FAISS memory, plugin system, voice biometrics, Cerebras as primary LLM
- Repo public on GitHub as "Zyphos" with README, LICENSE, CHANGELOG, .env.example, architecture diagram, plugin ecosystem diagram, asciinema terminal demo
- ~34 plugins

---

## PART 1 — SELF-DIAGNOSTIC & RELIABILITY TOOLING

### `--doctor` (plugins/doctor.py)
Full system health check: API keys present, Cerebras reachable, Windows sidecar running, Ollama running, memory index found, disk free space, known-issue pattern detection (checks source files for regressions like missing `reasoning_effort` param or low `max_tokens` on reasoning-model calls), API quota usage.

### `core/quota_tracker.py`
Tracks daily call counts per LLM provider (Cerebras/Groq/Gemini) against approximate free-tier limits. `record_call(provider)` hooked into each `ask_*` function in `core/llm.py`. Surfaced in `--doctor` output.

### `--diagnose "error text"` (plugins/diagnose.py)
Matches pasted error messages against a dictionary of known Zyphos failure patterns (JSON truncation, permission conflicts, missing PYTHONPATH, connection refused, indentation errors, rate limits, deprecated API 404s) and returns the known fix. Falls back to an LLM-generated diagnosis if no pattern matches.

### `core/autofix.py` — human-supervised two-tier auto-fix
- **Tier 1 (auto-commit allowed):** error must match a known-safe pattern from `diagnose.py` AND the target file must not be in a high-risk list (voice_auth.py, llm.py, .env, daemon.py, security.py, whatsapp*.py, gmail.py). Generates a fix via LLM, writes it, runs the full plugin smoke test suite + `--doctor`, auto-commits only if both pass, otherwise reverts to the original file content.
- **Tier 2:** anything not matching Tier 1 criteria requires human review — no auto-fix attempted.
- Safety gate tested and confirmed working in a sandboxed test (correctly refused a `NameError` since it wasn't a known-safe pattern).
- Explicitly decided this is NOT "self-evolving AI" — Zyphos is self-aware (introspects its own state/history) but does not autonomously decide what to fix without the pattern-match + test-suite gate.

### `tests/test_plugins.py` — smoke test suite
pytest-compatible. Calls every plugin's `run()` with safe dummy args, checks no crash and a dict with `status`/`error` key returned. All 36 plugins passing as of last run. Considered and explicitly declined GitHub Actions CI — sidecar/Windows dependency can't be replicated in a cloud runner, and the available PAT lacked `workflow` scope anyway.

### `session_summary` plugin
Reads recent `git log --oneline` and asks the LLM to summarize what was accomplished — auto-generates a changelog entry from commit history so manual changelog writing isn't always required.

### `session_stats` plugin
Goals run today/week/all-time, most-used tools (via a new dedicated `core/tool_usage_log.py` — memory.json's nested string format made direct parsing unreliable, so tool usage is now logged separately at the moment `smart_executor.py` calls each tool).

---

## PART 2 — NEW PLUGINS THIS SESSION

- **pdf_summary** — reads/summarizes PDFs via pypdf + Cerebras, strips markdown before TTS (fixed an issue where the LLM's `**bold**` syntax was being read aloud as literal asterisks)
- **ocr** — screen or image text extraction via pytesseract; supports `screen`, `screen_left`, `screen_right` (region cropping for split-screen use); preprocessing upgraded to grayscale + 2x upscale + `--psm 6` after initial attempts on dense/small UI text were garbled
- **currency** — currency conversion via exchangerate-api.com
- **unit_convert** — km/miles, kg/lbs, m/ft, cm/inches, celsius/fahrenheit/kelvin
- **doctor, diagnose, session_summary, session_stats** — see Part 1

### Fixes to existing plugins
- **countries** — REST Countries API found fully deprecated (v3.1/v3.2 both dead) mid-session; switched to Wikipedia REST API as a reliable free fallback, with optional REST Countries v5 (Bearer token, 500 req/month free) preferred when a key is present
- **nasa** — Mars Photos endpoint found dead/archived by NASA; rebuilt with 6 working actions (apod, asteroids, earth [EPIC], donki [solar flares], image [library search], eonet [natural events])
- **news** — added `language=en` filter after briefing pulled in Korean/Japanese/Italian headlines unfiltered
- **github_stats** — generalized to work on ANY public repo/user (was hardcoded to only the user's own repo); required making the Zyphos repo public since the token only had `public_repo` scope
- **weather / scripts/briefing.py** — added `core/location.py` (IP geolocation via ip-api.com) so weather defaults to auto-detected location instead of a hardcoded city; switched to using lat/lon instead of city name after a special character in the auto-detected city name ("Domchānch") broke OpenWeatherMap's name-based lookup
- **joke** — fixed to route through JokeAPI directly instead of being LLM-generated; disabled safe-mode per user request; fixed multi-joke requests (each joke gets its own timestamped TTS file to avoid permission conflicts, ~2s gap between)
- **researcher.py (--research)** — upgraded to use `wigolo` (ML-reranked search + dedicated research-brief action) and `webintel` (Jina Reader, Exa semantic search, YouTube transcripts, RSS) instead of raw DuckDuckGo; added fallback query diversification (rotating angles: "latest developments", "recent breakthroughs", etc.) and duplicate-phrase detection/trimming for when Cerebras's follow-up query generation glitches

### Auto-speak trigger list
`core/smart_executor.py`'s `speak_triggers` list grew throughout the session as gaps were found: added "summarize", "convert", changed "show me" to just "show" to catch "show my session stats". `joke` and `wisdom` are deliberately excluded from the generic auto-speak path because both plugins have their own internal `_speak()` calls (wisdom also supports a two-voice Socratic dialogue mode with batched TTS).

---

## PART 3 — CANCEL / STOP MECHANISM

- `core/cancel_flag.py` — simple file-flag based cancel signal, checked inside the `--research` loop between rounds
- Web UI got a CANCEL button (red, next to SEND) that POSTs to a new `/cancel` route
- **Audio interrupt was the harder problem.** Discovered the sidecar (`C:\zyphos_sidecar\sidecar.py`) had THREE competing, overlapping playback mechanisms left over from different points in earlier sessions: a `/play` route using Windows `SoundPlayer` (WAV-only, doesn't support MP3), a `/play_audio` route using VLC with its own `/stop_audio` (unused — nothing in the WSL codebase calls it), and `/speak`/`/speak_batch` using `playsound` (blocking, unkillable). Consolidated everything onto a single `play_audio_killable()` helper using `ffplay` (installed via `winget install ffmpeg`) as a real, trackable, killable subprocess. `/cancel` in webui.py now also calls the sidecar's `/stop_audio`, which terminates the tracked `ffplay` process — confirmed working, audio now stops within ~1 second of pressing CANCEL.

---

## PART 4 — REMOTE ACCESS (TAILSCALE) — the long debugging arc

### Goal
Control Zyphos (send goals, get spoken responses) from a phone, from anywhere, while the home PC keeps running.

### Setup
- Installed Tailscale on Windows PC and phone, same account, private mesh network
- `scripts/webui.py` was already bound to `0.0.0.0`, no code change needed there
- Web UI auto-refresh (originally a blunt `<meta refresh>` every 3s) was wiping out in-progress typing — replaced with JS `fetch()`-based partial refresh that only updates specific `id`-tagged panels (daemon-status, pending-queue, daemon-log, goal-history), leaving the goal input box untouched

### Port odyssey
- Port 6789 → found inside a Windows Hyper-V TCP port exclusion range (`netsh interface ipv4 show excludedportrange`) → "Permission denied" with zero traceback, very hard to diagnose
- Moved to 8181 → worked initially
- After the WSL2 migration (see Part 5), 8181 was found separately occupied by a genuine Windows `svchost.exe` system service (unrelated coincidence) → moved to **9191**, which is the current/final port

### Daemon/watchdog/webui resilience
- Found the daemon was NOT actually staying alive — `.bashrc` auto-start only fires when a NEW terminal opens, it's not a continuous monitor; if the daemon died while a terminal was already open, nothing brought it back until a fresh terminal was opened
- `--watchdog`'s subprocess launch had no `nohup`/`setsid`/`start_new_session` — closing its parent terminal killed it too. Fixed with `start_new_session=True` plus a proper PID file
- `.bashrc` extended with matching PID-file-check blocks for both the watchdog and (later) the web UI, mirroring the existing daemon block
- `scripts/watchdog.py` extended with `is_webui_running()` / `restart_webui()` alongside its existing daemon and event-reminder checks — full 30-second-interval self-healing for all three services
- `scripts/start_all.sh` consolidated to start daemon + watchdog + webui + event reminder together, each guarded by a `pgrep` check to avoid duplicate processes

### WSL1 → WSL2 migration
- Discovered mid-session the machine was running **WSL1**, not WSL2 — this explained the Task Scheduler unreliability (WSL1 has fundamentally different, less consistent behavior when launched non-interactively/at boot vs. WSL2's proper VM boot process)
- C: drive only had ~19GB free, Ubuntu install was ~65GB, so an in-place `wsl --set-version` conversion wasn't viable
- **Migration path used:** `wsl --export Ubuntu-22.04 D:\Ubuntu-backup.tar` (compressed to ~31GB) → `wsl --unregister Ubuntu-22.04` → `wsl --import Ubuntu-22.04 D:\WSL\Ubuntu-22.04 D:\Ubuntu-backup.tar --version 2` → `wsl --set-default Ubuntu-22.04`. Now running on D: (900+ GB free) instead of the cramped C:. All files/projects preserved.
- Post-import quirks fixed along the way: had to `echo -e "[user]\ndefault=tejas100x" | sudo tee -a /etc/wsl.conf` since the import defaulted to root user; watchdog PID file cleanup errors were cosmetic and harmless

### Windows Task Scheduler ("Zyphos Startup" task)
- Created with: Run whether logged on or not, Run with highest privileges, Trigger "At log on", Action `wsl.exe -d Ubuntu -- bash -c "~/zyp/scripts/start_all.sh"`
- **Key gotcha:** "Run whether logged on or not" requires the real Windows/Microsoft account password — NOT the 4-digit lock-screen PIN. This caused significant back-and-forth confusion before being identified.
- Even after fixing the password, the "At log on" trigger fired unreliably on actual restarts (Task Scheduler logged "Task completed" but the script's effects weren't visible) — attributed to a WSL2 boot-timing race condition. Tried adding a 2-minute trigger delay; still inconsistent. **This was subsumed by the mirrored-networking fix below and considered resolved enough to move on from** — not perfectly solved, but functional via the watchdog/bashrc fallbacks regardless of Task Scheduler's exact reliability.

### The 127.0.0.1 sidecar connectivity saga (WSL2 → Windows)
- After the WSL2 migration, WSL2 could no longer reach the Windows sidecar at `127.0.0.1:5000` (`ConnectionRefusedError: [Errno 111]`)
- Ruled out one by one: Tailscale interference (disconnected it, still failed), Windows Firewall (added explicit inbound rule for port 5000, still failed), direct WSL2-internal-IP instead of 127.0.0.1 (still failed), a stray duplicate `.wslconfig.txt` file that had absorbed an edit meant for the real `.wslconfig` (found and deleted)
- **Root cause found:** WSL 2.7.11.0 defaults to NAT-based networking; the fix was explicitly setting `networkingMode=mirrored` in `C:\Users\HP\.wslconfig` (alongside `localhostForwarding=true`), followed by a full `wsl --shutdown` and restart. This made 127.0.0.1 traffic between WSL2 and Windows work correctly in both directions.
- Side effect: under mirrored networking, WSL2 no longer has a separate internal IP (the old `172.28.168.231`-style address is gone) — it shares Windows' network interface directly. This made the earlier portproxy rule (added to forward the web UI port) obsolete; it was removed, and the web UI on `0.0.0.0` became directly reachable on the Windows host's Tailscale IP with no translation layer needed.

### Final confirmed-working state (end of this session)
- Web UI live at `http://<tailscale-ip>:9191`, reachable from phone anywhere
- CANCEL button stops both goal execution and any in-progress TTS audio
- Daemon, watchdog, web UI, event reminder all self-heal via `.bashrc` + 30s watchdog checks
- Sidecar (port 5000) reachable from WSL2 again after the mirrored-networking fix
- Full round trip tested and working: phone → web UI → daemon queue → smart execution → Cerebras → sidecar TTS → spoken response, all over Tailscale from outside the home network

---

## PART 5 — MULTI-LANGUAGE TTS

- `core/language_detect.py` using the `langdetect` library — `detect_language(text)` returns an ISO code, `get_voice_for_text(text)` maps it to an Edge TTS voice (en→Ryan, hi→hi-IN-MadhurNeural, es/fr/de/ja/zh-cn/ar also mapped)
- `tools/sidecar.py`'s `speak(text, voice=None)` now auto-detects language and picks the matching voice whenever no voice is explicitly passed — zero changes needed anywhere else in the codebase, since every existing `speak(text)` call site automatically benefits
- Tested and confirmed: Hindi text ("नमस्ते, आज मौसम कैसा है") correctly triggers `hi-IN-MadhurNeural`, English stays on Ryan, both without manual voice specification

---

## PART 6 — ROADMAP OVERHAUL

Original README Phase 1-9 roadmap was significantly out of date — most of Part 1-5 above (self-diagnostics, autofix, remote access, WSL2 migration, multi-language) weren't in the original phases at all. A new `ROADMAP.md` was written to replace/supplement it, organized as:
- Phases 1-3: marked complete, updated with what was actually built (more than originally scoped)
- New "Remote Access & Infrastructure" section documenting the Tailscale/WSL2 work as its own category, since it didn't fit the original phase numbering
- "Near-term" — remote voice commands, turn-based conversation mode, WSL setup docs
- "On new laptop arrival" — local LLM (Qwen2.5 7B + Hermes 8B), local vision (moondream2), Whisper medium, Kokoro TTS, wake word, `memory/persons/`, ambient awareness, full voice demo, Pavilion becomes home server
- "Longer-term / exploratory" — true live streaming conversation, home/environment control, proactive suggestions, fine-tuned Zyphos model, multi-machine sidecar
- "Explicitly deprioritized" — GitHub Actions CI (sidecar can't run in cloud runners), fully autonomous self-modification (deliberately kept human-supervised)

README's roadmap section was updated to point to this new file rather than duplicating it.

---

## DISCUSSED BUT NOT YET BUILT (next session candidates)

1. **Remote voice commands** — MediaRecorder API in the web UI, upload audio to a new `/voice_command` route, transcribe via the existing local Whisper, feed into the normal goal pipeline. Direct extension of everything built in Part 4.
2. **Turn-based conversation mode** — after Zyphos speaks a response, automatically re-arm listening for the next turn, creating a call-like loop without repeated tapping. Pros/cons of this vs. single-command vs. true live-streaming were discussed at length; turn-based was chosen as the right next scope (true streaming needs VAD + continuous audio infra, treated as a later/hardware-upgrade-era goal).
3. **`docs/wsl_setup_notes.md`** — a written record of the whole WSL2 migration + mirrored networking fix for future reference, in case of a fresh machine setup later.

---

## THINGS TO REMEMBER FOR NEXT SESSION

- Web UI port is **9191**, not 8181 or 6789 (both taken by unrelated Windows services/exclusion ranges)
- `.wslconfig` at `C:\Users\HP\.wslconfig` must contain `networkingMode=mirrored` and `localhostForwarding=true` — if sidecar connectivity ever breaks again after a Windows update, check this first
- WSL now lives at `D:\WSL\Ubuntu-22.04`, not the default C: location
- Sidecar audio is fully consolidated on `ffplay` via `play_audio_killable()` — do not reintroduce `playsound` or VLC-based playback, both were removed as redundant/unkillable
- `joke` and `wisdom` plugins intentionally excluded from generic auto-speak (they self-speak)
- Task Scheduler's "At log on" trigger for full-stack auto-start is not perfectly reliable even after the WSL2 fix — the watchdog/bashrc self-healing is the actual safety net, not Task Scheduler alone
