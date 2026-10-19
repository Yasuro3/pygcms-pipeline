#!/usr/bin/env python3
"""Validate a Shimadzu GCMSsolution QGD with the released browser parser."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - CLI guidance
    raise SystemExit("Playwright is required: python -m pip install -r requirements-browser.txt") from exc

ROOT = Path(__file__).resolve().parents[1]


def launch_chromium(pw):
    kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    executable = os.environ.get("PYGCMS_CHROMIUM", "").strip() or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if executable:
        kwargs["executable_path"] = executable
    return pw.chromium.launch(**kwargs)


def patch_session_storage(html: str) -> str:
    shim = (
        "<script>window.__sessionStore={};window.__session={"
        "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
        "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
        "removeItem:k=>{delete __sessionStore[k]}};</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qgd", required=True, type=Path, help="Shimadzu GCMSsolution .qgd file")
    ap.add_argument("--html", type=Path, default=ROOT / "software" / "index.html", help="PyGCMS Pipeline index.html")
    ap.add_argument("--output", type=Path, help="optional JSON report path")
    ap.add_argument("--run-deconvolution", action="store_true", help="also run the current default deconvolution (can take longer)")
    args = ap.parse_args()
    if not args.qgd.is_file():
        raise SystemExit(f"QGD not found: {args.qgd}")
    if args.qgd.suffix.lower() != ".qgd":
        raise SystemExit("--qgd must point to a .qgd file")

    html = patch_session_storage(args.html.read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page()
        page.set_default_timeout(900000)
        page_errors: list[str] = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.set_content(html, wait_until="load")
        page.evaluate("()=>{const x=document.createElement('input');x.type='file';x.id='qgdCliValidationFile';document.body.appendChild(x)}")
        page.set_input_files("#qgdCliValidationFile", str(args.qgd.resolve()))
        report = page.evaluate(
            """async()=>{const f=document.getElementById('qgdCliValidationFile').files[0];
            const d=await readRawFile(f);applyRawData(d);buildEIC();
            return {file:f.name,fileSize:f.size,format:d.format,selectedScans:d.n,
              rtMin:d.rt[0],rtMax:d.rt[d.n-1],nominalMZBins:G.nMZ,inputInfo:d.inputInfo};}"""
        )
        if args.run_deconvolution:
            page.evaluate("window.__qgdCliStart=document.getElementById('log').textContent.length;runPipeline();")
            page.wait_for_function(
                "document.getElementById('log').textContent.slice(window.__qgdCliStart).includes('Deconvolution complete:') && !document.getElementById('btnRun').disabled",
                timeout=900000,
            )
            report["deconvolution"] = page.evaluate(
                "()=>({components:G.results.length,nistEligible:G.results.filter(r=>componentSearchEligibility(r).eligible).length})"
            )
        browser.close()
    report["browserPageErrors"] = page_errors
    report["status"] = "PASS" if not page_errors and report.get("inputInfo", {}).get("ticMismatches", 0) == 0 else "CHECK"
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
