#!/usr/bin/env python3
"""Static and browser regression checks for the v1.3.2 sulfur class."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'software/index.html').read_text(encoding='utf-8')
for token in ["['S','Sulfur-containing']", "S_ORGANOSULFUR_NAME", "FORMULA_S_S", "CLASSIFICATION_MODEL_VERSION='2.2.0'", "S:'Sulfur-containing / sulfurization-associated'", "S:'Sulfur-containing',O:'Other'"]:
    assert token in text, token
try:
    from playwright.sync_api import sync_playwright
except Exception:
    print('SKIP: Playwright unavailable; static sulfur checks passed')
    raise SystemExit(77)
from browser_utils import launch_chromium
with sync_playwright() as pw:
    browser=launch_chromium(pw); page=browser.new_page(); page.set_content(text,wait_until='load')
    out=page.evaluate("""() => [
      {name:'Thiophene',formula:'C4H4S'},
      {name:'2-Methylthiophene',formula:'C5H6S'},
      {name:'Benzothiophene',formula:'C8H6S'},
      {name:'Benzothiazole',formula:'C7H5NS'},
      {name:'Unlisted sulfur compound',formula:'C6H6S'},
      {name:'Pyridine',formula:'C5H5N'}
    ].map(x=>applyCandidateContexts(Object.assign({paperClass:''},x),{overrideCat:true})).map(x=>({cat:x.cat,rule:x.finalOriginRuleID,label:x.finalCategoryLabel,warning:x.finalOriginWarning}))""")
    browser.close()
for x in out[:5]: assert x['cat']=='S', x
assert out[3]['rule']=='S_ORGANOSULFUR_NAME' and 'N/S' in out[3]['warning'], out[3]
assert out[4]['rule']=='FORMULA_S_S', out[4]
assert out[5]['cat']=='P', out[5]
print('PASS: v1.3.2 sulfur class regression checks passed')
