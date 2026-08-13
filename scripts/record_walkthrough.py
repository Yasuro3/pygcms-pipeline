#!/usr/bin/env python3
"""Record a short licence-free PyGCMS Pipeline walkthrough.

The recording uses the public synthetic mzML and synthetic mock bridge. It does
not invoke NIST software and does not contain experimental identifications.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "software" / "index.html"
EXAMPLE = ROOT / "data" / "example" / "synthetic_gc_ms.mzML"
MOCK = ROOT / "scripts" / "mock_nist_bridge.py"


def wait_up(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
            return
        except Exception:
            time.sleep(0.15)
    raise RuntimeError("mock bridge did not start")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=ROOT / "media")
    ap.add_argument("--port", type=int, default=18789)
    ap.add_argument("--chromium", default="/usr/bin/chromium")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    temp = args.outdir / "_recording_tmp"
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True)

    proc = subprocess.Popen([sys.executable, str(MOCK), "--port", str(args.port), "--mode", "adversarial"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_up(args.port)
        with sync_playwright() as pw:
            launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if args.chromium and Path(args.chromium).exists():
                launch["executable_path"] = args.chromium
            browser = pw.chromium.launch(**launch)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=str(temp),
                record_video_size={"width": 1440, "height": 900},
                accept_downloads=True,
            )
            page = context.new_page()
            html = INDEX.read_text(encoding="utf-8")
            shim = ("<script>window.__sessionStore={};window.__session={"
                    "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
                    "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
                    "removeItem:k=>{delete __sessionStore[k]}};</script>")
            html = html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")
            page.set_content(html, wait_until="load")
            page.evaluate("""() => {
                const n=document.createElement('div'); n.id='walkBanner';
                Object.assign(n.style,{position:'fixed',left:'18px',bottom:'18px',zIndex:'99999',padding:'10px 16px',borderRadius:'8px',background:'rgba(2,45,77,.93)',color:'white',font:'600 18px Arial',boxShadow:'0 3px 12px rgba(0,0,0,.25)'});
                n.textContent='Licence-free walkthrough: synthetic data and synthetic candidates'; document.body.appendChild(n);
            }""")
            page.wait_for_timeout(1800)
            page.set_input_files("#fi", str(EXAMPLE))
            page.wait_for_function("!document.getElementById('btnRun').disabled", timeout=120000)
            page.evaluate("document.getElementById('walkBanner').textContent='1. Load the working synthetic mzML example'")
            page.wait_for_timeout(1800)
            page.click("#btnRun")
            page.evaluate("document.getElementById('walkBanner').textContent='2. Run configurable deconvolution with the documented defaults'")
            page.wait_for_function("G.results.length===3 && !document.getElementById('btnRun').disabled", timeout=120000)
            page.wait_for_timeout(1800)
            page.evaluate("document.getElementById('walkBanner').textContent='3. Connect to the clearly labelled synthetic mock bridge'")
            page.click("text=Check connection")
            page.wait_for_function("document.getElementById('nistBridgeStatus').textContent.toLowerCase().includes('connected') || document.getElementById('nistBridgeStatus').textContent.toLowerCase().includes('mock')", timeout=30000)
            page.wait_for_timeout(1500)
            page.evaluate("document.getElementById('walkBanner').textContent='4. Search eligible spectra; every returned top-N candidate is preserved'")
            page.click("text=Run NIST search")
            page.wait_for_function("G.results.filter(r=>r.nistExternalDone).length===3", timeout=120000)
            page.wait_for_timeout(1800)
            page.locator("#tB tr").first.click()
            page.wait_for_timeout(1200)
            page.evaluate("document.getElementById('walkBanner').textContent='5. Inspect MF gap, unique species and the complete candidate record'")
            page.wait_for_timeout(1800)
            candidates = page.locator(".csel")
            if candidates.count() > 1:
                candidates.nth(1).click()
                page.wait_for_timeout(800)
                candidates = page.locator(".csel")
                candidates.first.click()
            page.evaluate("document.getElementById('walkBanner').textContent='6. Manual reselection is idempotent; raw ranks and scores remain archived'")
            page.wait_for_timeout(1800)
            page.evaluate("document.getElementById('walkBanner').textContent='7. Export components, candidates, settings and provenance for audit'")
            page.wait_for_timeout(1800)
            page.evaluate("document.getElementById('walkBanner').textContent='Synthetic demonstration only — no NIST software or licensed spectra used'")
            page.wait_for_timeout(2200)
            video = page.video
            context.close()
            browser.close()
            webm_path = Path(video.path())

        target_webm = args.outdir / "PyGCMS_Pipeline_v1.3.1_mock_walkthrough.webm"
        shutil.copy2(webm_path, target_webm)
        target_mp4 = args.outdir / "PyGCMS_Pipeline_v1.3.1_mock_walkthrough.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(target_webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "24", str(target_mp4)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"WROTE: {target_webm}")
        print(f"WROTE: {target_mp4}")
        return 0
    finally:
        for child in (proc,):
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
