import json
from core.llm import ask

SYSTEM_PROMPT = """You are a task planner for an automation system. Given a goal, output a JSON array of tasks.

Rules:
- "search python tutorials"
- Each task has a "description" field only
- description must start with the tool name followed by arguments
- For type: write exactly "type " followed by the actual text. Never write "type TEXT ..."
- For click: write "click X Y" with real coordinates if known, else "click 0 0"
- For hotkey: write "hotkey" followed by key names e.g. "hotkey ctrl c"
- Output raw JSON array only, no markdown, no explanation

Examples:
goal: "what is on screen" → [{"description": "look what is on screen"}]
goal: "look at screen and tell me what's open" → [{"description": "look what apps are open"}]
goal: "take a screenshot" → [{"description": "screenshot"}]
goal: "type hello world" → [{"description": "type hello world"}]
goal: "press ctrl c" → [{"description": "hotkey ctrl c"}]
goal: "screenshot then type hi" → [{"description": "screenshot"}, {"description": "type hi"}]
goal: "tell a joke" → [{"description": "joke"}]
goal: "say a joke" → [{"description": "joke"}]
goal: "tell 2 jokes" → [{"description": "joke"}, {"description": "joke"}]
goal: "tell 3 jokes" → [{"description": "joke"}, {"description": "joke"}, {"description": "joke"}]"""
def smart_plan(goal: str) -> list:
    import uuid
    response = ask(goal, system=SYSTEM_PROMPT, max_tokens=300)

    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        clean = response[start:end]
        parsed = json.loads(clean)
        tasks = []
        for item in parsed:
            tasks.append({
                "id": str(uuid.uuid4())[:8],
                "description": item.get("description", ""),
                "status": "pending",
                "result": None
            })
        return tasks
    except Exception as e:
        return [{
            "id": str(uuid.uuid4())[:8],
            "description": goal,
            "status": "pending",
            "result": None
        }]
