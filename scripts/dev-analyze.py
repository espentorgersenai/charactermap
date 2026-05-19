#!/usr/bin/env python3
"""dev-analyze.py — Stage 1 smoke test: run the analysis prompt with the
Anthropic web_search tool enabled.

The hypothesis: prompt iteration cannot reach 100% character recovery
because the model lacks knowledge of mid-tier works. Web-search-tool
grounding solves this by retrieving named sources at inference time.

Pass criterion for Congo: output's Cast section names BOTH Jan Kruger
AND Misulu (the two real characters every memory-only run has missed).
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from anthropic import AsyncAnthropic

from app.config import settings


async def _run(args) -> str:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt_path = (
        Path(__file__).parent.parent / "backend" / "prompts" / "character_map_analysis.md"
    )
    system_prompt = prompt_path.read_text()

    user_message = (
        f"<work_metadata>\n"
        f"title: {args.title}\n"
        f"year: {args.year or 'Unknown'}\n"
        f"author_or_director: {args.author or 'Unknown'}\n"
        f"type: {args.work_type}\n"
        f"</work_metadata>\n\n"
        f"Produce the analysis as specified."
    )

    response = await client.messages.create(
        model=args.model,
        max_tokens=8192,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": args.max_searches,
            }
        ],
    )

    # Anthropic returns a list of content blocks. Server-side tools produce
    # `server_tool_use` and `web_search_tool_result` blocks interleaved with
    # the model's text. Concatenate just the text blocks for the analysis;
    # report tool calls separately on stderr.
    text_parts: list[str] = []
    search_count = 0
    for block in response.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
        elif btype == "server_tool_use":
            search_count += 1
            query = getattr(block, "input", {}).get("query", "?")
            print(f"[dev-analyze] search #{search_count}: {query}", file=sys.stderr)

    stop_reason = response.stop_reason
    usage = response.usage
    print(
        f"[dev-analyze] {args.model} | stop={stop_reason} | "
        f"in={usage.input_tokens} out={usage.output_tokens} | searches={search_count}",
        file=sys.stderr,
    )

    return "\n".join(text_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Run Stage 1 analysis with the Anthropic web_search tool enabled.",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--year", type=int)
    parser.add_argument("--author")
    parser.add_argument("--work-type", choices=["book", "film_tv"], default="book")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument(
        "--max-searches",
        type=int,
        default=8,
        help="Maximum web_search tool invocations per call (default 8).",
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
