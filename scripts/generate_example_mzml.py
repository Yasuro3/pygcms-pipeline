#!/usr/bin/env python3
"""Generate the small public mzML example used by the quick-start workflow.

The fixture contains three well-separated nominal-mass EI-like component profiles
and is intentionally synthetic.  At the released default settings it produces
non-zero deconvolution results, so first-time users can proceed through the mock
candidate workflow without changing thresholds.
"""
from __future__ import annotations

import base64
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "example" / "synthetic_gc_ms.mzML"


def pack64(values: list[float]) -> str:
    return base64.b64encode(struct.pack("<" + "d" * len(values), *values)).decode("ascii")


def gauss(rt: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((rt - mu) / sigma) ** 2)


def main() -> None:
    scans: list[tuple[float, list[float], list[float]]] = []
    # Three synthetic components with distinct but partially shared nominal ions.
    components = [
        (3.5, 0.18, {43: 120000.0, 57: 80000.0, 71: 35000.0}),
        (6.2, 0.22, {77: 55000.0, 91: 140000.0, 105: 50000.0}),
        (9.0, 0.20, {43: 30000.0, 95: 85000.0, 96: 125000.0, 124: 25000.0}),
    ]
    for i in range(121):
        rt = i * 0.1
        intensities: dict[int, float] = {43: 80.0, 57: 60.0, 71: 40.0, 77: 40.0, 91: 50.0, 95: 40.0, 96: 40.0, 105: 30.0, 124: 20.0}
        for mu, sigma, spectrum in components:
            f = gauss(rt, mu, sigma)
            for mz, amp in spectrum.items():
                intensities[mz] = intensities.get(mz, 0.0) + amp * f
        mzs = sorted(intensities)
        vals = [float(intensities[m]) for m in mzs]
        scans.append((rt, [float(m) for m in mzs], vals))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">',
        f'  <run id="synthetic_gc_ms_v132"><spectrumList count="{len(scans)}">',
    ]
    for idx, (rt, mzs, vals) in enumerate(scans):
        tic = sum(vals)
        lines.extend([
            f'    <spectrum id="scan={idx+1}" index="{idx}" defaultArrayLength="{len(mzs)}">',
            '      <cvParam accession="MS:1000511" name="ms level" value="1"/>',
            f'      <cvParam accession="MS:1000285" name="total ion current" value="{tic:.6f}"/>',
            f'      <scanList count="1"><scan><cvParam accession="MS:1000016" name="scan start time" value="{rt:.4f}" unitAccession="UO:0000031" unitName="minute"/></scan></scanList>',
            '      <binaryDataArrayList count="2">',
            f'        <binaryDataArray encodedLength="0"><cvParam accession="MS:1000514" name="m/z array"/><cvParam accession="MS:1000523" name="64-bit float"/><cvParam accession="MS:1000576" name="no compression"/><binary>{pack64(mzs)}</binary></binaryDataArray>',
            f'        <binaryDataArray encodedLength="0"><cvParam accession="MS:1000515" name="intensity array"/><cvParam accession="MS:1000523" name="64-bit float"/><cvParam accession="MS:1000576" name="no compression"/><binary>{pack64(vals)}</binary></binaryDataArray>',
            '      </binaryDataArrayList>',
            '    </spectrum>',
        ])
    lines.extend(['  </spectrumList></run>', '</mzML>', ''])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(scans)} spectra)")


if __name__ == "__main__":
    main()
