import subprocess
from core.llm import ask

TOOL_NAME = "session_summary"
TOOL_DESCRIPTION = "Summarize recent git commits into a readable changelog entry"
TOOL_ARGS = {"count": "int: number of recent commits to summarize, default 10"}

def run(args=None):
    count = int(args.get("count", 10)) if args else 10

    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--oneline"],
            capture_output=True, text=True, cwd="/home/tejas100x/zyp", timeout=10
        )
        commits = result.stdout.strip()
        if not commits:
            return {"error": "no commits found"}

        summary = ask(
            commits,
            system="Given this git commit log, write a short 3-5 sentence summary of what was accomplished in this session. Group related commits together. Plain prose, no markdown formatting.",
            max_tokens=300
        )

        return {"status": "ok", "result": summary, "commit_count": len(commits.splitlines())}
    except Exception as e:
        return {"error": str(e)}
