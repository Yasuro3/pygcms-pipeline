#!/usr/bin/env python3
"""Run the public reproducibility checks with explicit browser-skip handling."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = 77


def run(args: list[str], skipped: list[str]) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    completed = subprocess.run(args, check=False)
    if completed.returncode == SKIP:
        skipped.append(Path(args[-1]).name if args else "unknown")
        return
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-browser", action="store_true",
        help="fail if a Playwright/Chromium browser test is skipped",
    )
    args = parser.parse_args()
    skipped: list[str] = []

    for test in sorted((ROOT / "tests").glob("test_*.py")):
        run([sys.executable, str(test)], skipped)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        run([
            sys.executable, str(ROOT / "scripts/reproduce_lake_biwa_statistics.py"),
            "--class-summary-csv", str(ROOT / "data/application/17B_class_summary_percent.csv"),
            "--outdir", str(out / "derived"),
        ], skipped)
        run([
            sys.executable, str(ROOT / "scripts/generate_figures.py"),
            "--outdir", str(out / "figures"),
            "--class-summary", str(ROOT / "data/application/17B_class_summary_percent.csv"),
            "--check-only",
        ], skipped)
        run([
            sys.executable, str(ROOT / "scripts/validate_mzml_structure.py"),
            str(ROOT / "data/validation/full_length/17B_L1_PY_full_length_validation.mzML"),
            "--output", str(out / "full_length_structure.json"),
        ], skipped)

    run([
        sys.executable, str(ROOT / "scripts/extract_literature_rules.py"),
        "--html", str(ROOT / "software/index.html"),
        "--outdir", str(ROOT / "provenance"), "--check",
    ], skipped)
    run([
        sys.executable, str(ROOT / "scripts/verify_checksums.py"),
        str(ROOT / "CHECKSUMS.sha256"),
    ], skipped)

    if skipped:
        names = ", ".join(skipped)
        if args.require_browser:
            print(f"FAIL: browser checks were required but skipped: {names}")
            return 2
        print(f"PASS WITH SKIPS: non-browser checks completed; skipped: {names}")
        print("Run with --require-browser after installing Playwright Chromium for a strict result.")
        return 0

    print("PASS: all public reproducibility checks completed; browser tests executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
