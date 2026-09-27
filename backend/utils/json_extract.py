import json
from typing import Optional

def extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    content = text
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
    content = content.strip()
    if not content.startswith("{"):
        i = content.find("{")
        if i == -1:
            return None
        content = content[i:]
    if not content.endswith("}"):
        j = content.rfind("}")
        if j == -1:
            return None
        content = content[: j + 1]
    try:
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None
