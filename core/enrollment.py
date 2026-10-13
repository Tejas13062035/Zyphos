import re
from core.greeter_ambient import greet
from core.llm import ask_chat
from tools.stt import listen_unattended
from tools.pending_clusters import resolve_cluster

# Common phrasings people use when stating their name — captures just the name part
_NAME_PATTERNS = [
    r"(?:my name is|i am|i'm|it's|its|call me|this is)\s+([A-Za-z]+(?:\s[A-Za-z]+)?)\.?$",
    r"^([A-Za-z]+(?:\s[A-Za-z]+)?)\.?$",  # bare name with nothing else, e.g. "Tejas"
]

# One- or two-word replies that are NOT names. Without this, "Yes" or "Hello" gets enrolled as the person's name.
_NOT_NAMES = {
    "yes", "yeah", "yep", "no", "nope", "hello", "hi", "hey", "okay", "ok", "sure", "fine", "good",
    "what", "who", "why", "huh", "sorry", "thanks", "thank", "please", "stop", "cancel", "nothing",
    "none", "nevermind", "maybe", "hmm", "um", "uh", "you", "me", "here", "welcome", "pardon",
}


def _extract_name_simple(text: str) -> str | None:
    """Step 1: cheap regex extraction for common phrasings. Returns None if
    nothing confidently matches, so the caller can fall back to the LLM."""
    text = text.strip()
    for pattern in _NAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if (name and len(name.split()) <= 2
                    and not any(w.lower() in _NOT_NAMES for w in name.split())):
                return name.title()
    return None


def _extract_name_llm(text: str) -> str | None:
    """Step 2: LLM fallback for phrasing the regex doesn't catch. Returns None
    if the model can't find a name either."""
    prompt = (
        f'Someone was asked their name and said: "{text}"\n'
        f"Extract ONLY their name, nothing else. If no name is actually present, "
        f'respond with exactly: NONE'
    )
    result = ask_chat(prompt, max_tokens=20).strip().strip(".\"'")
    if result.upper() == "NONE" or not result:
        return None
    words = result.split()
    if len(words) > 2 or not all(w.isalpha() for w in words):
        return None
    if any(w.lower() in _NOT_NAMES for w in words):
        return None
    return result.title()


def extract_name(text: str) -> str | None:
    """Two-step name extraction: cheap regex first, LLM fallback second."""
    name = _extract_name_simple(text)
    if name:
        return name
    return _extract_name_llm(text)


def handle_unknown(watch_result: dict):
    """Full flow for an unresolved/unknown face: speak the greeting+name request,
    listen once (internally retries up to 3x on low confidence), extract the
    actual name from whatever was said, then resolve or leave pending."""
    greet(watch_result)

    raw = listen_unattended()

    if raw:
        name = extract_name(raw)
        if name:
            cluster_id = watch_result["cluster_id"]
            try:
                resolve_cluster(cluster_id, name, category="known")
                return {"status": "enrolled", "name": name}
            except FileExistsError as e:
                return {"status": "enroll_failed", "reason": str(e)}
        else:
            # heard something, but couldn't extract a name from it — leave pending
            return {"status": "pending", "cluster_id": watch_result["cluster_id"], "raw_heard": raw}
    else:
        return {"status": "pending", "cluster_id": watch_result["cluster_id"]}
