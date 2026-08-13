#!/usr/bin/env python3
"""Verify non-destructive low-ion search gating and global result mapping."""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from browser_utils import launch_chromium

SKIP = 77
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed.")
    raise SystemExit(SKIP)

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "mock_nist_bridge.py"
INDEX = ROOT / "software" / "index.html"
PORT = 18993


def patch_session_storage(html: str) -> str:
    shim = (
        "<script>window.__sessionStore={};window.__session={"
        "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
        "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
        "removeItem:k=>{delete __sessionStore[k]}};</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def wait_up(proc: subprocess.Popen, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2).read()
            return
        except (urllib.error.URLError, OSError):
            if proc.poll() is not None:
                raise SystemExit("mock bridge exited")
            time.sleep(0.1)
    raise SystemExit("mock bridge did not start")


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(BRIDGE), "--port", str(PORT), "--mode", "demo"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_up(proc)
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
            page.set_content(html, wait_until="load")
            out = page.evaluate(
                """async port=>{
                const mk=(rt,scan,mz)=>({rt,scan,tic:100000,rawMZ:mz,rawI:mz.map(()=>1000),
                  dc:{mz:mz,i:mz.map((_,i)=>1000-i*100),t:mz.map(()=>10),nRaw:mz.length,nBefore:mz.length,nModelIons:Math.min(2,mz.length)},
                  cands:[],nistcandidates15:[],nistDone:false,nistExternalDone:false,aiDone:false});
                G.results=[mk(5,100,[43]),mk(6,200,[43,57]),mk(7,300,[43,57,71])];G.ok=true;
                G.rt=Float64Array.from([5,6,7]);G.tic=Float64Array.from([100000,100000,100000]);G.n=3;
                document.getElementById('nistMinIonCount').value='3';
                const built=buildMSPBlocksForNIST();
                const resp=await fetch('http://127.0.0.1:'+port+'/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msp:built.blocks.join('\\r\\n'),max_candidates:3})});
                const data=await resp.json();
                const merged=mergeNISTExternalResults(data.groups);
                return {count:built.count,block:built.blocks[0],merged,
                  states:G.results.map(r=>({eligible:componentSearchEligibility(r).eligible,nist:r.nistDone||false,name:r.cands&&r.cands[0]?r.cands[0].name:''}))};
                }""",
                PORT,
            )
            browser.close()
        if errors:
            raise SystemExit(f"page errors: {errors}")
        if out["count"] != 1 or "PGCMS_0003" not in out["block"] or "PyGCMS_Index=3" not in out["block"]:
            raise SystemExit(f"eligibility/MSP mapping failed: {out}")
        if out["merged"] != 1 or not out["states"][2]["nist"] or out["states"][0]["nist"] or out["states"][1]["nist"]:
            raise SystemExit(f"NIST merge attached to wrong component: {out}")
        print("PASS: 1- and 2-ion components are retained but not auto-submitted; the eligible third component maps correctly")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
