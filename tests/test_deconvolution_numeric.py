#!/usr/bin/env python3
"""Numerical ground-truth test for the deconvolution stage.

The candidate-preservation tests establish that the software does not lose
library candidates. They say nothing about whether the chromatographic
extraction itself is numerically correct. This test closes that gap for the
part of the problem that has a knowable answer.

A synthetic chromatogram is built in which the ground truth is defined by
construction: three components at known retention times, each with a known
nominal-mass spectrum, laid down as Gaussian elution profiles on a smooth
background. Two of them deliberately overlap at 40% of their peak width and
share a fragment ion, which is the situation deconvolution exists to resolve.
The released application is then driven headlessly over the file, and the
recovered components are compared against the values used to synthesise it.

What is asserted:

  D1  Every synthetic component is detected exactly once, at the correct scan.
  D2  Recovered apex retention times match the synthetic values.
  D3  The reconstructed spectrum of an isolated component reproduces the
      synthetic spectrum (cosine similarity on nominal-mass vectors).
  D4  For the overlapping pair, each reconstructed spectrum matches its own
      synthetic spectrum and not its neighbour's. Unique fragments must not
      be smeared between the two reconstructed spectra; D5 separately fixes the
      documented treatment of the fragment shared by both components.
  D5  Characterisation of the shared-fragment boundary. At the archived default
      correlation threshold the ion shared by the overlapping pair is admitted to
      neither reconstructed spectrum, because its trace carries two apices and
      therefore co-varies poorly with either single-component model profile. This
      is asserted as the documented behaviour so that any future change to the
      grouping rule breaks this test and forces the documentation to be revised.
  D6  No component is invented in a region containing background only.

Scope. This tests the extraction arithmetic against a synthetic reference. It
does not establish performance on real pyrograms, where true peak shapes are
not Gaussian and the background is not smooth. No claim about compound
identification is made or implied.

Requires: pip install -r requirements-browser.txt && playwright install chromium
Runs offline. No NIST software, no licensed library, no vendor-native file.
"""
from __future__ import annotations

import base64
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed. Install with "
          "'pip install -r requirements-browser.txt && playwright install chromium' "
          "to verify the deconvolution arithmetic.")
    raise SystemExit(77)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "software" / "index.html"

# ----------------------------------------------------------------- ground truth
N_SCANS = 600
RT_START, RT_STEP = 5.0, 0.01          # minutes
MZ_LO, MZ_HI = 40, 160
BASELINE = 2000.0

# (label, apex_scan, sigma_scans, {m/z: relative intensity})
TRUTH = [
    ("isolated", 120, 3.0, {57: 1.00, 71: 0.55, 85: 0.30, 43: 0.22}),
    ("overlap_A", 300, 3.0, {94: 1.00, 66: 0.60, 39: 0.35, 108: 0.25}),
    ("overlap_B", 312, 3.0, {96: 1.00, 81: 0.70, 39: 0.40, 53: 0.20}),
]
SHARED_MZ = 39                          # deliberately shared by overlap_A and overlap_B
APEX_HEIGHT = 900000.0
EMPTY_REGION = (430, 560)               # background only; nothing may be detected here


def gaussian(scan: int, apex: float, sigma: float) -> float:
    return math.exp(-((scan - apex) ** 2) / (2.0 * sigma * sigma))


def build_truth_matrix() -> list[dict[int, float]]:
    """Intensity of every m/z at every scan, from the ground truth."""
    scans: list[dict[int, float]] = []
    for s in range(N_SCANS):
        row: dict[int, float] = {}
        # smooth, slowly rising background on a few low ions
        for mz in (44, 45, 46):
            row[mz] = BASELINE * (1.0 + 0.4 * s / N_SCANS)
        for _label, apex, sigma, spec in TRUTH:
            g = gaussian(s, apex, sigma)
            if g < 1e-6:
                continue
            for mz, rel in spec.items():
                row[mz] = row.get(mz, 0.0) + APEX_HEIGHT * rel * g
        scans.append(row)
    return scans


