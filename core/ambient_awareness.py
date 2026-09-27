from tools.watch_for_face import watch_until_resolved
from core.greeter_ambient import greet
from core.enrollment import handle_unknown


def run_ambient_cycle():
    """Full pipeline: called when PIR fires. Watches for a face, then routes
    to the correct outcome: greet known/close, enroll unknown, or generic
    greeting on gave_up."""
    result = watch_until_resolved()

    if result["status"] in ("known", "gave_up"):
        greet(result)
        return result

    elif result["status"] == "unknown":
        return handle_unknown(result)

    return result
