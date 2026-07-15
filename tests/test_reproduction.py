#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys, tempfile
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)
    subprocess.run([sys.executable, str(ROOT / "scripts/reproduce_lake_biwa_statistics.py"), "--class-summary-csv", str(ROOT / "data/application/17B_class_summary_percent.csv"), "--outdir", str(out)], check=True)
    result = json.loads((out / "reproduced_statistics.json").read_text(encoding="utf-8"))
    comp = pd.read_csv(out / "class_composition_classified_records_percent.csv")
summary = result["class_summary"]
if summary["selected_component_records"] != 4510 or summary["classified_records"] != 1896:
    raise SystemExit(f"Unexpected totals: {summary}")
if summary["excluded_or_unclassified_records"] != 2614:
    raise SystemExit(f"Unexpected excluded total: {summary}")
for group, rows in comp.groupby("Group", sort=False):
    total = rows["Normalized_percent_within_classified"].sum()
    if abs(total - 100.0) > 1e-8:
        raise SystemExit(f"Composition does not sum to 100% for {group}: {total}")
order = comp[["Fraction", "Layer"]].drop_duplicates().apply(lambda r: f"{r.Fraction}-{r.Layer}", axis=1).tolist()
expected = [f"TD-L{i}" for i in range(1,6)] + [f"PY-L{i}" for i in range(1,6)]
if order != expected:
    raise SystemExit(f"Unexpected display order: {order}")
print("PASS: totals reproduce and the classified composition is ordered TD L1-L5 then Py L1-L5.")