def encode(values: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode("ascii")


def write_mzml(path: Path) -> None:
    scans = build_truth_matrix()
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<indexedmzML xmlns="http://psi.hupo.org/ms/mzml">',
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">',
        '<cvList count="1"><cv id="MS" fullName="PSI-MS" URI="https://psidev.info/ms"/></cvList>',
        '<softwareList count="1"><software id="synthetic_fixture" version="1.0">'
        '<cvParam cvRef="MS" accession="MS:1000799" name="custom unreleased software tool"/>'
        '</software></softwareList>',
        f'<run id="deconvolution_ground_truth"><spectrumList count="{N_SCANS}">',
    ]
    for i, row in enumerate(scans):
        mzs = sorted(m for m in row if MZ_LO <= m <= MZ_HI)
        ints = [row[m] for m in mzs]
        tic = sum(ints)
        rt = RT_START + i * RT_STEP
        mz_b64, in_b64 = encode([float(m) for m in mzs]), encode(ints)
        parts.append(
            f'<spectrum index="{i}" id="scan={i+1}" defaultArrayLength="{len(mzs)}">'
            f'<cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>'
            f'<cvParam cvRef="MS" accession="MS:1000127" name="centroid spectrum"/>'
            f'<cvParam cvRef="MS" accession="MS:1000285" name="total ion current" value="{tic:.4f}"/>'
            f'<scanList count="1"><scan><cvParam cvRef="MS" accession="MS:1000016" '
            f'name="scan start time" value="{rt:.6f}" unitAccession="UO:0000031" unitName="minute"/>'
            f'</scan></scanList>'
            f'<binaryDataArrayList count="2">'
            f'<binaryDataArray encodedLength="{len(mz_b64)}">'
            f'<cvParam cvRef="MS" accession="MS:1000521" name="32-bit float"/>'
            f'<cvParam cvRef="MS" accession="MS:1000576" name="no compression"/>'
            f'<cvParam cvRef="MS" accession="MS:1000514" name="m/z array"/>'
            f'<binary>{mz_b64}</binary></binaryDataArray>'
            f'<binaryDataArray encodedLength="{len(in_b64)}">'
            f'<cvParam cvRef="MS" accession="MS:1000521" name="32-bit float"/>'
            f'<cvParam cvRef="MS" accession="MS:1000576" name="no compression"/>'
            f'<cvParam cvRef="MS" accession="MS:1000515" name="intensity array"/>'
            f'<binary>{in_b64}</binary></binaryDataArray>'
            f'</binaryDataArrayList></spectrum>'
        )
    parts += ['</spectrumList></run></mzML></indexedmzML>']
    path.write_text("".join(parts), encoding="utf-8")


def patch_session_storage(html: str) -> str:
    shim = "<script>window.__session={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};</script>"
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def cosine(a: dict[int, float], b: dict[int, float]) -> float:
    keys = set(a) | set(b)
    num = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return num / (na * nb) if na and nb else 0.0


LOAD = """async () => {
  const f = document.getElementById('gtFile').files[0];
  const d = await readRawFile(f);
  G.rt=d.rt; G.tic=d.tic; G.n=d.n; G.si=null; G.ms=null;
  G.preloadedScanMaps=d.scanMaps; G.ok=true; G.results=[]; G.scanMaps=null;
  buildEIC();
  return {n:G.n, nMZ:G.nMZ, rt0:G.rt[0], rt1:G.rt[G.n-1]};
}"""

RUN = """() => {
  document.getElementById('pRT').value = 0;
  document.getElementById('pBleed').checked = false;
  window.__logStart = document.getElementById('log').textContent.length;
  window.__t0 = performance.now();
  runPipeline();
}"""

