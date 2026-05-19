#!/usr/bin/env python3
"""Re-run Stage 2 (structuring only) across all golden-set works, using
the Stage 1 analyses already on disk from run-2026-05-19-full/. Writes
new JSON files to run-2026-05-19-full2/ for clean comparison."""
import asyncio
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
GOLDEN_SET = ROOT / "tuning" / "golden_set.yaml"
ANALYSIS_DIR = ROOT / "tuning" / "run-2026-05-19-full"
OUT_DIR = ROOT / "tuning" / "run-2026-05-19-full2"
CONCURRENCY = 5


def slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")


async def _run(cmd: list[str], stderr_path: Path) -> int:
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stderr_path, "w") as f:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=f, cwd=str(ROOT),
        )
        await proc.wait()
    return proc.returncode


async def process_work(work: dict, sem: asyncio.Semaphore) -> tuple[str, str]:
    async with sem:
        s = slug(work["title"])
        analysis_file = ANALYSIS_DIR / f"{s}_analysis.md"
        json_file = OUT_DIR / f"{s}.json"
        json_stderr = OUT_DIR / f"{s}.stderr"
        # Reuse analysis md file by symlinking/copying for traceability
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        analysis_link = OUT_DIR / f"{s}_analysis.md"
        if not analysis_link.exists():
            shutil.copy(analysis_file, analysis_link)
        cmd = [
            "python3", "scripts/dev-structure.py",
            "--analysis-file", str(analysis_link),
            "--title", work["title"],
            "--year", str(work["year"]),
            "--work-type", work["type"],
            "--char-cap", "20",
            "--save", str(json_file),
        ]
        if work.get("author"):
            cmd += ["--author", work["author"]]
        rc = await _run(cmd, json_stderr)
        status = "ok" if rc == 0 else "stage2_failed"
        print(f"[done] {work['title']}: {status}", flush=True)
        return work["title"], status


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    works = yaml.safe_load(GOLDEN_SET.read_text())
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(process_work(w, sem) for w in works))
    print()
    print("Summary:")
    for title, status in results:
        print(f"  {status:20s} {title}")


if __name__ == "__main__":
    asyncio.run(main())
