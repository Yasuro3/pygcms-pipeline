#!/usr/bin/env python3
"""Regression checks for classification model 2.1.0 in software v1.3.2."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "software" / "index.html"
text = HTML.read_text(encoding="utf-8")

required = [
    "CLASSIFICATION_MODEL_VERSION='2.1.0'",
    "EXACT_TOLUENE",
    "L_AROMATIC_HYDROCARBON",
    "FORMULA_AROMATIC_HC_L",
    "function buildCandidateAuditCSVText()",
    "FinalOriginRuleID",
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(f"Missing classification-model implementation markers: {missing}")

try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("SKIP: Playwright unavailable; static classification-model checks passed")
    raise SystemExit(77)

from browser_utils import launch_chromium

with sync_playwright() as pw:
    browser = launch_chromium(pw)
    page = browser.new_page()
    page.set_content(text, wait_until="load")
    result = page.evaluate(
        """
        () => {
          const cases=[
            {name:'Toluene',formula:'C7H8',cas:'108-88-3'},
            {name:'toluene',formula:'C7H8',cas:''},
            {name:'Methylbenzene',formula:'C7H8',cas:''},
            {name:'Benzene, methyl-',formula:'C7H8',cas:''},
            {name:'Unusual library name',formula:'C7H8',cas:'108883'},
            {name:'Benzene',formula:'C6H6',cas:'71-43-2'},
            {name:'Naphthalene',formula:'C10H8',cas:'91-20-3'},
            {name:'Pyridine',formula:'C5H5N',cas:'110-86-1'},
            {name:'Thiophene',formula:'C4H4S',cas:'110-02-1'},
            {name:'2-Methylthiophene',formula:'C5H6S',cas:'554-14-3'},
            {name:'Benzothiophene',formula:'C8H6S',cas:'95-15-8'},
            {name:'Benzothiazole',formula:'C7H5NS',cas:'95-16-9'},
            {name:'Unlisted sulfur compound',formula:'C6H6S',cas:''},
            {name:'Furfural',formula:'C5H4O2',cas:'98-01-1'},
            {name:'Hexadecane',formula:'C16H34',cas:'544-76-3'},
            {name:'Cyclomethicone siloxane',formula:'C6H18OSi2',cas:''}
          ].map(c=>applyCandidateContexts(Object.assign({cat:'P',catEvid:'test',paperClass:''},c),{overrideCat:true}));
          // Reapply and simulate a prior AI-origin assignment to verify locked idempotence.
          const t=applyCandidateContexts({name:'Toluene',formula:'C7H8',cas:'108-88-3',cat:'P',aiOriginInterpretation:'protein'}, {overrideCat:true});
          applyCandidateContexts(t,{overrideCat:true});
          G.ok=true; G.deconvParams=getDeconvParameterSnapshot(); document.getElementById('pSC').value=0;
          G.results=[{scan:1,rt:3.788,tic:1000,dc:{nRaw:10,mz:[91,92,65],i:[1000,300,200]},rawMZ:[91,92,65],rawI:[1000,300,200],cands:[t],nistcandidates15:[t],nistDone:true,nistExternalDone:true}];
          const audit=buildCandidateAuditCSVText();
          const results=buildResultsCSVText();
          return {cases:cases.map(c=>({name:c.name,cat:c.cat,rule:c.finalOriginRuleID,locked:c.finalOriginLocked,model:c.classificationModelVersion,paper:c.finalPaperClass9,warning:c.finalOriginWarning})),t:{cat:t.cat,rule:t.finalOriginRuleID,locked:t.finalOriginLocked},audit,results};
        }
        """
    )
    browser.close()

cases = result["cases"]
for c in cases[:5]:
    assert c["cat"] == "L", c
    assert c["rule"] == "EXACT_TOLUENE", c
    assert c["locked"] is True, c
    assert c["model"] == "2.1.0", c
    assert c["paper"] == "Aromatic hydrocarbons", c
assert cases[5]["cat"] == "L" and cases[5]["rule"] == "L_AROMATIC_HYDROCARBON", cases[5]
assert cases[6]["cat"] == "L" and cases[6]["rule"] == "L_AROMATIC_HYDROCARBON", cases[6]
assert cases[7]["cat"] == "P", cases[7]
for c in cases[8:13]:
    assert c["cat"] == "S", c
    assert c["rule"] in {"S_ORGANOSULFUR_NAME", "FORMULA_S_S"}, c
assert cases[13]["cat"] == "C", cases[13]
assert cases[14]["cat"] == "F", cases[14]
assert cases[15]["cat"] == "O" and cases[15]["locked"] is True, cases[15]
assert result["t"] == {"cat": "L", "rule": "EXACT_TOLUENE", "locked": True}, result["t"]
assert "EXACT_TOLUENE" in result["audit"]
assert "2.1.0" in result["audit"]
assert "ClassificationModelVersion" in result["results"]
assert "FinalOriginRuleID" in result["results"]

print(json.dumps({"status":"PASS","cases":cases}, indent=2))
