#!/usr/bin/env python3
"""Extract the embedded literature classification database to auditable files."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path

OUTPUT_JSON = "literature_classification_rules.json"
OUTPUT_RULES = "literature_classification_rules.csv"
OUTPUT_SOURCES = "literature_sources.csv"


def load_database(html_path: Path) -> dict:
    text = html_path.read_text(encoding="utf-8")
    match = re.search(r"let\s+LITDB\s*=\s*(\{.*?\});\s*\n", text, re.S)
    if not match:
        raise RuntimeError("embedded LITDB object was not found")
    data = json.loads(match.group(1))
    if len(data.get("records", [])) != data.get("records_count"):
        raise RuntimeError("LITDB records_count does not match the embedded records")
    if len(data.get("sources", [])) != data.get("sources_count"):
        raise RuntimeError("LITDB sources_count does not match the embedded sources")
    return data


def csv_text(rows: list[dict]) -> str:
    if not rows:
        return ""
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def rendered(data: dict) -> dict[str, str]:
    return {
        OUTPUT_JSON: json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        OUTPUT_RULES: csv_text(data.get("records", [])),
        OUTPUT_SOURCES: csv_text(data.get("sources", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify existing files without rewriting")
    args = parser.parse_args()

    outputs = rendered(load_database(args.html))
    args.outdir.mkdir(parents=True, exist_ok=True)
    if args.check:
        mismatches = []
        for name, expected in outputs.items():
            path = args.outdir / name
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                mismatches.append(name)
        if mismatches:
            print("FAIL: literature-rule exports differ from the embedded LITDB: " + ", ".join(mismatches))
            return 2
        print("PASS: machine-readable literature rules match the embedded LITDB")
        return 0

    for name, content in outputs.items():
        (args.outdir / name).write_text(content, encoding="utf-8")
    data = load_database(args.html)
    print(f"Wrote {data['records_count']} rules and {data['sources_count']} sources to {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
