VOICE_MAP = {
    "en": "en-GB-RyanNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "ja": "ja-JP-KeitaNeural",
    "zh-cn": "zh-CN-YunxiNeural",
    "ar": "ar-SA-HamedNeural",
}

DEFAULT_VOICE = "en-GB-RyanNeural"

def detect_language(text: str) -> str:
    """Detect language of text, return ISO code."""
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "en"

def get_voice_for_text(text: str) -> str:
    lang = detect_language(text)
    return VOICE_MAP.get(lang, DEFAULT_VOICE)
