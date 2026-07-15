#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parents[1]

def run(args):
    print("+", " ".join(map(str,args)), flush=True)
    subprocess.run(args, check=True)

for test in sorted((ROOT / "tests").glob("test_*.py")):
    run([sys.executable, str(test)])
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)
    run([sys.executable, str(ROOT / "scripts/reproduce_lake_biwa_statistics.py"), "--class-summary-csv", str(ROOT / "data/application/17B_class_summary_percent.csv"), "--outdir", str(out / "derived")])
    run([sys.executable, str(ROOT / "scripts/generate_figures.py"), "--outdir", str(out / "figures"), "--class-summary", str(ROOT / "data/application/17B_class_summary_percent.csv")])
    run([sys.executable, str(ROOT / "scripts/validate_mzml_structure.py"), str(ROOT / "data/validation/full_length/17B_L1_PY_full_length_validation.mzML"), "--output", str(out / "full_length_structure.json")])
print("PASS: public reproducibility checks completed.")
