#!/usr/bin/env python3
"""Verify candidate preservation through selection, review, and CSV export.

The released browser application is driven against the adversarial synthetic
fixture served by ``scripts/mock_nist_bridge.py``.  No NIST software, licensed
library, licensed spectrum, or vendor-native file is used.

Invariants:

  I1  Every candidate returned by the search stage is present in the exported
      record, up to the selected top-N limit.
  I2  Every exported candidate retains its original rank.
  I3  Match factor, reverse match factor, probability, CAS, and library
      identifier are preserved unmodified.
  I4  Selecting a non-top candidate does not remove or reorder the archived
      alternatives in the candidate columns.
  I5  A component whose candidates are all weak can remain unassigned while
      its original candidates remain in the export.
  I6  A zero-hit component remains in the export as unidentified and receives
      no fabricated candidate.

Requires: ``pip install -r requirements-browser.txt`` and Playwright Chromium.
A missing browser dependency exits with status 77, which ``run_checks.py``
reports as a skip and can treat as an error with ``--require-browser``.
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKIP = 77
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "SKIP: playwright is not installed. Install with "
        "'pip install -r requirements-browser.txt && playwright install chromium' "
        "to verify candidate preservation in the browser."
    )
    raise SystemExit(SKIP)

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


INJECT = r"""
() => {
  const mk = (i, rt, scan) => ({
    rt: rt, scan: scan, tic: 100000 - i * 1000,
    rawMZ: [39, 95, 96], rawI: [210, 999, 610],
    dc: {
      mz: [39, 95, 96], i: [210, 999, 610], t: [8, 12, 9],
      nRaw: 3, nBefore: 3, nModelIons: 2
    },
    cands: [], nistcandidates15: [], nistDone: false,
    nistExternalDone: false, aiDone: false, aiSelected: false
  });
  G.results = [
    mk(1, 5.12, 614), mk(2, 6.48, 778), mk(3, 7.10, 852),
    mk(4, 8.90, 1068), mk(5, 9.55, 1146), mk(6, 10.2, 1224),
    mk(7, 11.8, 1416)
  ];
  G.ok = true;
  G.rt = Float64Array.from(G.results.map(r => r.rt));
  G.tic = Float64Array.from(G.results.map(r => r.tic));
  G.n = G.results.length;
  G.deconvParams = getDeconvParameterSnapshot();
  document.getElementById('pSC').value = 0;
  document.getElementById('nistCandidateCount').value = 15;
  updateCandidateCount();
  return G.results.length;
}
"""

EXERCISE = r"""
async (port) => {
  const blocks = G.results.map((r, idx) => {
    const id = String(idx + 1).padStart(4, '0');
    return [
      'Name: PGCMS_' + id + '_RT_' + r.rt.toFixed(3) + '_SCAN_' + r.scan,
      'Comment: PyGCMS_Index=' + (idx + 1) + ' RT_min=' + r.rt.toFixed(3) + ' Scan=' + r.scan,
      'Num Peaks: 3',
      '39 210; 95 999; 96 610',
      ''
    ].join('\r\n');
  });
  const resp = await fetch('http://127.0.0.1:' + port + '/search', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({msp: blocks.join('\r\n'), max_candidates: 15, index_offset: 0})
  });
  if (!resp.ok) throw new Error('mock bridge returned HTTP ' + resp.status);
  const data = await resp.json();
  const merged = mergeNISTExternalResults(data.groups);
  const sorted = G.results.slice().sort((a, b) => a.rt - b.rt);

  // I4: exercise the application's real selection function by selecting the
  // original rank-2 candidate for the near-tie record.
  selectCandidate(G.results.indexOf(sorted[0]), 1);

  // I5: exercise the deterministic review rule on the all-weak record.
  const weakResult = curateOneByAIQC(sorted[2]);

  return {
    sent: data.groups,
    merged,
    weakResult,
    post: sorted.map(r => ({
      rt: r.rt,
      selectedName: r.cands && r.cands.length ? r.cands[0].name : '',
      selectedRank: r.cands && r.cands.length ? r.cands[0].nistRank || '' : '',
      aiAction: r.aiAction || '',
      aiAnnotationLevel: r.aiAnnotationLevel || '',
      preserved: (r.nistcandidates15 || []).length
    })),
    csvText: buildResultsCSVText()
  };
}
"""


def as_text(value: object) -> str:
    return "" if value is None else str(value)


def assert_equal(actual: object, expected: object, label: str) -> None:
    if as_text(actual) != as_text(expected):
        raise SystemExit(f"{label} FAILED: expected {expected!r}, got {actual!r}")


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(BRIDGE), "--port", str(PORT), "--mode", "adversarial"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_up(proc)
        html = patch_session_storage(INDEX.read_text(encoding="utf-8"))
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:
                print(
                    f"SKIP: chromium is unavailable ({exc.__class__.__name__}). "
                    "Run 'playwright install chromium' to verify candidate preservation."
                )
                return SKIP
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.set_default_timeout(120000)
            page.set_content(html, wait_until="load")
            if page.evaluate(INJECT) != 7:
                raise SystemExit("candidate-test state injection failed")
            out = page.evaluate(EXERCISE, PORT)
            browser.close()

        if errors:
            raise SystemExit(f"page errors: {errors}")
        if out["merged"] != 7:
            raise SystemExit(f"I1 FAILED: merged {out['merged']} of 7 component groups")

        sent = {int(group["query_index"]): group["hits"] for group in out["sent"]}
        rows = list(csv.DictReader(io.StringIO(out["csvText"].lstrip("\ufeff"))))
        if len(rows) != 7:
            raise SystemExit(f"I6 FAILED: export contains {len(rows)} rows; expected 7")

        # I1-I3: compare the actual exported candidate columns with every hit
        # returned by the synthetic bridge. This verifies export, not only import.
        for qidx in range(1, 8):
            hits = sent[qidx]
            row = rows[qidx - 1]
            for pos, hit in enumerate(hits, start=1):
                prefix = f"Cand{pos:02d}_"
                assert_equal(row[prefix + "Name"], hit["name"], f"I1 component {qidx} candidate {pos} name")
                assert_equal(row[prefix + "Rank"], hit["rank"], f"I2 component {qidx} candidate {pos} rank")
                for column, key in (
                    ("MF", "mf"), ("RMF", "rmf"), ("Prob", "prob"),
                    ("CAS", "cas"), ("Lib", "lib"),
                ):
                    assert_equal(
                        row[prefix + column], hit.get(key, ""),
                        f"I3 component {qidx} candidate {pos} {column}",
                    )
            # The first unused candidate slot must be blank, preventing silent
            # fabrication or leakage from another component.
            if len(hits) < 15:
                blank_prefix = f"Cand{len(hits) + 1:02d}_"
                if row[blank_prefix + "Name"]:
                    raise SystemExit(
                        f"I1 FAILED: component {qidx} has fabricated candidate "
                        f"{row[blank_prefix + 'Name']!r}"
                    )

        # I4: rank 2 is selected in the result row while Cand01-Cand03 retain
        # the bridge's original order and values.
        rank2 = sent[1][1]
        assert_equal(rows[0]["Compound"], rank2["name"], "I4 selected candidate name")
        assert_equal(rows[0]["NIST_Rank"], 2, "I4 selected original rank")
        assert_equal(rows[0]["Cand01_Rank"], 1, "I4 archived rank 1")
        assert_equal(rows[0]["Cand02_Rank"], 2, "I4 archived rank 2")
        if out["post"][0]["preserved"] != len(sent[1]):
            raise SystemExit("I4 FAILED: selection changed the preserved snapshot length")

        # The class-conflict pair also remains available in original order.
        assert_equal(rows[1]["Cand01_Name"], "Pyridine", "I4 class-conflict rank 1")
        assert_equal(rows[1]["Cand02_Name"], "Furfural", "I4 class-conflict rank 2")

        # I5: deterministic review rejects all weak candidates but preserves
        # both in Cand01/Cand02 and records the component as unassigned.
        if out["weakResult"]["status"] != "rejected-all":
            raise SystemExit(f"I5 FAILED: all-weak review returned {out['weakResult']}")
        if not rows[2]["Compound"].startswith("Unidentified"):
            raise SystemExit(f"I5 FAILED: all-weak component exported as {rows[2]['Compound']!r}")
        assert_equal(rows[2]["AI_Action"], "rejected-all", "I5 AI action")
        assert_equal(rows[2]["AI_AnnotationLevel"], "unassigned", "I5 annotation level")
        assert_equal(rows[2]["Cand01_Name"], sent[3][0]["name"], "I5 preserved weak rank 1")
        assert_equal(rows[2]["Cand02_Name"], sent[3][1]["name"], "I5 preserved weak rank 2")

        # I6: zero-hit component remains as a row and all candidate fields are blank.
        assert_equal(rows[3]["Scan"], 1068, "I6 retained zero-hit scan")
        if rows[3]["Cand01_Name"] or rows[3]["Cand01_MF"] or rows[3]["Cand01_Rank"]:
            raise SystemExit("I6 FAILED: zero-hit component contains a fabricated candidate")

        print("PASS: I1 every returned top-N candidate is present in the CSV export")
        print("PASS: I2 original candidate ranks are preserved in the CSV export")
        print("PASS: I3 MF, RMF, probability, CAS, and library are unmodified")
        print("PASS: I4 selecting original rank 2 leaves all alternatives intact")
        print("PASS: I5 all-weak candidates remain archived while the component is unassigned")
        print("PASS: I6 the zero-hit component remains unidentified without fabricated hits")
        print("PASS: candidate preservation verified without NIST software or licensed data")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
