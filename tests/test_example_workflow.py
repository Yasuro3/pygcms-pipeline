#!/usr/bin/env python3
"""Verify that the public quick-start mzML produces components at defaults."""
from __future__ import annotations

import sys
from pathlib import Path

from browser_utils import launch_chromium

SKIP = 77
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed.")
    raise SystemExit(SKIP)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "software" / "index.html"
MZML = ROOT / "data" / "example" / "synthetic_gc_ms.mzML"


def patch_session_storage(html: str) -> str:
    shim = (
        "<script>window.__sessionStore={};window.__session={"
        "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
        "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
        "removeItem:k=>{delete __sessionStore[k]}};</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def main() -> int:
    html = patch_session_storage(INDEX.read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        try:
            browser = launch_chromium(pw)
        except Exception as exc:
            print(f"SKIP: chromium is unavailable ({exc.__class__.__name__}).")
            return SKIP
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.set_default_timeout(120000)
        page.set_content(html, wait_until="load")
        page.evaluate("()=>{const x=document.createElement('input');x.type='file';x.id='exampleValidationFile';document.body.appendChild(x)}")
        page.set_input_files("#exampleValidationFile", str(MZML))
        loaded = page.evaluate(
            """async()=>{const f=document.getElementById('exampleValidationFile').files[0];
            const d=await readRawFile(f);G.rt=d.rt;G.tic=d.tic;G.n=d.n;G.si=null;G.ms=null;
            G.preloadedScanMaps=d.scanMaps;G.ok=true;G.results=[];G.scanMaps=null;buildEIC();
            window.__testLogStart=document.getElementById('log').textContent.length;runPipeline();
            return {n:G.n,rt0:G.rt[0],rt1:G.rt[G.n-1]}}"""
        )
        page.wait_for_function(
            "document.getElementById('log').textContent.slice(window.__testLogStart).includes('Deconvolution complete:') && !document.getElementById('btnRun').disabled",
            timeout=120000,
        )
        result = page.evaluate(
            """()=>({count:G.results.length,ions:G.results.map(r=>r.dc.mz.length),
            eligible:G.results.filter(r=>componentSearchEligibility(r).eligible).length,
            mspCount:buildMSPBlocksForNIST().count})"""
        )
        browser.close()
    if errors:
        raise SystemExit(f"browser page errors: {errors}")
    if loaded["n"] != 121:
        raise SystemExit(f"expected 121 spectra, got {loaded['n']}")
    if result["count"] < 3:
        raise SystemExit(f"default example produced only {result['count']} components")
    if result["eligible"] < 3 or result["mspCount"] < 3:
        raise SystemExit(f"default example did not yield at least three NIST-eligible spectra: {result}")
    print(f"PASS: public example produced {result['count']} components and {result['eligible']} NIST-eligible spectra at defaults")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
