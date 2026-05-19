#!/usr/bin/env python3
"""Run the two-stage grounded pipeline (Stage 1 web_search + Stage 2 structure)
across the full golden set, with bounded parallelism.

For each work: spawns dev-analyze.py (Stage 1) → dev-structure.py (Stage 2),
saving both artifacts under tuning/run-2026-05-19-full/.
"""
import asyncio
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
GOLDEN_SET = ROOT / "tuning" / "golden_set.yaml"
OUT_DIR = ROOT / "tuning" / "run-2026-05-19-full"
CONCURRENCY = 3  # cap parallel Anthropic web_search calls


def slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")


async def _run(cmd: list[str], stderr_path: Path) -> int:
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stderr_path, "w") as f:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=f,
            cwd=str(ROOT),
        )
        await proc.wait()
    return proc.returncode


async def process_work(work: dict, sem: asyncio.Semaphore) -> tuple[str, str]:
    async with sem:
        s = slug(work["title"])
        analysis_file = OUT_DIR / f"{s}_analysis.md"
        analysis_stderr = OUT_DIR / f"{s}_analysis.stderr"
        json_file = OUT_DIR / f"{s}.json"
        json_stderr = OUT_DIR / f"{s}.stderr"

        cmd1 = [
            "python3", "scripts/dev-analyze.py",
            "--title", work["title"],
            "--year", str(work["year"]),
            "--work-type", work["type"],
            "--save", str(analysis_file),
        ]
        if work.get("author"):
            cmd1 += ["--author", work["author"]]
        print(f"[stage1 start] {work['title']}", flush=True)
        rc1 = await _run(cmd1, analysis_stderr)
        if rc1 != 0:
            print(f"[stage1 FAIL] {work['title']}", flush=True)
            return work["title"], "stage1_failed"

        cmd2 = [
            "python3", "scripts/dev-structure.py",
            "--analysis-file", str(analysis_file),
            "--title", work["title"],
            "--year", str(work["year"]),
            "--work-type", work["type"],
            "--char-cap", "20",
            "--save", str(json_file),
        ]
        if work.get("author"):
            cmd2 += ["--author", work["author"]]
        rc2 = await _run(cmd2, json_stderr)
        status = "ok" if rc2 == 0 else "stage2_failed"
        print(f"[done] {work['title']}: {status}", flush=True)
        return work["title"], status


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    works = yaml.safe_load(GOLDEN_SET.read_text())
    sem = asyncio.Semaphore(CONCURRENCY)
    print(f"Running {len(works)} works with concurrency={CONCURRENCY}")
    results = await asyncio.gather(*(process_work(w, sem) for w in works))
    print()
    print("Summary:")
    for title, status in results:
        print(f"  {status:20s} {title}")


if __name__ == "__main__":
    asyncio.run(main())
