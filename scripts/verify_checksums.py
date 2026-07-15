#!/usr/bin/env python3
"""Verify the archive-relative SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, nargs="?", default=Path("CHECKSUMS.sha256"))
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    root = manifest.parent
    failures: list[str] = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            expected, rel = line.split("  ", 1)
        except ValueError:
            failures.append(f"malformed line: {line}")
            continue
        path = root / rel
        if not path.is_file():
            failures.append(f"missing: {rel}")
            continue
        actual = digest(path)
        checked += 1
        if actual != expected:
            failures.append(f"mismatch: {rel}")
    if failures:
        print("FAIL: checksum verification")
        for item in failures:
            print(" -", item)
        return 2
    print(f"PASS: SHA-256 manifest verified for {checked} archived files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
