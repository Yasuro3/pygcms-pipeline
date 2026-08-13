#!/usr/bin/env python3
"""Generate an archive-relative SHA-256 manifest.

Generated/cache files that change simply by running Python are deliberately
excluded so verification remains stable after public checks are executed.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

EXCLUDED_DIRS = {"__pycache__", ".git", ".pytest_cache", ".venv", "venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_FILES = {"CHECKSUMS.sha256", "nistms_path.txt", "bridge_startup_log.txt"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def eligible(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if path.name in EXCLUDED_FILES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    return path.is_file()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "CHECKSUMS.sha256").resolve()
    paths = sorted(p for p in root.rglob("*") if eligible(p, root))
    lines = [f"{digest(path)}  {path.relative_to(root).as_posix()}" for path in paths if path.resolve() != output]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE: {output} ({len(lines)} files; caches excluded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
