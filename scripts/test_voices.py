import sys, time, requests
sys.path.insert(0, ".")
from tools.sidecar import speak_kokoro

FINALISTS = ["onyx", "sky", "jadzia", "fable", "nova", "echo", "lewis", "v0gurney"]

d = requests.get("http://localhost:8880/v1/audio/voices", timeout=5).json()
v = d["voices"] if isinstance(d, dict) else d
ids = [x["id"] if isinstance(x, dict) else x for x in v]

voices, missing = [], []
for n in FINALISTS:
    hits = [i for i in ids if i.split("_", 1)[-1] == n]
    (voices.extend(hits) if hits else missing.append(n))
print("voices:", voices)
if missing:
    print("NOT FOUND:", missing)

LINES = [
    ("GENERAL", "Hey there. Good evening, I am Zyphos. Your presence has been detected, "
                "and the room is ready. Shall I begin the briefing, or would you rather "
                "I stayed quiet for now?"
                "Hello Tejas, How are u doing?"),
    ("SHORT", "Done. The file has been moved."),
    ("GREETING", "Good evening, Boss. You look like you had a long day. How did it go?, "
                 "Welcome Back Boss, what are we working on today, or would you like to hear news first?"),
    ("BRIEFING", "Here is your briefing. It is 7:30 in the evening, the temperature is 24 degrees, "
                 "and you have two reminders tomorrow. The wake word model is ready, "
                 "and the room scan found nobody else at home."),
]

for label, text in LINES:
    print(f"\n=== {label} ===", flush=True)
    for vid in voices:
        print(f">> {vid}", flush=True)
        try:
            speak_kokoro(text, voice=vid)
        except Exception as e:
            print(f"   failed: {e}")
        time.sleep(1)

print("\ndone")
