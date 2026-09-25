import os
import re
import json
import random
import string
import requests
import hashlib
import subprocess
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/zyp/.env"))

TOOL_NAME = "security"
TOOL_DESCRIPTION = "Security and info tools: generate passwords, lookup IPs/domains, check breaches, WiFi info"
TOOL_ARGS = {"action": "password|ip_lookup|dns|whois|breach_check|wifi_info|port_scan", "target": "IP, domain, or email"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

def generate_password(length=16) -> dict:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choices(chars, k=length))
    strength = "strong" if length >= 16 else "medium" if length >= 12 else "weak"
    return {"status": "ok", "password": password, "length": length, "strength": strength}

def ip_lookup(ip: str) -> dict:
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
        data = r.json()
        return {
            "status": "ok",
            "ip": ip,
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country_name"),
            "isp": data.get("org"),
            "timezone": data.get("timezone"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude")
        }
    except Exception as e:
        return {"error": str(e)}

def dns_lookup(domain: str) -> dict:
    try:
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True, text=True, timeout=10
        )
        return {"status": "ok", "domain": domain, "result": result.stdout}
    except Exception as e:
        return {"error": str(e)}

def whois_lookup(domain: str) -> dict:
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15
        )
        # extract key lines only
        lines = result.stdout.splitlines()
        key_lines = [l for l in lines if any(k in l.lower() for k in
            ["registrar", "created", "expires", "updated", "name server", "status", "registrant"])]
        return {"status": "ok", "domain": domain, "info": "\n".join(key_lines[:20])}
    except Exception as e:
        return {"error": str(e)}

def breach_check(email: str) -> dict:
    try:
        headers = {"hibp-api-key": os.getenv("HIBP_API_KEY", ""), "User-Agent": "Zyphos"}
        r = requests.get(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
            headers=headers, timeout=10
        )
        if r.status_code == 404:
            return {"status": "ok", "email": email, "breached": False, "message": "No breaches found"}
        elif r.status_code == 200:
            breaches = r.json()
            names = [b["Name"] for b in breaches]
            return {"status": "ok", "email": email, "breached": True, "count": len(names), "breaches": names[:10]}
        elif r.status_code == 401:
            return {"error": "HIBP API key required — get free key at haveibeenpwned.com"}
        else:
            return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def wifi_info() -> dict:
    try:
        r = requests.get(f"{SIDECAR_URL}/wifi_info", timeout=10)
        return {"status": "ok", "info": r.json().get("info", "unavailable")}
    except Exception as e:
        return {"error": str(e)}

def port_scan(target: str, ports: str = "1-1000") -> dict:
    try:
        r = requests.post(f"{SIDECAR_URL}/network_scan",
            json={"target": target}, timeout=60)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def run(args: dict) -> dict:
    action = args.get("action", "").lower()
    target = args.get("target", "")
    length = int(args.get("length", 16))

    if action == "password":
        return generate_password(length)
    elif action == "ip_lookup":
        return ip_lookup(target or "8.8.8.8")
    elif action == "dns":
        return dns_lookup(target)
    elif action == "whois":
        return whois_lookup(target)
    elif action == "breach_check":
        return breach_check(target)
    elif action == "wifi_info":
        return wifi_info()
    elif action == "port_scan":
        return port_scan(target)
    else:
        return {"error": f"unknown action: {action}"}