COLLECT = """() => ({
  elapsed_seconds: (performance.now() - window.__t0) / 1000,
  components: G.results.map(r => ({
    scan: r.scan, rt: r.rt,
    spec: Array.from(r.dc.mz).map((m, i) => [m, Array.from(r.dc.i)[i]])
  }))
})"""


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    mzml = tmp / "gt.mzML"
    write_mzml(mzml)

    html = patch_session_storage(INDEX.read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            print(f"SKIP: chromium is unavailable ({exc.__class__.__name__}). "
                  "Run 'playwright install chromium' to verify the deconvolution arithmetic.")
            return 77
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_default_timeout(180000)
        page.set_content(html, wait_until="load")
        page.evaluate("()=>{const x=document.createElement('input');x.type='file';"
                      "x.id='gtFile';document.body.appendChild(x)}")
        page.set_input_files("#gtFile", str(mzml))
        loaded = page.evaluate(LOAD)
        if loaded["n"] != N_SCANS:
            raise SystemExit(f"fixture load failed: {loaded['n']} scans != {N_SCANS}")
        page.evaluate(RUN)
        page.wait_for_function(
            "document.getElementById('log').textContent.slice(window.__logStart)"
            ".includes('Deconvolution complete:') && !document.getElementById('btnRun').disabled"
        )
        out = page.evaluate(COLLECT)
        browser.close()
    if errors:
        raise SystemExit(f"page errors: {errors}")

    comps = out["components"]
    if not comps:
        raise SystemExit("D1 FAILED: no components were extracted from the ground-truth fixture")

    # --- D1 / D2: each truth component matched exactly once, at the right scan
    matched: dict[str, dict] = {}
    for label, apex, _sigma, _spec in TRUTH:
        near = [c for c in comps if abs(c["scan"] - apex) <= 2]
        if len(near) != 1:
            raise SystemExit(
                f"D1 FAILED: component '{label}' (apex scan {apex}) matched {len(near)} extracted "
                f"components; expected exactly 1. Extracted scans: {[c['scan'] for c in comps]}")
        matched[label] = near[0]
        rt_expect = RT_START + apex * RT_STEP
        if abs(near[0]["rt"] - rt_expect) > 0.03:
            raise SystemExit(
                f"D2 FAILED: '{label}' apex rt {near[0]['rt']:.4f} != expected {rt_expect:.4f} min")
    print("PASS: D1 every synthetic component detected exactly once at the correct scan")
    print("PASS: D2 recovered apex retention times match the synthetic values")

    truth_spec = {lab: spec for lab, _a, _s, spec in TRUTH}
    got_spec = {lab: {int(m): float(v) for m, v in rec["spec"]} for lab, rec in matched.items()}

    # --- D3: isolated component spectrum reproduced
    sim_iso = cosine(truth_spec["isolated"], got_spec["isolated"])
    if sim_iso < 0.95:
        raise SystemExit(f"D3 FAILED: isolated component cosine similarity {sim_iso:.4f} < 0.95")
    print(f"PASS: D3 isolated component spectrum reproduced (cosine {sim_iso:.4f})")

    # --- D4: overlapping pair resolved to their OWN spectra, not each other's
    report = []
    for lab, other in (("overlap_A", "overlap_B"), ("overlap_B", "overlap_A")):
        own = cosine(truth_spec[lab], got_spec[lab])
        cross = cosine(truth_spec[other], got_spec[lab])
        report.append((lab, own, cross))
        if own < 0.90:
            raise SystemExit(
                f"D4 FAILED: '{lab}' cosine to its own synthetic spectrum {own:.4f} < 0.90; "
                "the overlapping pair was not resolved")
        if own <= cross:
            raise SystemExit(
                f"D4 FAILED: '{lab}' resembles its neighbour at least as much as itself "
                f"(own {own:.4f} <= cross {cross:.4f}); spectra were smeared, not deconvolved")
    for lab, own, cross in report:
        print(f"PASS: D4 '{lab}' resolved to its own spectrum (own {own:.4f} vs neighbour {cross:.4f})")

    # --- D5: characterise the shared-fragment boundary (documented behaviour)
    shared_in = [lab for lab in ("overlap_A", "overlap_B") if SHARED_MZ in got_spec[lab]]
    if shared_in:
        raise SystemExit(
            f"D5 FAILED: shared ion m/z {SHARED_MZ} is now present in {shared_in}. The documented "
            "behaviour is that an ion shared by an overlapping pair is admitted to neither "
            "reconstructed spectrum at the default correlation threshold. If the grouping rule was "
            "changed deliberately, update docs/LIMITATIONS.md and this test together.")
    print(f"PASS: D5 shared ion m/z {SHARED_MZ} excluded from both overlapping components, "
          "matching the documented shared-fragment limitation (see docs/LIMITATIONS.md)")

    # --- D6: nothing invented in the background-only region
    lo, hi = EMPTY_REGION
    ghosts = [c["scan"] for c in comps if lo <= c["scan"] <= hi]
    if ghosts:
        raise SystemExit(
            f"D6 FAILED: {len(ghosts)} component(s) reported in a background-only region at scans "
            f"{ghosts}")
    print("PASS: D6 no components invented in the background-only region")

    print(f"PASS: deconvolution arithmetic verified against a synthetic ground truth "
          f"({len(comps)} components extracted in {out['elapsed_seconds']:.2f} s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
