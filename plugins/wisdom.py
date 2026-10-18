import requests
from core.llm import ask_reasoning
from core.sidecar_url import get_sidecar_url

TOOL_NAME = "wisdom"
TOOL_DESCRIPTION = "shares a philosophical quote or tells a short philosophical/moral story"
TOOL_ARGS = {"mode": "str (quote|story|dialogue)", "theme": "str (optional theme)", "author": "str (optional philosopher name)", "count": "int (optional, number of quotes/stories, default 1)"}


def _speak(text):
    try:
        from tools.sidecar import speak as _k; _k(text)
    except Exception:
        pass


def _get_quote(theme="", author=""):
    if author:
        prompt = f"Give me one real, verifiable quote from {author}"
        if theme:
            prompt += f" about {theme}"
        prompt += ". Respond with ONLY the quote in quotes followed by an em dash and the author name. No other text."
    else:
        theme_part = f" about {theme}" if theme else " about life, wisdom, or the human condition"
        prompt = (
            f"Give me one real, well-known philosophical quote{theme_part}. "
            f"Pick randomly from a WIDE range of philosophers — Nietzsche, Marcus Aurelius, Lao Tzu, "
            f"Confucius, Kant, Camus, Simone de Beauvoir, Seneca, Epictetus, Aristotle, Rumi, "
            f"or others. Avoid repeating the same philosopher every time. "
            f"Respond with ONLY the quote in quotes followed by an em dash and the author name. No other text."
        )

    result = ask_reasoning(prompt, system="You are a knowledgeable source of real philosophical quotes from diverse thinkers. Vary your author choice each time. Only cite quotes you are confident are accurate.", max_tokens=800)

    if result.startswith("LLM_ERROR"):
        return "The unexamined life is not worth living. — Socrates"

    return result.strip()


def _get_story(theme="", author=""):
    theme_prompt = f" about {theme}" if theme else ""
    style_prompt = f", written in the philosophical style and worldview of {author}" if author else ""
    prompt = f"Write a short philosophical parable or moral story{theme_prompt}{style_prompt}, in the style of Aesop or a Zen koan. Keep it under 150 words. End with a one-line moral."
    story = ask_reasoning(prompt, system="You are a wise storyteller who writes short, thought-provoking parables.", max_tokens=800)
    return story.strip()

def _get_dialogue(theme="", author=""):
    author_name = author if author else "a wise philosopher"
    theme_part = f" about {theme}" if theme else " about a fundamental question of life"
    prompt = (
        f"Write a short Socratic-style dialogue{theme_part} between {author_name} and a curious student. "
        f"Format EXACTLY like this, one line per turn, no extra text:\n"
        f"STUDENT: [line]\n"
        f"{author_name.upper()}: [line]\n"
        f"(continue for 4-6 exchanges total, end with a one-line moral prefixed by MORAL:)"
    )
    result = ask_reasoning(prompt, system="You write short, insightful philosophical dialogues in clean alternating format.", max_tokens=800)

    if result.startswith("LLM_ERROR"):
        return "STUDENT: What is wisdom?\nPHILOSOPHER: Knowing that you know nothing.\nMORAL: True wisdom begins with humility."

    return result.strip()


NARRATOR_VOICE = "am_onyx"
STUDENT_VOICE = "af_nova"
PHILOSOPHER_VOICE = "bm_fable"


NARRATOR_VOICE = "am_onyx"
STUDENT_VOICE = "af_nova"
PHILOSOPHER_VOICE = "bm_fable"


NARRATOR_VOICE = "am_onyx"
STUDENT_VOICE = "af_nova"
PHILOSOPHER_VOICE = "bm_fable"


NARRATOR_VOICE = "am_echo"
STUDENT_VOICE = "af_nova"
PHILOSOPHER_VOICE = "af_sky"


def _speak_dialogue(dialogue_text: str):
    import queue
    import threading
    from tools.sidecar import _kokoro_file, play_file, _strip_markdown

    batch = []
    for line in [l.strip() for l in dialogue_text.split("\n") if l.strip() and ":" in l]:
        speaker, _, text = line.partition(":")
        speaker, text = speaker.strip().upper(), _strip_markdown(text.strip())
        if not text:
            continue
        if speaker == "MORAL":
            batch.append((f"The moral is: {text}", NARRATOR_VOICE))
        elif speaker == "STUDENT":
            batch.append((text, STUDENT_VOICE))
        else:
            batch.append((text, PHILOSOPHER_VOICE))
    if not batch:
        return

    q = queue.Queue(maxsize=2)

    def producer():
        try:
            for text, voice in batch:
                q.put(_kokoro_file(text, voice))
        except Exception as e:
            print(f"[wisdom] speech generation failed: {e}")
        finally:
            q.put(None)

    threading.Thread(target=producer, daemon=True).start()
    while True:
        path = q.get()
        if path is None:
            break
        try:
            play_file(path)
        except Exception as e:
            print(f"[wisdom] playback failed: {e}")
            break

def run(args: dict) -> dict:
    mode = args.get("mode", "quote").lower()
    theme = args.get("theme", "")
    author = args.get("author", "")
    count = args.get("count", 1)
    silent = args.get("silent", False)

    try:
        results = []
        for _ in range(max(1, count)):
            if mode == "story":
                results.append(_get_story(theme, author))
            elif mode == "dialogue":
                results.append(_get_dialogue(theme, author))
            else:
                results.append(_get_quote(theme, author))

        combined = "\n\n---\n\n".join(results)

        if not silent:
            if mode == "dialogue":
                _speak_dialogue(results[0])
            else:
                for r in results:
                    _speak(r)

        return {"status": "ok", "result": combined}
    except Exception as e:
        return {"status": "error", "result": f"wisdom failed: {e}"}
