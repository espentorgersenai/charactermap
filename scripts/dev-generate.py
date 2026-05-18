#!/usr/bin/env python3
"""dev-generate.py — Prompt iteration tool for Character Map Generator.

Calls the LLM pipeline directly and prints raw JSON to stdout.
Bypasses database, Redis, resolver, rendering, email, Turnstile.
Phase 1: skeleton that parses flags and prints what it would call.
Phase 2 will wire this to the actual LLM client.
"""

import argparse
import sys
from pathlib import Path

# Load .env from repo root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv optional; env vars can be set directly


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

    # Work metadata
    parser.add_argument("--title", required=True, help="Title of the work")
    parser.add_argument("--year", type=int, help="Publication year")

    # Author or director (mutually exclusive)
    creator_group = parser.add_mutually_exclusive_group()
    creator_group.add_argument("--author", help="Author (for books)")
    creator_group.add_argument("--director", help="Director (for films/TV)")

    parser.add_argument(
        "--work-type",
        choices=["book", "film_tv"],
        default="book",
        help="Work type (default: book)",
    )

    # Model
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        choices=[
            "claude-sonnet-4-6",
            "claude-opus-4-7",
            "claude-haiku-4-5-20251001",
            "gpt-5.5",
            "gemini-2.5-pro",
        ],
        help="LLM model to use (default: claude-sonnet-4-6)",
    )

    # Prompt and output control
    parser.add_argument("--prompt-file", type=Path, help="Alternate prompt template file")
    parser.add_argument("--save", type=Path, help="Write JSON output to this file instead of stdout")
    parser.add_argument("--temperature", type=float, help="Override temperature (for determinism testing)")
    parser.add_argument("--seed", type=int, help="Seed for models that support it")
    parser.add_argument(
        "--include-actors",
        action="store_true",
        help="Also run the actor-mapping LLM call (skipped by default)",
    )

    args = parser.parse_args()

    creator = args.author or args.director
    creator_label = "author" if args.author else "director" if args.director else None

    # Phase 1: print what would be called (LLM not wired yet)
    print(f"[Phase 1 skeleton — LLM not wired yet]", file=sys.stderr)
    print(f"Would call: model={args.model}", file=sys.stderr)
    print(f"  title:     {args.title!r}", file=sys.stderr)
    if args.year:
        print(f"  year:      {args.year}", file=sys.stderr)
    if creator:
        print(f"  {creator_label}: {creator!r}", file=sys.stderr)
    print(f"  work_type: {args.work_type}", file=sys.stderr)
    if args.temperature is not None:
        print(f"  temperature: {args.temperature}", file=sys.stderr)
    if args.seed is not None:
        print(f"  seed: {args.seed}", file=sys.stderr)
    if args.prompt_file:
        print(f"  prompt_file: {args.prompt_file}", file=sys.stderr)
    if args.include_actors:
        print(f"  include_actors: True", file=sys.stderr)

    # Emit a stub JSON so piping to jq doesn't immediately break
    import json
    stub = {
        "__phase_1_stub": True,
        "title": args.title,
        "model": args.model,
        "work_type": args.work_type,
        "note": "Phase 2 will emit real CharacterMap JSON here.",
    }
    output = json.dumps(stub, indent=2)

    if args.save:
        args.save.write_text(output)
        print(f"Saved to {args.save}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
