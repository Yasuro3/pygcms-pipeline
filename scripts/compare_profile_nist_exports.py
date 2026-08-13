#!/usr/bin/env python3
"""Compare licensed-NIST results exported under deconvolution profiles.

This utility is intentionally separate from the public validation run because
NIST MS Search and its libraries are separately licensed.  It matches rows by
scan number (falling back to rounded RT), then reports agreement in selected
candidate, original NIST rank, and optional broad classification columns.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        scan = (row.get("Scan") or "").strip()
        key = f"scan:{scan}" if scan else f"rt:{float(row.get('RT_min') or 0):.3f}"
        out[key] = row
    return out


def norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def compare(left: dict[str, dict[str, str]], right: dict[str, dict[str, str]]) -> dict[str, Any]:
    shared = sorted(set(left) & set(right))
    top_equal = rank_equal = class5_equal = class9_equal = 0
    for key in shared:
        a, b = left[key], right[key]
        top_equal += norm(a.get("Compound")) == norm(b.get("Compound"))
        rank_equal += norm(a.get("NIST_Rank")) == norm(b.get("NIST_Rank"))
        class5_equal += norm(a.get("Category")) == norm(b.get("Category"))
        class9_equal += norm(a.get("PaperClass9")) == norm(b.get("PaperClass9"))
    n = len(shared)
    return {
        "shared_components": n,
        "left_only": len(left) - n,
        "right_only": len(right) - n,
        "selected_candidate_agreement": top_equal / n if n else None,
        "selected_original_rank_agreement": rank_equal / n if n else None,
        "nom5_class_agreement": class5_equal / n if n else None,
        "struct9_class_agreement": class9_equal / n if n else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--default", type=Path, required=True)
    ap.add_argument("--permissive", type=Path, required=True)
    ap.add_argument("--selective", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    data = {name: read_rows(getattr(args, name)) for name in ("default", "permissive", "selective")}
    report = {
        "default_vs_permissive": compare(data["default"], data["permissive"]),
        "default_vs_selective": compare(data["default"], data["selective"]),
        "permissive_vs_selective": compare(data["permissive"], data["selective"]),
        "note": "Agreement is conditional on the locally licensed NIST release and search configuration recorded with the exports.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
