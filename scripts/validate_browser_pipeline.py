#!/usr/bin/env python3
"""Run the public browser pipeline on a full-length mzML and verify active controls.

This optional validation uses Playwright. It never reads a vendor-native file.
The default result can be compared with the archived component reference JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

PROFILES = {
    "permissive": {"pRT": 2, "pTH": 5000, "pCT": 0.5, "pHW": 4, "pCorr": 0.70, "pBleed": False},
    "default": {"pRT": 2, "pTH": 5000, "pCT": 1.0, "pHW": 6, "pCorr": 0.85, "pBleed": True},
    "selective": {"pRT": 2, "pTH": 5000, "pCT": 2.0, "pHW": 6, "pCorr": 0.95, "pBleed": True},
}


def patch_session_storage(html: str) -> str:
    shim = (
        "<script>window.__sessionStore={};window.__session={"
        "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
        "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
        "removeItem:k=>{delete __sessionStore[k]}};</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def run_profile(browser: Any, html: str, mzml: Path, profile: str, extract_components: bool) -> dict[str, Any]:
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.set_default_timeout(600000)
    page.set_content(patch_session_storage(html), wait_until="load", timeout=120000)
    page.evaluate("()=>{const x=document.createElement('input');x.type='file';x.id='validationFile';document.body.appendChild(x)}")
    page.set_input_files("#validationFile", str(mzml))

    start = time.time()
    loaded = page.evaluate(
        """async()=>{const f=document.getElementById('validationFile').files[0];
        const d=await readRawFile(f);G.rt=d.rt;G.tic=d.tic;G.n=d.n;G.si=null;G.ms=null;
        G.preloadedScanMaps=d.scanMaps;G.ok=true;G.results=[];G.scanMaps=null;buildEIC();
        return {n:G.n,nMZ:G.nMZ,rt0:G.rt[0],rt1:G.rt[G.n-1],tic0:G.tic[0],tic1:G.tic[G.n-1]}}"""
    )
    load_seconds = time.time() - start
    page.evaluate(
        """cfg=>{for(const [id,v] of Object.entries(cfg)){const e=document.getElementById(id);
        if(!e)continue;if(e.type==='checkbox')e.checked=!!v;else{e.value=String(v);e.dispatchEvent(new Event('input'));}}
        window.__validationLogStart=document.getElementById('log').textContent.length;
        window.__validationStart=performance.now();runPipeline()}""",
        PROFILES[profile],
    )
    page.wait_for_function(
        "document.getElementById('log').textContent.slice(window.__validationLogStart).includes('Deconvolution complete:') && !document.getElementById('btnRun').disabled",
        timeout=600000,
    )
    common = """elapsed_seconds:(performance.now()-window.__validationStart)/1000,nf:G.Nf,
      component_count:G.results.length,total_deconvolved_ions:G.results.reduce((a,r)=>a+r.dc.mz.length,0),
      parameters:getDeconvParameterSnapshot()"""
    if extract_components:
        expression = """()=>({%s,components:G.results.map(r=>({scan:r.scan,rt:r.rt,tic:r.tic,
        mz:Array.from(r.dc.mz),i:Array.from(r.dc.i).map(x=>Math.round(x*1e6)/1e6),
        nBefore:r.dc.nBefore,nModelIons:r.dc.nModelIons}))})""" % common
    else:
        expression = "()=>({%s})" % common
    result = page.evaluate(expression)
    page.close()
    return {"load_seconds": load_seconds, "loaded": loaded, "run": result, "page_errors": errors, "profile": PROFILES[profile]}


def compare_components(reference: list[dict[str, Any]], current: list[dict[str, Any]], tolerance: float) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "PASS", "reference_count": len(reference), "current_count": len(current),
        "mismatch_count": 0, "max_rt_difference_min": 0.0, "max_tic_difference": 0.0,
        "max_intensity_difference": 0.0, "examples": [],
    }
    if len(reference) != len(current):
        report["status"] = "FAIL"
    for index, (left, right) in enumerate(zip(reference, current)):
        rt_diff = abs(left["rt"] - right["rt"])
        tic_diff = abs(left["tic"] - right["tic"])
        if len(left["i"]) == len(right["i"]):
            intensity_diff = max((abs(a - b) for a, b in zip(left["i"], right["i"])), default=0.0)
        else:
            intensity_diff = float("inf")
        report["max_rt_difference_min"] = max(report["max_rt_difference_min"], rt_diff)
        report["max_tic_difference"] = max(report["max_tic_difference"], tic_diff)
        report["max_intensity_difference"] = max(report["max_intensity_difference"], intensity_diff)
        ok = (
            left["scan"] == right["scan"] and rt_diff < 1e-10 and tic_diff == 0 and
            left["mz"] == right["mz"] and intensity_diff <= tolerance and
            left["nBefore"] == right["nBefore"] and left["nModelIons"] == right["nModelIons"]
        )
        if not ok:
            report["status"] = "FAIL"
            report["mismatch_count"] += 1
            if len(report["examples"]) < 10:
                report["examples"].append({
                    "position": index, "scan": [left["scan"], right["scan"]],
                    "rt_difference_min": rt_diff, "tic_difference": tic_diff,
                    "mz_equal": left["mz"] == right["mz"], "intensity_difference": intensity_diff,
                })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--mzml", type=Path, required=True)
    parser.add_argument("--reference-json", type=Path)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--chromium", help="optional Chromium executable; Playwright bundled Chromium is used by default")
    parser.add_argument("--intensity-tolerance", type=float, default=0.01)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    html = args.html.read_text(encoding="utf-8")

    with sync_playwright() as playwright:
        launch = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=8192"],
        }
        if args.chromium:
            launch["executable_path"] = args.chromium
        browser = playwright.chromium.launch(**launch)
        browser_version = browser.version
        runs = {
            name: run_profile(browser, html, args.mzml, name, name == "default")
            for name in ("default", "permissive", "selective")
        }
        browser.close()

    comparison = None
    if args.reference_json:
        archived = json.loads(args.reference_json.read_text(encoding="utf-8"))
        reference = archived["runs"]["default"]["run"]["components"]
        comparison = compare_components(reference, runs["default"]["run"]["components"], args.intensity_tolerance)
    status = "PASS" if all(not run["page_errors"] for run in runs.values()) and (comparison is None or comparison["status"] == "PASS") else "FAIL"
    environment = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "playwright_browser": "Chromium",
        "browser_version": browser_version,
        "logical_cpu_count": os.cpu_count(),
        "chromium_executable": args.chromium or "Playwright bundled Chromium",
    }
    output = {"status": status, "environment": environment, "comparison": comparison, "runs": runs}
    (args.outdir / "browser_pipeline_validation.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    counts = {name: run["run"]["component_count"] for name, run in runs.items()}
    report = [
        "# Browser-pipeline validation", "", f"**Status:** {status}", "",
        f"- Spectra: {runs['default']['loaded']['n']:,}",
        f"- Retention-time range: {runs['default']['loaded']['rt0']:.4f}-{runs['default']['loaded']['rt1']:.4f} min",
        f"- Default components: {counts['default']:,}",
        f"- Permissive components: {counts['permissive']:,}",
        f"- Selective components: {counts['selective']:,}",
        "", "## Single-run diagnostic timings", "",
        "| Profile | mzML load (s) | Deconvolution (s) |",
        "|---|---:|---:|",
        *[f"| {name.capitalize()} | {runs[name]['load_seconds']:.3f} | {runs[name]['run']['elapsed_seconds']:.3f} |" for name in ("default", "permissive", "selective")],
        "",
        "These are single-run diagnostic timings for the recorded environment, not a cross-system benchmark.",
        "", "## Environment", "",
        f"- Recorded UTC: {environment['recorded_utc']}",
        f"- Platform: {environment['platform']}",
        f"- Python: {environment['python']}",
        f"- Browser: Chromium {environment['browser_version']}",
        f"- Logical CPUs: {environment['logical_cpu_count']}",
    ]
    if comparison:
        report += [
            f"- Archived-reference mismatches: {comparison['mismatch_count']}",
            f"- Maximum intensity difference: {comparison['max_intensity_difference']}",
        ]
    (args.outdir / "BROWSER_PIPELINE_VALIDATION.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    raise SystemExit(0 if status == "PASS" else 2)


if __name__ == "__main__":
    main()
