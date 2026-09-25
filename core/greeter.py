import requests
from datetime import datetime

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def speak(text: str):
    try:
        requests.post(f"{SIDECAR_URL}/speak", json={"text": text})
    except:
        print(text)

def get_period(hour: int) -> str:
    if 7 <= hour <= 12:
        return "morning"
    elif 12 < hour <= 16:
        return "afternoon"
    elif 16 < hour <= 22:
        return "evening"
    else:
        return "night"

GREETINGS = {
    "morning": [
        "Good morning Sir Tejas. Rise and grind. Let's make today count.",
        "Good morning sir. It's a new day. What are we building today?",
        "Morning Sir. Coffee's up, let's get to work."
    ],
    "afternoon": [
        "Good afternoon Tejas. Hope the morning was productive.",
        "Afternoon sir. Stay focused, the day is still young.",
        "Good afternoon Sir. How's the build going?"
    ],
    "evening": [
        "Good evening Tejas. Wind down but don't stop thinking.",
        "Evening sir. What did we accomplish today?",
        "Good evening sir. Are we almost done for the day?"
    ],
    "night": [
        "It's past 10 PM. You should sleep now sir. Have a good night.",
        "Night mode activated. Rest well Sir, big day tomorrow.",
        "It's late sir. Shut it down and get some sleep. Good night."
    ]
}

REMINDERS = {
    "morning": "Don't forget to check your calendar sir and drink water.",
    "afternoon": "Take a break if you've been at it for a while sir.",
    "evening": "Don't forget to wrap up your tasks and review what you did today Sir.",
    "night": "Sleep is important for memory consolidation sir. Rest well."
}

import random

def greet():
    now = datetime.now()
    hour = now.hour
    period = get_period(hour)
    time_str = now.strftime("%I:%M %p")

    greeting = random.choice(GREETINGS[period])
    reminder = REMINDERS[period]

    speak(greeting)
    speak(reminder)

    return {
        "status": "ok",
        "period": period,
        "time": time_str,
        "greeting": greeting,
        "reminder": reminder
    }

if __name__ == "__main__":
    greet()
