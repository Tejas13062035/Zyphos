import os
from pypdf import PdfReader
from core.llm import ask
import re

def _strip_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)        # italic
    text = re.sub(r'#{1,6}\s*', '', text)           # headers
    text = re.sub(r'`(.*?)`', r'\1', text)           # inline code
    return text

TOOL_NAME = "pdf_summary"
TOOL_DESCRIPTION = "Read and summarize a PDF file"
TOOL_ARGS = {"path": "str: path to the PDF file", "pages": "int (optional): max pages to read, default 20"}

def run(args=None):
    path = args.get("path", "") if args else ""
    max_pages = int(args.get("pages", 20)) if args else 20

    if not path:
        return {"error": "no path provided"}

    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return {"error": f"file not found: {path}"}

    try:
        reader = PdfReader(path)
        total_pages = len(reader.pages)
        text_chunks = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text()
            if text:
                text_chunks.append(text)

        full_text = "\n".join(text_chunks)
        if not full_text.strip():
            return {"error": "no extractable text found (may be a scanned/image PDF)"}

        # truncate to keep prompt reasonable
        truncated = full_text[:6000]

        summary = ask(
            truncated,
            system="Summarize this PDF content in 3-5 clear paragraphs. Cover the main points, key facts, and conclusions. Be concise and factual.",
            max_tokens=500
        )

        summary = _strip_markdown(summary)

        return {
            "status": "ok",
            "result": summary,
            "pages_read": min(max_pages, total_pages),
            "total_pages": total_pages
        }
    except Exception as e:
        return {"error": str(e)}
