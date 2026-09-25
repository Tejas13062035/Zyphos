import time
import requests

TOOL_NAME = "whatsapp_bulk"
TOOL_DESCRIPTION = "Send same WhatsApp message to multiple contacts"
TOOL_ARGS = {"contacts": "list of phone numbers or contact names", "message": "message to send"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

from plugins.whatsapp import CONTACTS

def send_one(phone: str, message: str) -> dict:
    url = f"https://web.whatsapp.com/send?phone={phone}&text={message}"
    requests.post(f"{SIDECAR_URL}/open_url", json={"url": url})
    time.sleep(6)
    requests.post(f"{SIDECAR_URL}/click", json={"x": 1300, "y": 752})
    time.sleep(1)
    requests.post(f"{SIDECAR_URL}/hotkey", json={"keys": ["enter"]})
    time.sleep(2)
    return {"phone": phone, "status": "sent"}

def run(args: dict) -> dict:
    contacts = args.get("contacts", [])
    message = args.get("message", "")

    if not message:
        return {"error": "message required"}
    if not contacts:
        return {"error": "contacts required"}

    results = []
    for contact in contacts:
        phone = CONTACTS.get(contact.lower(), contact)
        print(f"Sending to {contact} ({phone})...")
        result = send_one(phone, message)
        results.append(result)
        print(f"  ✓ sent")

    return {
        "status": "done",
        "sent": len(results),
        "results": results
    }
