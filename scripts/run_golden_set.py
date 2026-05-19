#!/usr/bin/env python3
"""run_golden_set.py — Batch golden-set runner for prompt regression testing.

Runs dev-generate.py against every work in tuning/golden_set.yaml and
saves timestamped outputs. Prints a summary table.

Usage:
  python scripts/run_golden_set.py --model claude-sonnet-4-6
  python scripts/run_golden_set.py --model claude-sonnet-4-6 --save-dir tuning/baseline
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

import yaml

from app.config import settings
from app.worker.pipeline import (
    call_and_validate,
    RefusalError,
    _load_prompt_template,
    _render_system_prompt,
    REFUSAL_MESSAGES,
)
from app.llm.anthropic_client import AnthropicClient


async def _generate_one(work: dict, model: str, system_prompt: str) -> dict:
    author_or_director = work.get("author") or work.get("director") or "Unknown"
    user_message = (
        f"<work_metadata>\n"
        f"title: {work['title']}\n"
        f"year: {work.get('year', 'Unknown')}\n"
        f"author_or_director: {author_or_director}\n"
        f"type: {work.get('type', 'book')}\n"
        f"</work_metadata>\n\n"
        f"<user_query>\n"
        f"{work['title']}\n"
        f"</user_query>\n\n"
        f"Output a single JSON object matching the CharacterMap schema. No prose, no markdown fences."
    )

    if model.startswith("claude-"):
        client = AnthropicClient(model=model, api_key=settings.anthropic_api_key)
    else:
        raise NotImplementedError(f"Model {model!r} not yet wired")

    try:
        char_map, llm_result = await call_and_validate(client, system_prompt, user_message)
    except RefusalError as e:
        return {"status": "refused", "refusal_code": e.refusal_code, "work": work}
    except Exception as e:
        return {"status": "error", "error": str(e), "work": work}

    # Compute spoiler_level coverage
    all_entities = list(char_map.characters) + list(char_map.relationships)
    tagged = sum(1 for e in all_entities if e.spoiler_level is not None)
    coverage = (tagged / len(all_entities) * 100) if all_entities else 0

    return {
        "status": "ok",
        "work": work,
        "char_map": char_map.model_dump(),
        "chars": len(char_map.characters),
        "factions": len(char_map.factions),
        "rels": len(char_map.relationships),
        "spoiler_level_coverage_pct": round(coverage, 1),
        "cost_usd": llm_result.cost_usd,
        "input_tokens": llm_result.input_tokens,
        "output_tokens": llm_result.output_tokens,
        "model": model,
    }


async def _run_all(works: list[dict], model: str, save_dir: Path, char_cap: int) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)
    system_prompt = _render_system_prompt(_load_prompt_template(), char_cap)

    print(f"\nRunning golden set ({len(works)} works) with {model}\n")
    header = f"{'Title':<35} {'Chars':>5} {'Fcts':>4} {'spoiler%':>8} {'Cost':>7}  Notes"
    print(header)
    print("-" * len(header))

    total_cost = 0.0
    results = []

    for work in works:
        title = work["title"]
        print(f"  {title:<33}…", end="", flush=True)
        result = await _generate_one(work, model, system_prompt)
        results.append(result)

        if result["status"] == "ok":
            notes = []
            if result["chars"] >= 25:
                notes.append("cap hit")
            if result["spoiler_level_coverage_pct"] < 100:
                notes.append(f"⚠ {round(100 - result['spoiler_level_coverage_pct'])}% untagged")
            note_str = ", ".join(notes) if notes else "OK"
            print(
                f"\r  {title:<33} {result['chars']:>5} {result['factions']:>4} "
                f"{result['spoiler_level_coverage_pct']:>7.0f}% "
                f"${result['cost_usd']:.4f}  {note_str}"
            )
            total_cost += result["cost_usd"]

            # Save individual output
            safe_title = title.replace(" ", "_").replace("/", "-")[:30]
            out_file = save_dir / f"{safe_title}.json"
            out_file.write_text(json.dumps(result["char_map"], indent=2, ensure_ascii=False))
        else:
            code = result.get("refusal_code") or result.get("error", "unknown")
            print(f"\r  {title:<33} {'—':>5} {'—':>4} {'—':>8} {'—':>7}  {result['status']}: {code}")

    print(f"\nTotal cost: ${total_cost:.4f}")

    # Save full results
    summary_file = save_dir / "summary.json"
    summary_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Results saved to {save_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Run the golden test set against a model.")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        choices=["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001", "gpt-5.5", "gemini-2.5-pro"],
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="Directory to save outputs (default: tuning/run-<timestamp>)",
    )
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path(__file__).parent.parent / "tuning" / "golden_set.yaml",
    )
    parser.add_argument(
        "--char-cap",
        type=int,
        default=20,
        help="Substituted for {CHAR_CAP} in the prompt (default 20, matches runtime default).",
    )
    args = parser.parse_args()

    works = yaml.safe_load(args.golden_set.read_text())
    save_dir = args.save_dir or Path("tuning") / f"run-{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    asyncio.run(_run_all(works, args.model, save_dir, args.char_cap))


if __name__ == "__main__":
    main()
