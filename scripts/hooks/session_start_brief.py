#!/usr/bin/env python3
"""
SessionStart hook — project-bootstrap template (no-pillar mode).

Reads Planka credentials from .mcp.json so it works without exporting env vars.
Auto-injects a session brief: last chronicle entry, top 5 In Progress + top 5
ToDo cards by recently updated, and last 3 git commits.

Replace 1777578866382997173 with the actual board ID before installing.
If the project doesn't use Planka, leave it as-is — the hook gracefully skips
the cards section.

Time budget: 5 seconds. Fails gracefully — any error becomes a one-line note,
never blocks session start.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PLANKA_BOARD_ID = "1777578866382997173"  # replace at install time
PROJECT_NAME = "Character Map Generator"  # replace at install time


def find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for _ in range(20):
        if (cur / ".git").exists():
            return cur
        if cur == cur.parent:
            return None
        cur = cur.parent
    return None


def get_planka_creds(repo_root: Path) -> dict | None:
    mcp_path = repo_root / ".mcp.json"
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text())
            planka = data.get("mcpServers", {}).get("planka", {}).get("env", {})
            base_url = planka.get("PLANKA_BASE_URL", "https://kanban.torgersen.ai")
            username = planka.get("PLANKA_USERNAME")
            password_raw = planka.get("PLANKA_PASSWORD", "")
            if password_raw.startswith("${") and password_raw.endswith("}"):
                password = os.environ.get(password_raw[2:-1])
            elif password_raw.startswith("$"):
                password = os.environ.get(password_raw[1:])
            else:
                password = password_raw
            if username and password:
                return {"base_url": base_url, "username": username, "password": password}
        except Exception:
            pass
    user = os.environ.get("PLANKA_USERNAME")
    pwd = os.environ.get("PLANKA_PASSWORD")
    if user and pwd:
        return {
            "base_url": os.environ.get("PLANKA_BASE_URL", "https://kanban.torgersen.ai"),
            "username": user,
            "password": pwd,
        }
    return None


def last_chronicle_entry(repo_root: Path) -> dict | None:
    chronicle = repo_root / "docs" / "SESSION_CHRONICLE.md"
    if not chronicle.exists():
        return None
    content = chronicle.read_text()
    m = re.search(r"^## (.+)$", content, re.MULTILINE)
    if not m:
        return None
    return {"heading": m.group(1).strip()}


def recent_commits(repo_root: Path, n: int = 3) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--oneline", f"-{n}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return [line for line in out.stdout.strip().split("\n") if line]
    except Exception:
        return []


def fetch_planka_cards(creds: dict, timeout: float = 4.0) -> dict | None:
    if PLANKA_BOARD_ID.startswith("__") or not PLANKA_BOARD_ID:
        return None
    try:
        login_data = urllib.parse.urlencode(
            {"emailOrUsername": creds["username"], "password": creds["password"]}
        ).encode()
        req = urllib.request.Request(
            f"{creds['base_url']}/api/access-tokens",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            token = json.loads(r.read())["item"]
        req = urllib.request.Request(
            f"{creds['base_url']}/api/boards/{PLANKA_BOARD_ID}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        inc = data.get("included", {})
        lists = {L["id"]: L["name"] for L in inc.get("lists", [])}
        cards = sorted(
            inc.get("cards", []),
            key=lambda c: c.get("updatedAt") or c.get("createdAt") or "",
            reverse=True,
        )
        result = {"todo": [], "in_progress": []}
        for c in cards:
            list_name = lists.get(c.get("listId"), "")
            name = c.get("name", "")[:90]
            if list_name == "ToDo" and len(result["todo"]) < 5:
                result["todo"].append(name)
            elif list_name == "In Progress" and len(result["in_progress"]) < 5:
                result["in_progress"].append(name)
            if len(result["todo"]) >= 5 and len(result["in_progress"]) >= 5:
                break
        return result
    except Exception:
        return None


def build_brief(repo_root: Path) -> str:
    chronicle = last_chronicle_entry(repo_root)
    commits = recent_commits(repo_root)
    creds = get_planka_creds(repo_root)
    cards = fetch_planka_cards(creds) if creds else None

    name = PROJECT_NAME if not PROJECT_NAME.startswith("__") else repo_root.name
    lines = [f"### Session brief — {name}"]

    if chronicle:
        lines.append(f"\n**Last chronicle:** {chronicle['heading']}")

    if cards is not None:
        ip_count = len(cards["in_progress"])
        td_count = len(cards["todo"])
        lines.append(
            f"\n**Active Planka — top {ip_count} In Progress + top {td_count} ToDo by recent activity:**"
        )
        if cards["in_progress"]:
            for c in cards["in_progress"]:
                lines.append(f"  [In Progress] {c}")
        else:
            lines.append("  (no In Progress cards)")
        if cards["todo"]:
            for c in cards["todo"]:
                lines.append(f"  [ToDo] {c}")
        else:
            lines.append("  (no ToDo cards)")

    if commits:
        lines.append("\n**Recent commits:**")
        for line in commits:
            lines.append(f"  {line}")

    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdin.read()
    except Exception:
        pass

    try:
        repo_root = find_repo_root(Path.cwd())
        brief = build_brief(repo_root) if repo_root else ""
    except Exception as e:
        brief = f"[session_start_brief hook error: {type(e).__name__}: {e}]"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": brief,
        }
    }))


if __name__ == "__main__":
    main()
