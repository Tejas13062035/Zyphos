import warnings
import os
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import os
import numpy as np
from datetime import datetime

MEMORY_FILE = os.path.expanduser("~/zyp/state/memory.json")
INDEX_FILE = os.path.expanduser("~/zyp/state/memory.index")

_model = None
_index = None
_entries = []


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_index():
    global _index, _entries
    import faiss
    if _index is None:
        _entries = _load_entries()
        if os.path.exists(INDEX_FILE) and _entries:
            _index = faiss.read_index(INDEX_FILE)
        else:
            _index = faiss.IndexFlatL2(384)
            if _entries:
                model = _get_model()
                vectors = model.encode([e["goal"] for e in _entries]).astype("float32")
                _index.add(vectors)
                faiss.write_index(_index, INDEX_FILE)
    return _index


def _load_entries():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_entries(entries):
    with open(MEMORY_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def save(goal: str, tasks: list):
    global _index, _entries
    import faiss

    clean_tasks = []
    for t in tasks:
        if isinstance(t, dict):
            desc = t.get("description", "")
            result = t.get("result", {})
            if isinstance(result, dict):
                # strip base64 image blobs before storing
                cleaned = {k: v for k, v in result.items() if k != "image"}
                result_str = (
                    cleaned.get("result") or
                    cleaned.get("status") or
                    cleaned.get("saved") or
                    cleaned.get("content") or
                    cleaned.get("output") or
                    str(cleaned)
                )
            else:
                result_str = str(result) if result else ""
        else:
            desc = str(t)
            result_str = ""
        clean_tasks.append({"description": desc, "result": result_str})

    entry = {
        "goal": goal,
        "tasks": clean_tasks,
        "timestamp": datetime.now().isoformat()
    }

    _entries = _load_entries()
    _entries.append(entry)
    _save_entries(_entries)

    model = _get_model()
    vector = model.encode([goal]).astype("float32")
    index = _get_index()
    index.add(vector)
    index = _get_index()
    index.add(vector)
    import faiss
    faiss.write_index(index, INDEX_FILE)
    print(f"MEMORY: saved + indexed ({len(_entries)} total)")


def recall(query: str, top_k: int = 5) -> list:
    entries = _load_entries()
    if not entries:
        return []

    # if query is an int (legacy call), fall back to last N
    if isinstance(query, int):
        return entries[-query:]

    model = _get_model()
    index = _get_index()

    vector = model.encode([query]).astype("float32")
    k = min(top_k, len(entries))
    distances, indices = index.search(vector, k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(entries):
            results.append(entries[idx])
    return results

def forget(query: str) -> int:
    """
    Deletes memory entries matching the query (exact substring match on goal text).
    Rebuilds the FAISS index after deletion.
    Returns the number of entries deleted.
    """
    global _index, _entries
    import faiss

    entries = _load_entries()
    original_count = len(entries)

    remaining = [e for e in entries if query.lower() not in e["goal"].lower()]
    deleted_count = original_count - len(remaining)

    if deleted_count == 0:
        return 0

    _save_entries(remaining)
    _entries = remaining

    # rebuild index from scratch
    model = _get_model()
    _index = faiss.IndexFlatL2(384)
    if remaining:
        vectors = model.encode([e["goal"] for e in remaining]).astype("float32")
        _index.add(vectors)

    faiss.write_index(_index, INDEX_FILE)
    return deleted_count
