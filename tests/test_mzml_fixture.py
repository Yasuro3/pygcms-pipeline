#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "validation.json"
    subprocess.run([sys.executable, str(ROOT / "scripts/validate_mzml_structure.py"), str(ROOT / "data/example/synthetic_gc_ms.mzML"), "--output", str(out)], check=True)
    result = json.loads(out.read_text(encoding="utf-8"))
if result.get("status") != "PASS" or result.get("spectra") != 3:
    raise SystemExit(f"Unexpected fixture validation: {result}")
print("PASS: synthetic mzML fixture is structurally valid.")
