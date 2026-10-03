# Kokoro-82M supports 8 languages: American/British English, Spanish, French,
# Hindi, Japanese, Mandarin, Italian, Brazilian Portuguese.
# German (de) and Arabic (ar) are NOT supported by Kokoro — both fall back to
# DEFAULT_VOICE below. If either language matters, a separate TTS engine
# would be needed just for those two.
VOICE_MAP = {
    "en": "bm_george",
    "hi": "hf_alpha",
    "es": "em_alex",
    "fr": "ff_siwis",
    "ja": "jm_kumo",
    "zh-cn": "zm_yunxi",
}

DEFAULT_VOICE = "bm_george"

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
