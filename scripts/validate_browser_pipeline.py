#!/usr/bin/env python3
"""Run the public browser pipeline on a full-length mzML and verify active controls.

This optional validation uses Playwright. It never reads a vendor-native file.
The default result can be compared with the archived component reference JSON.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import statistics
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


def _ion_bins(components: list[dict[str, Any]], minimum_search_ions: int = 3) -> dict[str, int]:
    bins = {"1": 0, "2": 0, "3-4": 0, "5-9": 0, ">=10": 0, "search_eligible": 0}
    for comp in components:
        n = len(comp.get("mz", []))
        if n == 1:
            bins["1"] += 1
        elif n == 2:
            bins["2"] += 1
        elif n <= 4:
            bins["3-4"] += 1
        elif n <= 9:
            bins["5-9"] += 1
        else:
            bins[">=10"] += 1
        if n >= minimum_search_ions:
            bins["search_eligible"] += 1
    return bins


def _cosine(a: dict[str, Any], b: dict[str, Any]) -> float:
    ma = {int(m): float(i) for m, i in zip(a.get("mz", []), a.get("i", []))}
    mb = {int(m): float(i) for m, i in zip(b.get("mz", []), b.get("i", []))}
    keys = set(ma) | set(mb)
    dot = sum(ma.get(k, 0.0) * mb.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in ma.values()))
    nb = math.sqrt(sum(v * v for v in mb.values()))
    return dot / (na * nb) if na and nb else 0.0


def _profile_pair(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    lmap = {int(c["scan"]): c for c in left}
    rmap = {int(c["scan"]): c for c in right}
    scans = sorted(set(lmap) & set(rmap))
    cosines = [_cosine(lmap[scan], rmap[scan]) for scan in scans]
    return {
        "shared_apex_count": len(scans),
        "left_only": len(lmap) - len(scans),
        "right_only": len(rmap) - len(scans),
        "median_spectrum_cosine": statistics.median(cosines) if cosines else None,
        "p10_spectrum_cosine": sorted(cosines)[max(0, int(0.10 * (len(cosines) - 1)))] if cosines else None,
        "mean_spectrum_cosine": statistics.fmean(cosines) if cosines else None,
    }


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
            name: run_profile(browser, html, args.mzml, name, True)
            for name in ("default", "permissive", "selective")
        }
        browser.close()

    minimum_search_ions = 3
    ion_qc = {name: _ion_bins(run["run"]["components"], minimum_search_ions) for name, run in runs.items()}
    pair_qc = {
        "default_vs_permissive": _profile_pair(runs["default"]["run"]["components"], runs["permissive"]["run"]["components"]),
        "default_vs_selective": _profile_pair(runs["default"]["run"]["components"], runs["selective"]["run"]["components"]),
        "permissive_vs_selective": _profile_pair(runs["permissive"]["run"]["components"], runs["selective"]["run"]["components"]),
    }

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
    output = {"status": status, "environment": environment, "comparison": comparison, "minimum_search_ions": minimum_search_ions, "ion_count_qc": ion_qc, "profile_pairwise_qc": pair_qc, "runs": runs}
    (args.outdir / "browser_pipeline_validation.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (args.outdir / "profile_component_ion_counts.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["profile", "components", "one_ion", "two_ions", "three_to_four", "five_to_nine", "ten_or_more", "search_eligible_min3"])
        for name in ("default", "permissive", "selective"):
            q = ion_qc[name]
            w.writerow([name, runs[name]["run"]["component_count"], q["1"], q["2"], q["3-4"], q["5-9"], q[">=10"], q["search_eligible"]])
    with (args.outdir / "profile_pairwise_spectral_comparison.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["comparison", "shared_apex_count", "left_only", "right_only", "median_spectrum_cosine", "p10_spectrum_cosine", "mean_spectrum_cosine"])
        for name, q in pair_qc.items():
            w.writerow([name, q["shared_apex_count"], q["left_only"], q["right_only"], q["median_spectrum_cosine"], q["p10_spectrum_cosine"], q["mean_spectrum_cosine"]])

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
        "", "## Reconstructed-ion count QC", "",
        "Automatic NIST submission uses a non-destructive minimum of three reconstructed spectral ions in v1.3.1. Components below this threshold remain in the component export and can be included manually.",
        "", "| Profile | 1 ion | 2 ions | 3-4 | 5-9 | >=10 | Eligible (>=3) |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *[f"| {name.capitalize()} | {ion_qc[name]['1']} | {ion_qc[name]['2']} | {ion_qc[name]['3-4']} | {ion_qc[name]['5-9']} | {ion_qc[name]['>=10']} | {ion_qc[name]['search_eligible']} |" for name in ("default", "permissive", "selective")],
        "", "## Parameter-profile spectral comparison", "",
        "The profiles are matched by component-apex scan. Cosine statistics describe changes in reconstructed spectra; they are not library-identification accuracy measurements.",
        "", "| Comparison | Shared apices | Left only | Right only | Median cosine | 10th percentile |",
        "|---|---:|---:|---:|---:|---:|",
        *[f"| {name.replace('_',' ')} | {q['shared_apex_count']} | {q['left_only']} | {q['right_only']} | {q['median_spectrum_cosine']:.3f} | {q['p10_spectrum_cosine']:.3f} |" for name, q in pair_qc.items()],
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
