import requests
import time

TOOL_NAME = "whatsapp"
TOOL_DESCRIPTION = "Send WhatsApp messages via WhatsApp Web"
TOOL_ARGS = {"phone": "phone number with country code e.g. 919229420080", "message": "message text"}

from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

CONTACTS = {
    "mom": "917488640558",
    "dad": "918709306282",
    "dr. shalu di": "917004895930",
    "chunni di": "919162552922",
    "jhunni di": "916202743566",
}

def run(args: dict) -> dict:
    phone = args.get("phone", "")
    message = args.get("message", "")
    name = args.get("name", "").lower()

    if name and name in CONTACTS:
        phone = CONTACTS[name]

    if not phone:
        return {"error": "phone number required"}

    url = f"https://web.whatsapp.com/send?phone={phone}&text={message}"
    r = requests.post(f"{SIDECAR_URL}/open_url", json={"url": url})
    time.sleep(6)  # wait for WhatsApp Web to load

    # click message input box to focus it
    requests.post(f"{SIDECAR_URL}/click", json={"x": 1300, "y": 752})
    time.sleep(1)

    # press Enter to send
    requests.post(f"{SIDECAR_URL}/hotkey", json={"keys": ["enter"]})

    return {"status": "sent", "phone": phone, "message": message}
