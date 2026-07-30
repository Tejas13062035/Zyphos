"""
Lightweight smoke test for all Zyphos plugins.
Calls each plugin's run() with safe dummy args and checks it doesn't crash
and returns a dict with a 'status' or 'error' key.

Run with: python -m pytest tests/test_plugins.py -v
or standalone: python tests/test_plugins.py
"""
import sys
import os
sys.path.insert(0, os.path.expanduser("~/zyp"))

from core.plugin_loader import load_plugins

# safe dummy args per plugin — avoids sending real messages, spending money,
# or triggering destructive actions during tests
DUMMY_ARGS = {
    "whatsapp": {"contact": "test", "message": "test"},
    "whatsapp_bulk": {"contacts": [], "message": "test"},
    "gmail": {"action": "read"},
    "drive": {"action": "list"},
    "calendar": {"action": "today"},
    "file_organizer": {"path": "/tmp"},
    "notes": {"action": "list"},
    "timer": {"minutes": 0.01, "message": "test", "block": False},
    "pdf_summary": {"path": "/nonexistent.pdf"},
    "ocr": {"source": "/nonexistent.png"},
    "github_clone": {"action": "clone", "owner": "test", "repo": "test", "path": "/tmp/nonexistent"},
    "network_scan": {},
    "port_scanner": {"target": "127.0.0.1", "ports": "80"},
    "security": {"action": "password"},
}

PLUGINS_TO_SKIP = {"hello"}  # example/template plugin, not a real tool


def test_all_plugins():
    plugins = load_plugins()
    failures = []

    for name, plugin in plugins.items():
        if name in PLUGINS_TO_SKIP:
            continue

        args = DUMMY_ARGS.get(name, {})
        try:
            result = plugin["run"](args)
            if not isinstance(result, dict):
                failures.append(f"{name}: run() did not return a dict (got {type(result)})")
            elif "status" not in result and "error" not in result:
                failures.append(f"{name}: result missing both 'status' and 'error' keys")
        except Exception as e:
            failures.append(f"{name}: raised exception — {e}")

    if failures:
        print(f"\n{len(failures)} plugin(s) failed:")
        for f in failures:
            print(f"  - {f}")
    else:
        print(f"\nAll {len(plugins) - len(PLUGINS_TO_SKIP)} plugins passed smoke test.")

    assert not failures, f"{len(failures)} plugin(s) failed the smoke test"


if __name__ == "__main__":
    test_all_plugins()
