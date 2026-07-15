#!/usr/bin/env python3
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "software/index.html").read_text(encoding="utf-8")
required_ids = ["pRT", "pTH", "pDist", "pHW", "pCorr", "pCT", "pIonApex", "pTrace", "pSharp", "pModelFrac", "pModelMax", "pBleed"]
missing = [x for x in required_ids if f'id="{x}"' not in text]
if missing:
    raise SystemExit(f"Missing controls: {missing}")
for name in ["getDeconvParameterSnapshot", "exportDeconvParameters", "importDeconvParameters", "resetDeconvParameters"]:
    if not re.search(rf"function\s+{name}\s*\(", text):
        raise SystemExit(f"Missing function: {name}")
print("PASS: configurable deconvolution controls and preset functions are present.")
