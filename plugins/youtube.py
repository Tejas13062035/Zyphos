import requests
import urllib.parse

TOOL_NAME = "youtube"
TOOL_DESCRIPTION = "Search and open YouTube videos or playlists in browser"
TOOL_ARGS = {"action": "search|play|playlist", "query": "search term or video name"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def run(args: dict) -> dict:
    action = args.get("action", "search").lower()
    query = args.get("query", "")

    if not query:
        return {"error": "query required"}

    encoded = urllib.parse.quote(query)

    if action == "search":
        url = f"https://www.youtube.com/results?search_query={encoded}"

    elif action == "play":
        # opens first result directly via YouTube search
        url = f"https://www.youtube.com/results?search_query={encoded}"

    elif action == "playlist":
        url = f"https://www.youtube.com/results?search_query={encoded}&sp=EgIQAw%253D%253D"

    else:
        return {"error": f"unknown action: {action}"}

    r = requests.post(f"{SIDECAR_URL}/open_url", json={"url": url})
    return {"status": "opened", "url": url, "query": query}
