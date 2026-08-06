import requests
import os
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/zyp/.env"))

TOOL_NAME = "news"
TOOL_DESCRIPTION = "Get latest news headlines by topic"
TOOL_ARGS = {"topic": "str: topic to search news for", "strict": "bool: exact phrase + relevancy sort (default False)"}

def run(args=None):
    topic = args.get("topic", "technology") if args else "technology"
    strict = args.get("strict", False) if args else False
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return {"error": "NEWS_API_KEY not set in .env"}

    query = f'"{topic}"' if strict else topic
    sort_by = "relevancy" if strict else "publishedAt"

    r = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "language": "en",
            "sortBy": sort_by,
            "pageSize": 5,
            "apiKey": api_key
        }
    )
    data = r.json()
    articles = data.get("articles", [])
    lines = [f"{i+1}. {a['title']} — {a['source']['name']}" for i, a in enumerate(articles)]
    result = "\n".join(lines) if lines else "No articles found"
    return {"status": "ok", "result": result}
