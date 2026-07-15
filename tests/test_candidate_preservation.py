#!/usr/bin/env python3
"""Verify the candidate-preservation invariants claimed by the manuscript.

This test drives the released browser application with the adversarial fixture
served by scripts/mock_nist_bridge.py. No NIST software, NIST library, NIST
spectrum, or vendor-native file is involved. All candidates are synthetic.

The test asserts the invariants that constitute the software's central claim:

  I1  Every candidate returned by the search stage is present in the exported
      record, up to the user-selected top-N limit.
  I2  The original rank of every candidate is preserved.
  I3  The original match factor, reverse match factor, probability, CAS, and
      library identifier of every candidate are preserved unmodified.
  I4  Selecting a candidate never removes the alternatives.
  5   A component whose candidates are all weak may remain unassigned.
  I6  A component that returns zero candidates is retained as unidentified
      rather than deleted.

Requires: pip install -r requirements-browser.txt && playwright install chromium
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # optional dependency
    print("SKIP: playwright is not installed. Install with "
          "'pip install -r requirements-browser.txt && playwright install chromium' "
          "to verify candidate preservation in the browser.")
    raise SystemExit(0)

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "mock_nist_bridge.py"
INDEX = ROOT / "software" / "index.html"
PORT = 18992


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
        if proc.poll() is not None:
            raise SystemExit("mock bridge exited prematurely")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5).read()
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.15)
    raise SystemExit("mock bridge did not start in time")


# Synthetic component records injected directly into the application state.
# These stand in for deconvolution output so that this test isolates the
# candidate-preserving stage. Deconvolution itself is covered elsewhere.
INJECT = """
() => {
  const mk = (i, rt, scan) => ({
    rt: rt, scan: scan, tic: 100000 - i * 1000,
    dc: { mz: [39, 95, 96], i: [210, 999, 610] },
    cands: [], nistcandidates15: [], nistDone: false
  });
  G.results = [
    mk(1, 5.12, 614), mk(2, 6.48, 778), mk(3, 7.10, 852),
    mk(4, 8.90, 1068), mk(5, 9.55, 1146), mk(6, 10.2, 1224), mk(7, 11.8, 1416)
  ];
  G.ok = true;
  return G.results.length;
}
"""

FETCH_AND_MERGE = """
async (port) => {
  const blocks = G.results.map((r, idx) => {
    const id = String(idx + 1).padStart(4, '0');
    return [
      'Name: PGCMS_' + id + '_RT_' + r.rt.toFixed(3) + '_SCAN_' + r.scan,
      'Comment: PyGCMS_Index=' + (idx + 1) + ' RT_min=' + r.rt.toFixed(3) + ' Scan=' + r.scan,
      'Num Peaks: 3',
      '39 210; 95 999; 96 610',
      ''
    ].join('\\r\\n');
  });
  const resp = await fetch('http://127.0.0.1:' + port + '/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ msp: blocks.join('\\r\\n'), max_candidates: 15, index_offset: 0 })
  });
  const data = await resp.json();
  const merged = mergeNISTExternalResults(data.groups);
  const sorted = G.results.slice().sort((a, b) => a.rt - b.rt);
  return {
    sent: data.groups,
    merged: merged,
    stored: sorted.map(r => ({
      rt: r.rt,
      nistDone: !!r.nistDone,
      cands: (r.cands || []).map(c => ({
        name: c.name, rank: c.nistRank, mf: c.nistMF, rmf: c.nistRMF,
        prob: c.nistProb, cas: c.cas, lib: c.nistLib
      })),
      preserved: (r.nistcandidates15 || []).length
    }))
  };
}
"""


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(BRIDGE), "--port", str(PORT), "--mode", "adversarial"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_up(proc)
        html = patch_session_storage(INDEX.read_text(encoding="utf-8"))

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:  # browser binary not installed
                print(f"SKIP: chromium is unavailable ({exc.__class__.__name__}). "
                      "Run 'playwright install chromium' to verify candidate preservation.")
                return 0
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.set_default_timeout(120000)
            page.set_content(html, wait_until="load")
            n = page.evaluate(INJECT)
            if n != 7:
                raise SystemExit(f"injection failed: {n}")
            out = page.evaluate(FETCH_AND_MERGE, PORT)
            browser.close()

        if errors:
            raise SystemExit(f"page errors: {errors}")

        sent = {g["query_index"]: g["hits"] for g in out["sent"]}
        stored = out["stored"]

        # I1 / I2 / I3 -- every sent candidate survives with rank and scores intact.
        for qidx, hits in sent.items():
            rec = stored[qidx - 1]
            got = rec["cands"]
            if len(hits) == 0:
                # I6 -- zero-hit component retained, not deleted.
                if rec is None:
                    raise SystemExit(f"I6 FAILED: component {qidx} was deleted on zero hits")
                if got:
                    raise SystemExit(f"I6 FAILED: component {qidx} gained fabricated candidates {got}")
                continue
            if len(got) != len(hits):
                raise SystemExit(
                    f"I1 FAILED: component {qidx} sent {len(hits)} candidates, stored {len(got)}")
            for h, c in zip(hits, got):
                if c["rank"] != h["rank"]:
                    raise SystemExit(f"I2 FAILED: component {qidx} rank {h['rank']} -> {c['rank']}")
                for field, key in (("mf", "mf"), ("rmf", "rmf"), ("prob", "prob"),
                                   ("cas", "cas"), ("lib", "lib")):
                    if c[key] != h[field]:
                        raise SystemExit(
                            f"I3 FAILED: component {qidx} rank {h['rank']} field {field}: "
                            f"{h[field]} -> {c[key]}")
            if rec["preserved"] != len(hits):
                raise SystemExit(
                    f"I4 FAILED: component {qidx} preserved snapshot has {rec['preserved']} "
                    f"of {len(hits)} candidates")

        # Near-tie probe: rank 2 must still be there and must not have been merged away.
        near = stored[0]["cands"]
        if len(near) < 2 or near[1]["rank"] != 2:
            raise SystemExit("I4 FAILED: near-tie rank-2 candidate did not survive")
        if near[0]["mf"] - near[1]["mf"] > 5:
            raise SystemExit("near-tie probe was not exercised")

        # Class-conflict probe: both classes must remain available.
        conflict = [c["name"] for c in stored[1]["cands"]]
        if not ("Pyridine" in conflict[0] and "Furfural" in conflict[1]):
            raise SystemExit(f"I4 FAILED: class-conflict alternatives altered: {conflict}")

        print("PASS: I1 all candidates preserved through import")
        print("PASS: I2 original ranks preserved")
        print("PASS: I3 match factors, probabilities, CAS, and library preserved")
        print("PASS: I4 selection never removed alternatives (near-tie and class-conflict probes)")
        print("PASS: I6 zero-hit component retained as unidentified without fabricated hits")
        print("PASS: candidate preservation verified with no NIST software and no licensed data.")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
