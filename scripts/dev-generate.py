#!/usr/bin/env python3
"""dev-generate.py — Prompt iteration tool for Character Map Generator.

Calls the LLM pipeline directly and prints raw JSON to stdout.
Bypasses database, Redis, resolver, rendering, email, Turnstile.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure backend app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load .env from repo root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from app.config import settings
from app.worker.pipeline import call_and_validate, RefusalError, _load_prompt_template, REFUSAL_MESSAGES
from app.llm.anthropic_client import AnthropicClient


async def _run(args) -> str:
    creator = args.author or args.director
    author_or_director = creator or "Unknown"

    system_prompt = _load_prompt_template()
    if args.prompt_file:
        system_prompt = Path(args.prompt_file).read_text()

    user_message = (
        f"<work_metadata>\n"
        f"title: {args.title}\n"
        f"year: {args.year or 'Unknown'}\n"
        f"author_or_director: {author_or_director}\n"
        f"type: {args.work_type}\n"
        f"</work_metadata>\n\n"
        f"<user_query>\n"
        f"{args.title}\n"
        f"</user_query>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. No prose, no markdown fences."
    )

    if args.model.startswith("claude-"):
        client = AnthropicClient(model=args.model, api_key=settings.anthropic_api_key)
    else:
        print(f"[dev-generate] Model {args.model!r} not yet wired (Phase 5)", file=sys.stderr)
        sys.exit(1)

    try:
        char_map, llm_result = await call_and_validate(client, system_prompt, user_message)
    except RefusalError as e:
        msg = REFUSAL_MESSAGES.get(e.refusal_code, REFUSAL_MESSAGES["unknown_work"])
        print(f"[dev-generate] Refused: {e.refusal_code} — {msg}", file=sys.stderr)
        return json.dumps({"refusal": e.refusal_code})

    print(
        f"[dev-generate] {args.model} | "
        f"in={llm_result.input_tokens} out={llm_result.output_tokens} "
        f"cost=${llm_result.cost_usd:.4f} | "
        f"chars={len(char_map.characters)} rels={len(char_map.relationships)}",
        file=sys.stderr,
    )
    return char_map.model_dump_json(indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a character map for a book or film directly via the LLM pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/dev-generate.py --title "Marekors" --author "Jo Nesbø" --year 2003 --work-type book
  python scripts/dev-generate.py --title "Congo" --author "Michael Crichton" --year 1980 --work-type book --save /tmp/congo.json
  python scripts/dev-generate.py --title "Marekors" --year 2003 --author "Jo Nesbø" | jq '.characters[] | {name, spoiler_level}'
""",
    )

    parser.add_argument("--title", required=True)
    parser.add_argument("--year", type=int)

    creator_group = parser.add_mutually_exclusive_group()
    creator_group.add_argument("--author")
    creator_group.add_argument("--director")

    parser.add_argument("--work-type", choices=["book", "film_tv"], default="book")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        choices=["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001", "gpt-5.5", "gemini-2.5-pro"],
    )
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--include-actors", action="store_true")

    args = parser.parse_args()

    output = asyncio.run(_run(args))

    if args.save:
        args.save.write_text(output)
        print(f"Saved to {args.save}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
