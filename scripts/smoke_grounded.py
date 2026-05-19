#!/usr/bin/env python3
"""Smoke test: exercise the worker's `_run_grounded` end-to-end on a stub Job
to verify the pipeline integration works (and matches the manual dev-analyze
+ dev-structure split we proved out earlier)."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from app.config import settings
from app.llm.anthropic_client import AnthropicClient
from app.worker.pipeline import _run_grounded


async def main():
    stub_job = SimpleNamespace(
        id="smoke-test",
        resolved_title="Congo",
        resolved_year=1980,
        work_type="book",
        character_cap=20,
        resolved_meta={"author": "Michael Crichton"},
    )
    client = AnthropicClient("claude-sonnet-4-6", settings.anthropic_api_key)
    char_map, stage1, stage2 = await _run_grounded(client, stub_job)
    print(f"Stage 1: in={stage1.input_tokens} out={stage1.output_tokens} cost=${stage1.cost_usd:.4f}")
    print(f"Stage 2: in={stage2.input_tokens} out={stage2.output_tokens} cost=${stage2.cost_usd:.4f}")
    print(f"Total cost: ${stage1.cost_usd + stage2.cost_usd:.4f}")
    print()
    print(f"Characters ({len(char_map.characters)}):")
    for c in char_map.characters:
        print(f"  - {c.name:36s} [{c.importance:11s}] sp={c.spoiler_level} dead={c.is_deceased_in_work}")
    print()
    if char_map.adaptation_note:
        print(f"adaptation_note: {char_map.adaptation_note[:200]}...")
    print()
    names_low = {c.name.lower() for c in char_map.characters}
    has_kruger = any("kruger" in n for n in names_low)
    has_misulu = any("misulu" in n for n in names_low)
    print(f"Has Jan Kruger: {has_kruger}")
    print(f"Has Misulu:     {has_misulu}")


asyncio.run(main())
