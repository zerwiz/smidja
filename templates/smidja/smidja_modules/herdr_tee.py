"""Filter for a seated turn: stdin is pi's JSON stream; the raw lines go to a file the
engine tails, and a readable view of the turn is printed for the person in the pane."""

import json
import sys


def _brief(event: dict) -> str:
    kind = event.get("type", "")
    if kind == "message_end":
        msg = event.get("message", {})
        if msg.get("role") == "assistant":
            parts = [c.get("text", "") for c in msg.get("content", []) if isinstance(c, dict) and c.get("type") == "text"]
            return "\n".join(p for p in parts if p).strip()
    if kind in ("tool_execution_start", "tool_call"):
        name = event.get("toolName") or event.get("name") or "tool"
        args = event.get("args") or event.get("arguments") or {}
        hint = next((str(args[k]) for k in ("command", "path", "file_path", "pattern", "query") if isinstance(args, dict) and k in args), "")
        return f"-> {name} {hint}"[:200]
    return ""


def main() -> int:
    raw = open(sys.argv[1], "a")
    for line in sys.stdin:
        raw.write(line)
        raw.flush()
        try:
            text = _brief(json.loads(line))
        except ValueError:
            text = ""
        if text:
            print(text, flush=True)
    raw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
