import os
from core.llm import ask

TOOL_NAME = "diagnose"
TOOL_DESCRIPTION = "Diagnose an error message by analyzing it against common Zyphos failure patterns"
TOOL_ARGS = {"error": "str: the error message or traceback to diagnose"}

KNOWN_PATTERNS = {
    "Expecting value: line 1 column 1": "Empty or malformed JSON response — likely a reasoning-model (Cerebras gpt-oss-120b) truncation issue. Check max_tokens is 150+ on the failing call, and confirm 'reasoning_effort' param is set.",
    "Permission denied": "File lock conflict, commonly seen with TTS mp3 files being written/read simultaneously. Check that timestamped filenames are used instead of fixed names for concurrent operations.",
    "ModuleNotFoundError": "Missing PYTHONPATH or wrong venv activated. Run 'export PYTHONPATH=~/zyp' (or ~/markos for Mark.OS) and confirm 'source venv/bin/activate' was run.",
    "Connection refused": "A local service isn't running — likely the Windows sidecar (port 5000) or Ollama (port 11434). Run --doctor to check service status.",
    "IndentationError": "Python indentation broke during a nano paste — common when copy-pasting multi-line blocks. Check the specific line number in the traceback and verify indentation matches surrounding code.",
    "rate limit": "API quota likely exceeded. Run --doctor to check current usage against known free-tier limits.",
    "404": "API endpoint may have changed or been deprecated (seen with NASA Mars Photos API and REST Countries v3.1). Check the provider's current docs for the updated endpoint.",
}

def run(args=None):
    error_text = args.get("error", "") if args else ""
    if not error_text:
        return {"error": "no error text provided"}

    matched = []
    for pattern, explanation in KNOWN_PATTERNS.items():
        if pattern.lower() in error_text.lower():
            matched.append(f"Matched known pattern '{pattern}': {explanation}")

    if matched:
        result = "\n\n".join(matched)
        return {"status": "ok", "result": result, "matched_known_pattern": True}

    # no known pattern matched — ask the LLM for a general diagnosis
    diagnosis = ask(
        error_text,
        system="You are debugging a Python project called Zyphos (an AI assistant with plugins, Cerebras/Groq/Gemini LLM backends, a Windows sidecar, WSL2, FAISS memory). Given this error, suggest the most likely cause and a concrete fix in 2-3 sentences. Be specific and technical.",
        max_tokens=200
    )
    return {"status": "ok", "result": diagnosis, "matched_known_pattern": False}
