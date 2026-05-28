#!/usr/bin/env python3
"""dev-structure.py — Stage 2: convert a Stage 1 analysis into a CharacterMap JSON.

Takes a Stage 1 analysis (produced by `dev-analyze.py`) and runs the
structuring prompt on it to emit a validated CharacterMap.

Usage:
  python scripts/dev-structure.py \\
      --analysis-file tuning/run-2026-05-19-stage1/Congo_analysis.md \\
      --title "Congo" --author "Michael Crichton" --year 1980 \\
      --work-type book --char-cap 20 \\
      --save tuning/run-2026-05-19-stage2/Congo.json
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from app.config import settings
from app.worker.pipeline import call_and_validate, RefusalError, REFUSAL_MESSAGES
from app.llm.anthropic_client import AnthropicClient
from app.llm.openai_client import OpenAIClient
from app.llm.gemini_client import GeminiClient


def _load_structuring_prompt(char_cap: int) -> str:
    path = Path(__file__).parent.parent / "backend" / "prompts" / "character_map_structuring.md"
    template = path.read_text()
    return template.replace("{CHAR_CAP}", str(char_cap))


async def _run(args) -> str:
    system_prompt = _load_structuring_prompt(args.char_cap)
    analysis = Path(args.analysis_file).read_text()

    creator = args.author or args.director or "Unknown"
    user_message = (
        f"<work_metadata>\n"
        f"title: {args.title}\n"
        f"year: {args.year or 'Unknown'}\n"
        f"author_or_director: {creator}\n"
        f"type: {args.work_type}\n"
        f"</work_metadata>\n\n"
        f"<analysis>\n{analysis}\n</analysis>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. "
        f"No prose, no markdown fences."
    )

    if args.model.startswith("claude-"):
        client = AnthropicClient(model=args.model, api_key=settings.anthropic_api_key)
    elif args.model.startswith("gpt-"):
        client = OpenAIClient(model=args.model, api_key=settings.openai_api_key)
    elif args.model.startswith("gemini-"):
        client = GeminiClient(
            model=args.model,
            api_key=settings.google_api_key,
            project=settings.google_cloud_project or None,
            location=settings.google_cloud_location,
        )
    else:
        print(f"[dev-structure] Model {args.model!r} not wired", file=sys.stderr)
        sys.exit(1)

    try:
        char_map, llm_result = await call_and_validate(client, system_prompt, user_message)
    except RefusalError as e:
        msg = REFUSAL_MESSAGES.get(e.refusal_code, REFUSAL_MESSAGES.get("unknown_work", ""))
        print(f"[dev-structure] Refused: {e.refusal_code} — {msg}", file=sys.stderr)
        return json.dumps({"refusal": e.refusal_code})

    print(
        f"[dev-structure] {args.model} | "
        f"in={llm_result.input_tokens} out={llm_result.output_tokens} "
        f"cost=${llm_result.cost_usd:.4f} | "
        f"chars={len(char_map.characters)} rels={len(char_map.relationships)}",
        file=sys.stderr,
    )
    return char_map.model_dump_json(indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Stage 1 analysis into a CharacterMap JSON.",
    )
    parser.add_argument("--analysis-file", required=True, type=Path,
                        help="Path to the Stage 1 analysis .md file.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--year", type=int)
    creator_group = parser.add_mutually_exclusive_group()
    creator_group.add_argument("--author")
    creator_group.add_argument("--director")
    parser.add_argument("--work-type", choices=["book", "film_tv"], default="book")
    parser.add_argument("--char-cap", type=int, default=20)
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        choices=[
            "claude-sonnet-4-6", "claude-opus-4-8", "claude-opus-4-7",
            "gpt-5.5", "gpt-5", "gpt-5-mini",
            "gemini-2.5-pro",
        ],
    )
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()

    output = asyncio.run(_run(args))
    if args.save:
        args.save.write_text(output)
        print(f"Saved to {args.save}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
