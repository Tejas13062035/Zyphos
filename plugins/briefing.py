import requests
from plugins.weather import run as weather_run
from plugins.news import run as news_run
from plugins.calendar import run as calendar_run
from plugins.nasa import run as nasa_run
from plugins.stocks import run as stocks_run
from plugins.wisdom import run as wisdom_run
from core.location import get_location
from core.llm import ask_cerebras
import re

def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # remove bold
    text = re.sub(r"^\s*-\s+", "", text, flags=re.MULTILINE)  # remove bullet dashes
    text = re.sub(r"#+\s*", "", text)  # remove markdown headers
    return text

TOOL_NAME = "briefing"
TOOL_DESCRIPTION = "gives a full spoken briefing in Hindi (weather, calendar, AI news, space news, stock market) plus one English philosophical quote"
TOOL_ARGS = {"city": "str (default: auto-detected from IP)", "topic": "str (news topic, default technology)"}

HINDI_VOICE = "hi-IN-SwaraNeural"
ENGLISH_VOICE = "en-GB-RyanNeural"

def _speak(text: str, voice: str = ENGLISH_VOICE):
    try:
        requests.post("http://127.0.0.1:5000/speak", json={"text": text, "voice": voice}, timeout=120)
    except Exception:
        pass


def _translate_to_hindi(text: str) -> str:
    prompt = (
        f"Translate the following briefing into natural, conversational spoken Hindi "
        f"(Devanagari script). Keep numbers, city names, and proper nouns (like 'Nasdaq', "
        f"'S&P 500', company names) as-is, don't translate them. Make it sound natural when "
        f"spoken aloud, not robotic word-for-word translation. "
        f"IMPORTANT: Do NOT use any markdown formatting — no asterisks, no bullet points, "
        f"no headers, no dashes. Plain conversational sentences only, as if spoken by a news anchor.\n\nText:\n{text}"
    )
    result = ask_cerebras(
        prompt,
        system="You are an expert Hindi translator who produces natural, fluent spoken Hindi for voice assistants. Never use markdown formatting.",
        max_tokens=1200
    )
    if result.startswith("LLM_ERROR"):
        return text
    return result.strip()


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

    # Calendar
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

    # AI news
    try:
        n = news_run({"topic": "artificial intelligence", "strict": True})
        if n.get("status") == "ok":
            parts.append(f"AI news: {n['result']}")
    except Exception:
        pass

    # Tech news
    try:
        n2 = news_run({"topic": topic})
        if n2.get("status") == "ok":
            parts.append(f"Top {topic} news: {n2['result']}")
    except Exception:
        pass

    # Space
    try:
        space = nasa_run({"action": "apod"})
        if space.get("status") == "ok":
            parts.append(f"Space update: {space['result']}")
    except Exception:
        pass

    # Stocks
    try:
        stocks = stocks_run({})
        if stocks.get("status") == "ok":
            parts.append(f"Market snapshot: {stocks['summary']}")
    except Exception:
        pass

    english_briefing = "\n\n".join(parts)

    # Translate everything except the quote to Hindi
    hindi_briefing = _translate_to_hindi(english_briefing)

    # Wisdom quote — stays in English
    quote_text = ""
    try:
        q = wisdom_run({"mode": "quote", "silent": True})
        if q.get("status") == "ok":
            quote_text = q["result"]
    except Exception:
        pass

    # Speak: Hindi briefing first, then English quote
    _speak(_strip_markdown(hindi_briefing), voice=HINDI_VOICE)
    if quote_text:
        _speak(f"Thought for the day. {quote_text}", voice=ENGLISH_VOICE)

    full_result = f"[HINDI]\n{hindi_briefing}\n\n[ENGLISH QUOTE]\n{quote_text}"
    return {"status": "ok", "result": full_result}
