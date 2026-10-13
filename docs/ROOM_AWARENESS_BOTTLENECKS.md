# Room awareness: bottlenecks and fixes

How a person walking in is detected, recognized and greeted, what was slowing or breaking that, and what fixed it.
Numbers were measured on the owner's machine (laptop with an RTX 5050, an ESP32-S3 camera, an LD2412 radar, a PIR)
unless a line says "inferred". Where an improvement coincided with other changes, that is noted rather than claimed.

## Result at a glance

| Stage | Before | After |
|---|---|---|
| First greeting text after idle | 23.8 s (model swap) | 0.5-0.8 s warm; none at all for a personal greeting |
| Speaking one greeting (`speak()`) | about 20 s | no fixed sleep; Kokoro 0.2-0.7 s per sentence |
| Kokoro, 10 words | 9.0 s | 0.6-0.7 s |
| Face detection, per frame | 307 ms | 27 ms |
| Embedding, per face | 232-306 ms | 4-9 ms |
| One frame containing a face | 540-610 ms | 31-36 ms |
| Faces found in 36 door frames | 2 | 8 |
| Scan start to decision | 2.3 s (5 frames, dlib) | 0.7-0.9 s |
| Frames judged per second | about 2 | about 4.4 (limited by capture) |
| Blurry door face vs the enrolled person | similarity 0.23-0.31 (no match) | 0.58-0.63 (match) |
| ESP link, ping | 33% loss, average 323 ms | 0% loss, average 4.5 ms (see section E) |
| Watcher memory | 2.9 GB (Whisper loaded, inferred) | 0.3 GB after a restart |

## A. False arrivals and false greetings

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 1 | Radar "targets" at about 0 cm and single-poll blips counted as arrivals | The old watcher failed the new tests for both | `MIN_TARGET_CM = 20`, `ARRIVE_POLLS = 2` |
| 2 | PIR noise started arrivals | Many "arrival at 0 cm" log lines | PIR only starts a face search; a greeting needs a recognized face |
| 3 | 5 s of radar silence counted as a departure and cleared the roster; a very still person can go quiet that long | Inferred from code and logs | `ABSENT_HOLD_S = 30` |
| 4 | The same person was re-greeted after a roster clear or a head turn; the only guard was a 5-minute cooldown | Code | Greet a named person only after 10 min unseen (`AWAY_MIN_S`); last-seen time survives roster clears; a repeat face with the same name merges into one entry |
| 5 | The generic prompt produced "welcome home" while sitting | Reported | Personal greeting from written lines; generic prompt rewritten |
| 6 | Strangers could be asked repeatedly; "Yes" or "Hello" could be enrolled as a name | Code | 30-minute re-ask memory; stop-word filter in name extraction |

## B. Getting frames from the camera

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 7 | Capture, detect, embed, identify ran strictly in sequence, and a walking person was judged by stale frames | 5 frames in 2.3 s | Producer/consumer pipeline that keeps only the newest frame; frames stay in memory (no shared temp file) |
| 8 | The producer captured faster than frames were processed | Mocked scan: 60 captures for 9 processed frames; about 2x with dlib (inferred) | The producer stays at most one frame ahead |
| 9 | A failing capture took 20 s (10 s timeout, 2 tries) | Median capture 22.5 s during the bad link period | Scan captures: 5 s, one try |
| 10 | The ESP serves one request at a time, so polls queue behind captures | Code and measured poll latency under capture | Presence polling slows to once a second during a scan |

## C. Finding and recognizing the face

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 11 | dlib detection and embedding were slow | 307 ms + 232-306 ms per frame | New `sface` backend: OpenCV YuNet detector + SFace embedder. No `onnxruntime` needed, so it works on Python 3.14 |
| 12 | A second detection pass and a re-read of every person file per identification | About 1 s per face | Match the embedding already computed (`identify_embedding`); person files cached by modification time |
| 13 | dlib missed faces of 100-179 px (pose and blur, not size) | 2 faces found vs 8 in the same 36 frames | YuNet |
| 14 | Door frames are far blurrier than enrollment photos | Sharpness 230 and 426 (reference photos) vs 10-23 (door frames) | Migration adds door-frame embeddings (several per person) next to the reference photo |
| 15 | Blurry frames of a known person scored low and could look like a stranger | Sharpness >= 17 scored 0.43-0.51; <= 15 scored 0.23-0.31 (8 faces) | Blurry faces are never called strangers (`SHARP_MIN_UNKNOWN = 16`); decide on the best frame, not two of N (two-of-N would have failed all 3 walks); ambiguity rule between enrolled people (`SFACE_MARGIN = 0.15`) |
| 16 | Threshold choice | A second enrolled person scored -0.03 to 0.16 against the owner's frames | `THRESHOLD_SFACE = 0.363`; YuNet score 0.8 (no false positives in about 29 face-less frames) |

