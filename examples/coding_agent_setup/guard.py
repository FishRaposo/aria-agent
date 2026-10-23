"""Claude command hook. Denials use exit 2; success makes no permission grant."""

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path


def safe_path(root, candidate):
    """Reject escapes and links before resolving; not an OS race-proof sandbox."""
    root = Path(root).resolve(strict=True)
    if not isinstance(candidate, str) or not candidate or "\x00" in candidate:
        raise ValueError("invalid file path")
    path = Path(candidate)
    if ".." in path.parts:
        raise ValueError("path traversal denied")
    path = path if path.is_absolute() else root / path
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("outside fixture denied") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink denied")
        if current.exists():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("reparse link denied")
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("resolved outside fixture denied")
    return resolved


def audit(root, record):
    path = safe_path(root, str(root / ".aria/audit.jsonl"))
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")


def check(payload, root):
    if not isinstance(payload, dict) or payload.get("cwd") != str(root):
        raise ValueError("missing or changed fixture cwd")
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        tool = payload.get("tool_name")
        if tool not in {"Read", "Edit", "Write"}:
            raise ValueError("tool is outside the fixture allowlist")
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            raise ValueError("malformed tool input")
        path = safe_path(root, tool_input.get("file_path"))
        relative = path.relative_to(root).as_posix()
        reads = {
            "app.py",
            "README.md",
            "notes/injection.md",
            "CLAUDE.md",
            ".agents/skills/scoped-repair/SKILL.md",
        }
        if relative not in (reads if tool == "Read" else {"app.py"}):
            raise ValueError("file path has no approved permission")
        audit(
            root,
            {
                "event": event,
                "tool": tool,
                "decision": "no_objection",
                "path": relative,
            },
        )
        return 0
    if event == "Stop":
        if type(payload.get("stop_hook_active")) is not bool:
            raise ValueError("missing Stop continuation state")
        path = safe_path(root, str(root / ".aria/verify.py"))
        spec = importlib.util.spec_from_file_location("fixture_verify", path)
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        contract = json.loads(
            (root / ".aria/contract.json").read_text(encoding="utf-8")
        )
        result = verifier.verify(root, contract["task_id"])
        audit(
            root,
            {
                "event": event,
                "verification": "passed" if result["passed"] else "failed",
                "reason": result["reason"],
            },
        )
        if result["passed"]:
            return 0
        if payload["stop_hook_active"]:
            # Avoid infinite continuation; the outer evaluator still rejects this run.
            print(
                "Verification failed; external acceptance remains blocked.",
                file=sys.stderr,
            )
            return 0
        raise ValueError("verification failed: " + result["reason"])
    raise ValueError("unexpected hook event")


def main():
    root = Path(__file__).resolve().parent.parent
    try:
        if Path(__file__).parent.name != ".aria":
            raise ValueError("run only the installed fixture hook")
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("hook input exceeds limit")
        return check(json.loads(raw), root)
    except Exception as exc:
        try:
            audit(root, {"event": "guard", "decision": "deny", "reason": str(exc)})
        except Exception:
            pass
        print(f"ARIA fixture denied: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.exit(main())
