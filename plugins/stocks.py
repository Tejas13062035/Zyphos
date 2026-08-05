import requests
import time

TOOL_NAME = "stocks"
TOOL_DESCRIPTION = "Get global stock market index snapshot"
TOOL_ARGS = {}

INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def _fetch(symbol, retries=2):
    for attempt in range(retries):
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                headers=HEADERS,
                timeout=10
            )
            if r.status_code != 200:
                time.sleep(1)
                continue
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            return meta
        except Exception:
            time.sleep(1)
            continue
    return None

def run(args=None):
    results = []
    for name, symbol in INDICES.items():
        meta = _fetch(symbol)
        if not meta:
            continue
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None or prev is None:
            continue
        change = price - prev
        pct = (change / prev) * 100
        direction = "up" if change >= 0 else "down"
        results.append(f"{name}: {round(price, 2)}, {direction} {abs(round(pct, 2))}%")

    if not results:
        return {"error": "no market data returned — Yahoo may be rate limiting, try again shortly"}

    summary = ". ".join(results)
    return {"status": "ok", "summary": summary, "indices": results}