## D. The greeting itself

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 17 | `speak_kokoro` slept `len(text)/15` s (minimum 2 s) after `/play`, which already blocks | `speak()` measured 20 s against 7 s generation + 2.7 s playback | Sleep removed |
| 18 | Kokoro used all 16 threads and ran about 10x slower | 9.0 s vs 0.6-0.7 s at `OMP_NUM_THREADS=6`. The cause (mixed performance/efficiency cores) is a hypothesis; the speedup is measured | `scripts/start_kokoro.sh` pins 6 threads |
| 19 | The whole greeting was generated before any audio played | Code | `speak_fast`: sentence 2 is generated while sentence 1 plays |
| 20 | The greeting model (qwen3.5:9b) competed with granite for 8 GB of VRAM | 23.8 s cold, 0.5 s warm | Greeter uses the default warm model; the model is prewarmed when a scan starts; a personal greeting needs no model |
| 21 | An LLM error string could be spoken aloud | Code | Fallback lines |
| 22 | Kokoro was called at the Windows host address, but it runs inside WSL (60 s timeout); it also was not started automatically | Connection timeouts | Use localhost with a 3 s connect timeout; `start_kokoro.sh` runs from `start_all.sh` and the watchdog restarts it |

## E. ESP32 and network

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 23 | The link on a phone hotspot was unreliable | Ping 33% loss, up to 542 ms; `/presence` timeouts; captures 22 s median | Moved to the house WiFi: ping 0% loss, 4.5 ms average. `WiFi.setSleep(false)` was also recommended; the improvement coincided with the network change, so the two cannot be separated |
| 24 | A slow ESP triggered a network scan of about 1,000 addresses | `found at` printed for an unchanged address | The saved address gets a 5 s check; scans at most once a minute, 32 threads |
| 25 | The ESP did not reconnect by itself | Code | Reconnect check in `loop()` |

## F. Bring-up mistakes worth remembering

- The LD2412 talks at **115200** baud, not 256000. At the wrong rate bytes arrive but no frame ever parses.
- Camera settings: QXGA at quality 6 with an 8 MHz clock overflowed the frame buffer (`FB-OVF`) and made `/capture` fail. The tuned settings were later restored from the wrong copy of the sketch; compare against the last working copy before restoring anything.
- Camera pins 4-13 and 15-18 are taken; the radar uses GPIO 1, 42 and 2, the VC-01 uses 47 and 41. GPIO14 is marked occupied on this board.

## Enabling and tuning the sface backend

Set `ZYPHOS_FACE_BACKEND=sface` (in `scripts/start_all.sh`, so the watchdog's children inherit it). Run `scripts/migrate_to_sface.py` first: with sface on and nobody migrated, everyone looks like a stranger. The migration is additive; unset the variable to roll back.

| Setting | Where | Value |
|---|---|---|
| `THRESHOLD_SFACE` | `tools/face_recognition_backend.py` | 0.363 |
| `SFACE_MARGIN` | same | 0.15 |
| `YUNET_SCORE_MIN` | same | 0.8 |
| `SHARP_MIN_UNKNOWN` | `core/room_roster.py` | 16 (from 8 faces in one lighting setup; retune from the `faces` list in `presence_log.jsonl`) |
| `AWAY_MIN_S` | same | 600 |
| `ABSENT_HOLD_S`, `ARRIVE_POLLS`, `MIN_TARGET_CM` | `scripts/presence_watcher.py` | 30, 2, 20 |

## Not verified

- sface has been run end to end only as one-shot silent scans, and not as a hold-out test (same session and spot as the enrolled door frames). Re-check in other lighting and on other days.
- The live greeting latency (the owner reports about 8-10 s). The per-stage breakdown needs the timing edits in `tools/sidecar.py` and `core/greeter_ambient.py`.
- The VC-01 hardware path: `wake_count` has not been seen to increase.
- `zyphos.py --wakeword` is not started by `start_all.sh` or the watchdog.
- The effect of `WiFi.setSleep(false)` alone.
- Enrollment runs inside the watcher process, and its microphone use may collide with the wake-word loop (not tested). The watcher also loads Whisper on the first stranger.
- `requirements.txt` is missing packages needed on a fresh clone (`face_recognition`, `dlib`, `opencv`, `openwakeword`, `soundfile`, `insightface` if used).
- The remaining blur at the door is a camera-side limit (exposure and focus). Shorter exposure or more light is the next lever.

## Tests

`scripts/stress_test_room.py` covers the roster, the greeting rules, the sface rules (with mocked models), the watcher state machine
(including radar noise, PIR and blips), ESP link policy, scan load, the personal greeting, and live checks of the ESP, capture, face
pipeline, Kokoro and the greeting. Read-only helpers: `scripts/bench_faces.py`, `scripts/sface_vs_reference.py`, `scripts/face_debug.py`.
