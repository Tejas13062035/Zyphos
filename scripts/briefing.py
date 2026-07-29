import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.expanduser("~/zyp"))
from tools.sidecar import speak as speak_edge

def speak(text):
    print(f"  → {text}")
    try:
        speak_edge(text)
    except Exception as e:
        print(f"    (TTS failed: {e})")

def briefing():
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
    print("\nDAILY BRIEFING")
    print("=" * 40)

    speak(f"{greeting} Tejas. Here is your daily briefing.")

    date_str = now.strftime("%A, %B %d, %Y")
    speak(f"Today is {date_str}.")

    try:
        from plugins.weather import run as weather_run
        w = weather_run({"city": "Godda"})
        if w.get("status") == "ok":
            speak(f"Weather in Godda: {w['description']}, {w['temp']} degrees Celsius.")
        else:
            speak("Weather data unavailable.")
    except Exception as e:
        speak(f"Weather check failed.")

    try:
        from plugins.calendar import run as cal_run
        events = cal_run({"action": "today"})
        if events.get("status") == "ok" and events.get("events"):
            speak(f"You have {len(events['events'])} event today.")
            for e in events["events"]:
                speak(e)
        else:
            speak("No events on your calendar today.")
    except Exception as e:
        speak("Calendar unavailable.")

    try:
        from plugins.notes import run as notes_run
        notes = notes_run({"action": "list"})
        if notes.get("status") == "ok" and notes.get("notes"):
            speak(f"You have {len(notes['notes'])} saved notes.")
    except Exception:
        pass

    try:
        from plugins.news import run as news_run
        n = news_run({"topic": "technology"})
        if n.get("status") == "ok":
            speak(f"Top technology news: {n['result'][:300]}")
    except Exception:
        speak("News unavailable.")

    speak("That's your briefing. Have a productive day, Tejas.")
    print("=" * 40)

if __name__ == "__main__":
    briefing()
