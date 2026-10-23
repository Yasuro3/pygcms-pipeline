# PyGCMS Pipeline v1.4.1 — validation report (2026-10-21)

**Status: Experimental / GitHub pre-release candidate, not a certified AMDIS replacement.**

This is the historical 2026-10-21 package-assembly record; `VALIDATION_v141.json` records the same historical stage. The 2026-10-22 AMDIS comparison is described in the addendum below. The separate `PUBLICATION_VALIDATION_v1.4.1-rc1.md` records checks rerun on 2026-10-23.

## Test datasets

Original `神戸大学.zip`, SHA256 `7ee2c59bc8d3f9cf8cf003527ba46061c7421647a257c9801f57198e07a1e2cc`. Source QGD content was read with a SHA256-matched 40-run manifest. No raw QGD files are included in the GitHub source distribution.

## Full-run verification

- 40 QGD acquisitions detected: **29 chromatographic GC runs, 11 EGA profiles**.
- GC candidate components: **10,446**; valid >=3-ion MSP queries: **10,444**, of which **7,978** are FA samples.
- These counts match the preceding globally coupled v0.3.1 engine run on the same archive. The program independently regenerated all 29 runs from the raw QGD again during v1.4.1 packaging.
- Global cell-wise allocated intensity of each run was bounded by the observed nonnegative baseline-corrected signal. **Maximum numerical relative closure error: 2.61e-09.** This is an algorithmic invariant, *not* ground-truth deconvolution validation.
- **Model overprediction remained 7.5–27.9%** across 29 GC runs; **26 / 29** exceeded 10% overprediction. Do not interpret matched signal as chemically assigned area.
- The published **v1.4.0 bridge/runtime cryptographic manifest** and the regenerated v1.4.1 NIST inputs passed `--validate-only` for both ALL=10,444 and FA=7,978 scopes.

## Numerical tests

- Partially coeluting synthetic three-compound test, nonnegative global fit and low residual: PASS.
- Deliberately overpredicting models (coefficients x2) cannot allocate more observed signal: PASS.
- Adjacent indistinguishable shapes/spectra merge; genuinely separated same-spectrum peaks not forcibly merged: PASS.
- Fake NIST result groups returned out-of-order and with incorrect/duplicate IDs are rejected or correctly keyed: PASS.
- Real QGD Q15 (SS, 2004), Q26 (TD, 2004) and Q19 blank: 1,364 component candidates, 1,363 MSP, two-scope input verification: PASS.

## Not yet tested / scientific limitations

1. **Windows NIST 17 Automation end-to-end live search is NOT tested in this environment.** Input compatibility and response mapping were tested; this is not a claim that GUI search finished.
2. **The proprietary NIST AMDIS algorithm was NOT run as an independent benchmark.** Numerical mass closure cannot establish correct separation or prevent all false positives/over-splitting.
3. Underlying baseline, ion noise threshold and EI spectral coverage depend on sample type and GC method; signal coverage must not be equated with abundance or correct compound detection.
4. High L2 or overprediction measurements and near-duplicate spectra require analyst review. MF 700/800 only assesses library match quality of a *proposed* pure spectrum.

## Reproducibility

Software source and SHA256 manifests are distributed. Record each raw QGD digest, `settings/deconvolution.json` digest, release commit, NIST version and libraries, mode, and the query-index digest in the publication SI. Do not recycle v1.4.0 identifications or previous NNLS MSP search results by peak number.


## Later independent AMDIS comparison (2026-10-22)

The preceding statement about AMDIS not being tested records the situation on 2026-10-21. A four-run authentic AMDIS comparison was subsequently performed. See `AMDIS_COMPARISON_2026-10-22_JA.md`. This does not certify complete deconvolution accuracy or remove residual model overprediction.
