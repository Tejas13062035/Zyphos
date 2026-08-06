import requests
from plugins.weather import run as weather_run
from plugins.news import run as news_run
from plugins.calendar import run as calendar_run
from plugins.nasa import run as nasa_run
from plugins.stocks import run as stocks_run
from plugins.wisdom import run as wisdom_run
from core.location import get_location

TOOL_NAME = "briefing"
TOOL_DESCRIPTION = "gives a full spoken briefing: weather, calendar, AI news, space news, stock market, and a philosophical quote"
TOOL_ARGS = {"city": "str (default: auto-detected from IP)", "topic": "str (news topic, default technology)"}


def _speak(text: str):
    try:
        requests.post("http://127.0.0.1:5000/speak", json={"text": text}, timeout=5)
    except Exception:
        pass


def run(args: dict) -> dict:
    city = args.get("city")
    if not city:
        location = get_location()
        city = location.get("city", "Godda")
    topic = args.get("topic", "technology")

    parts = []

    # Weather
    try:
        w = weather_run({"city": city, "speak": False})
        if w.get("status") == "ok":
            parts.append(f"Weather in {city}: {w['description']}, {w['temp']} degrees, feels like {w['feels_like']}.")
        else:
            parts.append("Weather data unavailable.")
    except Exception as e:
        parts.append(f"Weather check failed: {e}")

    # Calendar — today's events
    try:
        c = calendar_run({"action": "today"})
        if c.get("status") == "ok":
            events = c.get("events", [])
            if events:
                parts.append(f"You have {len(events)} event(s) today: " + "; ".join(events))
            else:
                parts.append("No events on your calendar today.")
        else:
            parts.append("No events on your calendar today.")
    except Exception as e:
        parts.append(f"Calendar check failed: {e}")

    # AI / tech news
    try:
        n = news_run({"topic": "artificial intelligence", "strict": True})
        if n.get("status") == "ok":
            parts.append(f"AI news: {n['result']}")
        else:
            parts.append("AI news unavailable.")
    except Exception as e:
        parts.append(f"AI news check failed: {e}")

    # General topic news (default: technology)
    try:
        n2 = news_run({"topic": topic})
        if n2.get("status") == "ok":
            parts.append(f"Top {topic} news: {n2['result']}")
    except Exception:
        pass

    # Space news — NASA APOD
    try:
        space = nasa_run({"action": "apod"})
        if space.get("status") == "ok":
            parts.append(f"Space update: {space['result']}")
        else:
            parts.append("Space update unavailable.")
    except Exception as e:
        parts.append(f"Space update failed: {e}")

    # Stock market
    try:
        stocks = stocks_run({})
        if stocks.get("status") == "ok":
            parts.append(f"Market snapshot: {stocks['summary']}")
        else:
            parts.append("Market data unavailable.")
    except Exception as e:
        parts.append(f"Market check failed: {e}")

    # Philosophy quote
    try:
        w2 = wisdom_run({"mode": "quote"})
        if w2.get("status") == "ok":
            parts.append(f"Thought for the day: {w2['result']}")
    except Exception as e:
        parts.append(f"Wisdom check failed: {e}")

    full_briefing = "\n\n".join(parts)
    _speak(" ".join(parts).replace("\n", " "))
    return {"status": "ok", "result": full_briefing}
