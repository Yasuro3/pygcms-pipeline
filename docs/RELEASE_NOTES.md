# Release notes - v1.3.0

- Added `scripts/mock_nist_bridge.py`, an offline test double of the licensed-search bridge. It returns clearly labelled synthetic candidates from `MOCKLIB-SYNTHETIC-1.0`, allowing the candidate-handling path to be exercised without NIST software, a licensed library, a NIST spectrum, or a vendor-native file.
- Added the adversarial mock fixture and `tests/test_candidate_preservation.py`. The browser test now exercises actual non-top candidate selection, deterministic rejection of an all-weak candidate list, and CSV export before asserting invariants I1-I6. It verifies the exported candidate columns rather than stopping at import state.
- Added `tests/test_deconvolution_numeric.py`, which drives the released browser application over a synthetic chromatogram with known scans and spectra. It verifies exact component recovery, retention times, an isolated-spectrum cosine of 1.000, separation of an overlapping pair (own-spectrum cosine 0.960 and 0.952; cross-cosine 0.000), the documented exclusion of a shared fragment at the default correlation threshold, and absence of background-only ghost components.
- Browser tests now exit with status 77 when Playwright or Chromium is unavailable. `scripts/run_checks.py` reports `PASS WITH SKIPS` in that case and supports `--require-browser` for a strict result; a missing browser can no longer be mistaken for full browser-test success.
- Added lightweight figure generation for automated checks (`scripts/generate_figures.py --check-only`), avoiding unnecessary 600-1000 dpi TIFF/PNG work during routine verification while preserving full publication output in normal mode.
- Added machine-readable literature classification exports (`provenance/literature_classification_rules.json`, `provenance/literature_classification_rules.csv`, and `provenance/literature_sources.csv`) plus `scripts/extract_literature_rules.py --check` to keep them synchronized with the application's embedded database.
- Added `CHECKSUMS.sha256` and `scripts/verify_checksums.py`.
- Added an archived full-length timing note. The values are explicitly described as single-run diagnostics because the original run did not record hardware or browser-build metadata. Updated browser validation records those fields for future runs and uses Playwright's bundled Chromium unless `--chromium` is supplied.
- Corrected distributed version strings and paths to v1.3.0 and `software/index.html`.
- Clarified that the archive contains the aggregate Lake Biwa class-summary table used for Figure 4, not component- or candidate-level application records. Area-weighted class composition therefore cannot be reconstructed from this release.
- Removed absolute local paths from derived records; provenance paths are archive relative.

# Release notes - v1.2.0

- Public input restricted to mzML; no vendor-native parser or conversion code is distributed.
- Configurable nominal-mass chromatographic deconvolution documented in the interface, manuscript, and Supplementary Information.
- Adjustable controls include minimum retention time, TIC height, peak separation, half-window, shape correlation, ion cutoff, ion-apex intensity, trace-intensity threshold, sharpness threshold, model-ion fraction, maximum model ions, and common-bleed exclusion.
- Added export, import, and reset controls for parameter presets using schema `PyGCMS-deconvolution-parameters-v1`.
- Top-N candidate preservation, decision rationale, and provenance records retained.
- Optional external-model review separated from deterministic local QC.
- Lake Biwa Figure 4 normalized only to literature-classified records and ordered TD L1-L5 followed by Py L1-L5.
- Deterministic figure generation and the aggregate class-summary source table included.
