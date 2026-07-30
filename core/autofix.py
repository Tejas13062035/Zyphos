import os
import subprocess
from core.llm import ask
from plugins.diagnose import KNOWN_PATTERNS

ZYP_ROOT = os.path.expanduser("~/zyp")

# files that ALWAYS require human review, regardless of what the fix looks like
HIGH_RISK_FILES = [
    "core/voice_auth.py",
    "core/llm.py",  # touches API keys and auth headers
    ".env",
    "core/daemon.py",
    "plugins/security.py",
    "plugins/whatsapp.py",
    "plugins/whatsapp_bulk.py",
    "plugins/gmail.py",
]

def is_high_risk(filepath: str) -> bool:
    rel_path = filepath.replace(ZYP_ROOT + "/", "")
    return any(rel_path == hr or rel_path.startswith(hr) for hr in HIGH_RISK_FILES)

def is_known_safe_pattern(error_text: str) -> bool:
    """Only Tier 1 auto-fix if the error matches one of our known, low-risk patterns."""
    return any(pattern.lower() in error_text.lower() for pattern in KNOWN_PATTERNS)

def run_tests() -> tuple:
    """Run the plugin smoke test suite. Returns (passed: bool, output: str)."""
    result = subprocess.run(
        ["python", "tests/test_plugins.py"],
        capture_output=True, text=True, cwd=ZYP_ROOT, timeout=120
    )
    passed = result.returncode == 0
    return passed, result.stdout + result.stderr

def run_doctor() -> tuple:
    """Run --doctor and check for 'All systems operational'."""
    result = subprocess.run(
        ["python", "zyphos.py", "--doctor"],
        capture_output=True, text=True, cwd=ZYP_ROOT, timeout=60
    )
    passed = "operational" in result.stdout
    return passed, result.stdout

def propose_fix(filepath: str, error_text: str) -> str:
    """Ask the LLM to generate a fix for the given file and error."""
    full_path = os.path.join(ZYP_ROOT, filepath)
    if not os.path.exists(full_path):
        return None

    with open(full_path) as f:
        current_content = f.read()

    fix = ask(
        f"FILE: {filepath}\n\nCURRENT CONTENT:\n{current_content[:4000]}\n\nERROR:\n{error_text}",
        system="You are fixing a bug in a Python file. Return ONLY the complete corrected file content, no explanation, no markdown fences. The fix must be minimal and targeted — do not refactor unrelated code.",
        max_tokens=2000
    )
    return fix

def attempt_autofix(filepath: str, error_text: str) -> dict:
    """
    Full Tier-1 autofix pipeline:
    1. Reject if file is high-risk (requires human review)
    2. Reject if error doesn't match a known safe pattern
    3. Generate fix, write to file
    4. Run test suite + doctor
    5. If both pass: commit. If either fails: revert and flag for human review.
    """
    if is_high_risk(filepath):
        return {"status": "human_review_required", "reason": f"{filepath} is a high-risk file — auto-fix disabled"}

    if not is_known_safe_pattern(error_text):
        return {"status": "human_review_required", "reason": "error does not match a known safe pattern"}

    full_path = os.path.join(ZYP_ROOT, filepath)
    with open(full_path) as f:
        backup_content = f.read()

    proposed_fix = propose_fix(filepath, error_text)
    if not proposed_fix:
        return {"status": "failed", "reason": "could not generate fix"}

    # write the proposed fix
    with open(full_path, "w") as f:
        f.write(proposed_fix)

    tests_ok, test_output = run_tests()
    doctor_ok, doctor_output = run_doctor()

    if tests_ok and doctor_ok:
        subprocess.run(["git", "add", filepath], cwd=ZYP_ROOT)
        subprocess.run(
            ["git", "commit", "-m", f"autofix: {filepath} — {error_text[:60]}"],
            cwd=ZYP_ROOT
        )
        return {
            "status": "committed",
            "file": filepath,
            "test_output": test_output[-500:],
            "doctor_output": doctor_output[-300:]
        }
    else:
        # revert on any failure
        with open(full_path, "w") as f:
            f.write(backup_content)
        return {
            "status": "reverted",
            "reason": "tests or doctor check failed after fix",
            "test_output": test_output[-500:],
            "doctor_output": doctor_output[-300:]
        }
