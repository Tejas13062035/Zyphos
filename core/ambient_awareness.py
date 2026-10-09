from tools.watch_for_face import watch_until_resolved
from core.greeter_ambient import greet
from core.enrollment import handle_unknown


def run_ambient_cycle(greet_on_gave_up=True, enroll_unknown=True):
    """Full pipeline: called when someone arrives. Watches for a face, then routes
    to the correct outcome: greet known/close, enroll unknown, or generic
    greeting on gave_up. The two flags let callers stay quiet on weak results."""
    result = watch_until_resolved()

    if result["status"] == "known":
        greet(result)
        return result

    if result["status"] == "gave_up":
        if greet_on_gave_up:
            greet(result)
        return result

    if result["status"] == "unknown":
        if enroll_unknown:
            return handle_unknown(result)
        return result

    return result
