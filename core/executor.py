from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

from tools.vision import look
from tools.sidecar import click, type_text, screenshot, scroll, drag, hotkey

def execute_task(task: dict) -> dict:
    desc = task.get("description", "").lower()
    result = None

    if "click" in desc:
        parts = desc.split()
        try:
            x = int(parts[parts.index("click") + 1])
            y = int(parts[parts.index("click") + 2])
            result = click(x, y)
        except (ValueError, IndexError):
            result = {"error": "click requires x y coordinates"}

    elif desc.startswith("remember "):
        from core.personality import remember
        fact = desc.replace("remember ", "").strip()
        result = {"status": "ok", "result": remember(fact)}

    elif desc.startswith("forget "):
        from core.personality import forget
        key = desc.replace("forget ", "").strip()
        result = {"status": "ok", "result": forget(key)}

    elif "what do you know about me" in desc or "recall personality" in desc:
        from core.personality import recall_all
        result = {"status": "ok", "result": recall_all()}

    elif "type" in desc:
        parts = desc.split("type ", 1)
        text = parts[1] if len(parts) > 1 else ""
        result = type_text(text)

    elif "date" in desc or "time" in desc or "weather" in desc:
        import datetime
        import requests as req
        now = datetime.datetime.now().strftime("%A, %B %d %Y, %I:%M %p")
        text = f"The current date and time is {now}"
        req.post(f"{SIDECAR_URL}/speak", json={"text": text})
        result = {"status": "spoken", "text": text}

    elif desc.startswith("speak ") or desc.startswith("say "):
        import requests as req
        text = desc.replace("speak ", "").replace("say ", "").strip()
        r = req.post(f"{SIDECAR_URL}/speak", json={"text": text})
        result = r.json()

    elif "network" in desc or "scan" in desc or "devices" in desc:
        from plugins.network_scan import run as net_run
        result = net_run({"action": "scan", "target": "192.168.31"})

    elif "screenshot" in desc:
        result = screenshot()
        result = {"status": "screenshot taken", "has_image": "image" in result}

    elif "search" in desc and ("chrome" in desc or "browser" in desc or "tab" in desc):
        import requests as req
        query = desc
        for word in ["search", "in chrome", "in browser", "in tab", "chrome tab", "browser tab", "in the"]:
            query = query.replace(word, "")
        query = query.strip()
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        r = req.post(f"{SIDECAR_URL}/open_url", json={"url": search_url})
        result = r.json()

    elif "open" in desc:
        import requests as req
        app_name = desc.replace("open", "").strip()
        # if it's a URL
        if "http" in app_name or "www" in app_name:
            r = req.post(f"{SIDECAR_URL}/open_url", json={"url": app_name})
        else:
            r = req.post(f"{SIDECAR_URL}/open_app", json={"app": app_name})
        result = r.json()

    elif "scroll" in desc:
        parts = desc.split()
        try:
            x = int(parts[parts.index("scroll") + 1])
            y = int(parts[parts.index("scroll") + 2])
            amount = int(parts[parts.index("scroll") + 3]) if len(parts) > parts.index("scroll") + 3 else 3
            result = scroll(x, y, amount)
        except (ValueError, IndexError):
            result = {"error": "scroll requires x y coordinates"}

    elif "drag" in desc:
        parts = desc.split()
        try:
            x1 = int(parts[parts.index("drag") + 1])
            y1 = int(parts[parts.index("drag") + 2])
            x2 = int(parts[parts.index("drag") + 3])
            y2 = int(parts[parts.index("drag") + 4])
            result = drag(x1, y1, x2, y2)
        except (ValueError, IndexError):
            result = {"error": "drag requires x1 y1 x2 y2 coordinates"}

    elif "hotkey" in desc:
        parts = desc.split()
        idx = parts.index("hotkey")
        keys = parts[idx + 1:]
        result = hotkey(keys) if keys else {"error": "hotkey requires at least one key"}

    elif "look" in desc:
        prompt = desc.replace("look", "").strip() or "What do you see on this screen?"
        result = look(prompt)

    elif "search" in desc:
        from tools.search import search_summary
        query = desc.split("search ", 1)[1] if "search " in desc else desc
        result = {"status": "ok", "result": search_summary(query)}

    elif desc.startswith("play "):
        from plugins.music import run as music_run
        query = desc[5:].strip()
        result = music_run({"action": "play", "query": query})

    elif "stop music" in desc or desc == "stop":
        from plugins.music import stop_music
        result = stop_music()

    elif "calendar" in desc or "schedule" in desc or "remind" in desc:
        from plugins.calendar import run as cal_run
        if "add" in desc or "create" in desc or "new event" in desc:
            import re
            summary_match = re.search(r"event\s+(.+?)\s+on\s+", desc)
            date_match = re.search(r"on\s+(\d{4}-\d{2}-\d{2})", desc)
            time_match = re.search(r"at\s+(\d{2}:\d{2})", desc)
            result = cal_run({
                "action": "add",
                "summary": summary_match.group(1) if summary_match else "New Event",
                "date": date_match.group(1) if date_match else "",
                "time": time_match.group(1) if time_match else "09:00"
            })

        elif "today" in desc:
            result = cal_run({"action": "today"})
        else:
            result = cal_run({"action": "list"})

    elif "email" in desc or "gmail" in desc:
        from plugins.gmail import run as gmail_run
        if "send" in desc:
            result = gmail_run({"action": "send", "to": "", "subject": "", "body": desc})
        else:
            result = gmail_run({"action": "read"})

    elif "drive" in desc:
        from plugins.drive import run as drive_run
        if "upload" in desc:
            result = drive_run({"action": "upload", "file_path": desc.replace("drive upload", "").strip()})
        elif "download" in desc:
            result = drive_run({"action": "download", "query": desc.replace("drive download", "").strip()})
        elif "search" in desc:
            result = drive_run({"action": "search", "query": desc.replace("drive search", "").strip()})
        else:
            result = drive_run({"action": "list"})

    elif "speak" in desc:
        text = desc.replace("speak", "").strip()
        from tools.sidecar import speak
        result = speak(text)

    elif "joke" in desc:
        from plugins.joke import run as joke_run
        from tools.sidecar import speak
        parts = desc.split()
        count = 1
        for p in parts:
            if p.isdigit():
                count = int(p)
                break
        result = joke_run({"count": count, "category": "Any"})
        joke_text = result.get("joke", "")
        if joke_text:
            speak(joke_text)

    else:
        result = {"error": f"unknown task: {desc}"}

    task["status"] = "done"
    task["result"] = result
    return task
