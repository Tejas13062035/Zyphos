import requests

DEFAULT_CITY = "Godda"

def get_location() -> dict:
    """Auto-detect city via IP geolocation. Falls back to DEFAULT_CITY on failure."""
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5)
        data = r.json()
        if data.get("status") == "success":
            return {
                "city": data.get("city", DEFAULT_CITY),
                "region": data.get("regionName", ""),
                "country": data.get("country", ""),
                "lat": data.get("lat"),
                "lon": data.get("lon")
            }
    except Exception:
        pass
    return {"city": DEFAULT_CITY, "region": "", "country": "", "lat": None, "lon": None}
