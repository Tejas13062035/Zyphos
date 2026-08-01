import os

CANCEL_FILE = os.path.expanduser("~/zyp/state/cancel.flag")

def request_cancel():
    with open(CANCEL_FILE, "w") as f:
        f.write("cancel")

def is_cancelled() -> bool:
    return os.path.exists(CANCEL_FILE)

def clear_cancel():
    if os.path.exists(CANCEL_FILE):
        os.remove(CANCEL_FILE)
