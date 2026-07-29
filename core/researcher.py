import os
from plugins.wigolo import run as wigolo_run
from plugins.webintel import run as webintel_run
from core.llm import ask

REPORTS_DIR = os.path.expanduser("~/zyp/reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

NEXT_QUERY_PROMPT = """Research topic: {topic}
Notes so far: {summary}
Give ONE short follow-up search query (5 words max). Only the query, nothing else."""

REPORT_PROMPT = """Write a research report on: {topic}
Based on these notes:
{notes}
Write 3-5 paragraphs. Facts only. No fluff."""

def research(topic: str, depth: int = 3) -> str:
    print(f"\nRESEARCH: {topic}")
    notes = []
    query = topic

    for i in range(depth):
        print(f"[Round {i+1}] Query: {query}")

        # Use wigolo's reranked search — better quality than raw DuckDuckGo
        search_result = wigolo_run({"action": "search", "query": query})
        summary_text = search_result.get("result", "")
        if summary_text and summary_text != "no results":
            notes.append(f"Search round {i+1} ({query}):\n{summary_text}")
            print(f"  Added {len(summary_text)} chars from wigolo search")

        # Deep-dive: use wigolo's dedicated research action once per topic for a synthesized brief
        if i == 0:
            deep = wigolo_run({"action": "research", "query": topic})
            deep_text = deep.get("result", "")
            if deep_text:
                notes.append(f"Wigolo research brief:\n{deep_text}")
                print(f"  Added wigolo research brief ({len(deep_text)} chars)")

        FALLBACK_ANGLES = ["latest developments", "recent breakthroughs", "expert analysis", "future outlook", "key challenges"]

        if i < depth - 1 and notes:
            all_notes = "\n\n".join(notes[-4:])
            raw_query = ask(
                f"Topic: {topic}\nNotes: {all_notes[:800]}",
                system=NEXT_QUERY_PROMPT.format(topic=topic, summary=all_notes[:500]),
                max_tokens=150
            ).strip()
            if raw_query.startswith("LLM_ERROR") or raw_query.startswith("{"):
                # fallback: diversify by appending a different angle each round instead of repeating the exact same query
                angle = FALLBACK_ANGLES[i % len(FALLBACK_ANGLES)]
                query = f"{topic} {angle}"
                print(f"  Query generation failed, using fallback angle: '{angle}'")
            else:
                query = raw_query.replace('"', '').replace("Search query:", "").strip()
                # detect and fix duplicated-phrase glitches (e.g. "xyzxyz" with no space)
                half = len(query) // 2
                if len(query) > 10 and query[:half] == query[half:]:
                    query = query[:half]
                    print(f"  Detected duplicated query, trimmed to: '{query}'")
                # guard against overly long or malformed queries slipping through
                if len(query) > 80 or not query:
                    angle = FALLBACK_ANGLES[i % len(FALLBACK_ANGLES)]
                    query = f"{topic} {angle}"
                    print(f"  Query malformed, using fallback angle: '{angle}'")
            print(f"  Next query: {query}")

    if not notes:
        return "No research data found."

    print("\nGenerating report...")
    all_notes = "\n\n".join(notes)

    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": REPORT_PROMPT.format(topic=topic, notes=all_notes[:4000])},
                {"role": "user", "content": all_notes[:4000]}
            ],
            max_tokens=600
        )
        report = response.choices[0].message.content.strip()
    except Exception as e:
        report = f"Report generation failed: {e}"

    filename = topic.replace(" ", "_")[:50] + ".txt"
    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, "w") as f:
        f.write(f"RESEARCH REPORT: {topic}\n")
        f.write("="*50 + "\n\n")
        f.write(report)
        f.write("\n\nRAW NOTES:\n")
        for n in notes:
            f.write(f"\n---\n{n[:500]}\n")

    print(f"Report saved: {filepath}")
    return report

def research_deep_page(url: str) -> str:
    """Read a specific page in full via Jina Reader — useful for citing a specific source."""
    result = webintel_run({"action": "read_page", "target": url})
    return result.get("result", "")
