#!/usr/bin/env python3
"""Static reviewer-driven feature checks for v1.3.2."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "software/index.html").read_text(encoding="utf-8")

required_ids = [
    "nistMinIonCount", "matchGapThreshold", "showAmbiguousOnly",
    "groupDuplicateCAS", "riReferenceFile", "idcRIanchorMF", "manualRItext",
]
missing = [item for item in required_ids if f'id="{item}"' not in text]
if missing:
    raise SystemExit(f"Missing reviewer-driven controls: {missing}")

required_functions = [
    "componentSearchEligibility", "candidateAmbiguityMetrics",
    "candidateDisplayEntries", "selectCandidate", "loadRIReference",
    "setManualRIAnchors", "applyRIAnchoring", "finalOriginClassification",
    "buildCandidateAuditCSVText",
]
missing_functions = [name for name in required_functions if f"function {name}" not in text]
if missing_functions:
    raise SystemExit(f"Missing reviewer-driven functions: {missing_functions}")

for phrase in [
    "not a universal taxonomy",
    "neutral nine-class structural-product summary",
    "immutable snapshot",
    "conventional nominal-mass, MS1 full-scan GC-MS",
    "ClassificationModelVersion 2.1.0",
    "Sulfur-containing / sulfurization-associated",
]:
    if phrase not in text:
        raise SystemExit(f"Missing clarification in interface: {phrase}")

print("PASS: v1.3.2 reviewer-driven controls, sulfur class, and clarifications are present")
