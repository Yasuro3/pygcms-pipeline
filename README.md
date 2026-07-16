# PyGCMS Pipeline v1.3.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21369547.svg)](https://doi.org/10.5281/zenodo.21369547)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)

PyGCMS Pipeline is a fixed, English-language research-software release for efficient analysis of nominal-mass, full-scan pyrolysis GC-MS chromatograms. The browser application reads a documented mzML subset, performs configurable chromatographic deconvolution, sends reconstructed component spectra to a separately licensed local NIST MS Search installation, and preserves the returned top-N candidates with their original ranks, scores, selected status, rationale, analysis parameters, and run provenance.

The release does not claim a new deconvolution theory. Its contribution is an integrated and auditable workflow in which users can optimize processing parameters for their chromatographic system, export and re-import the exact preset, retain alternative library candidates, and revisit decisions without repeating the library search.

## Quick start

1. Convert authorized vendor-native full-scan data to mzML outside this archive.
2. Validate the mzML structure:

   ```bash
   python scripts/validate_mzml_structure.py your_file.mzML --output validation.json
   ```

3. Open `software/index.html` in a Chromium-based desktop browser, or use
   `00_START_EN.cmd` on Windows to start the production localhost bridge and
   open the application.
4. Load the mzML, inspect the TIC and representative spectra, and optimize the
   adjustable deconvolution controls.
5. Export the accepted parameter preset and retain it with the run record.
6. Use a locally licensed NIST MS Search installation through the production
   bridge, or use the clearly labelled mock bridge for licence-free software
   verification. Preserve the returned candidates and export the component,
   candidate, and provenance records.

## Licensed NIST MS Search bridge on Windows

The archive includes the production localhost bridge that was present in the
original optimized distribution and has been adapted to the released
`software/index.html` interface:

- `scripts/nist_mssearch_bridge_server.py` - HTTP bridge used by the browser
- `scripts/nist_mssearch_bridge.py` - NIST file-automation and result parser
- `scripts/nist_dll_backend.py` - optional DLL backend
- `00_START_EN.cmd` and diagnostic launchers - Windows startup and checks

Copy `nistms_path.example.txt` to `nistms_path.txt`, enter the full path to the
user's licensed `NISTMS$.EXE`, configure NIST Automation and the number of hits
to print, and then run `00_START_EN.cmd`. No NIST executable, library, licence,
or reference spectrum is included. Detailed instructions are in
`docs/NIST_BRIDGE_SETUP.md`.

## Verify without a NIST licence

NIST MS Search is a separately licensed dependency and is not distributed here. So that the
candidate-preserving stage remains checkable by a reader who has no licence, the archive includes an
offline **mock** of the bridge. It re-implements the bridge interface contract and returns synthetic
candidates from a fictitious library.

```bash
# Terminal 1 - start the mock
python scripts/mock_nist_bridge.py                     # demo mode
python scripts/mock_nist_bridge.py --mode adversarial  # edge-case fixture

# Terminal 2 - portable checks (reports browser skips explicitly)
python scripts/run_checks.py

# Strict verification: require Playwright Chromium
python -m pip install -r requirements-browser.txt
playwright install chromium
python scripts/run_checks.py --require-browser
```

Then open `software/index.html`, leave the bridge URL at `http://127.0.0.1:18789`, press
**Check bridge**, load `data/example/synthetic_gc_ms.mzML`, run the analysis, and press
**Run NIST search**.

The mock verifies **software behaviour, not chemistry**. Whether a rank-2 candidate and its original
score survive in the exported record after rank 1 was selected is determinate independently of
whether rank 1 is chemically correct. Match-factor accuracy and compound identification are outside
its scope and are not claimed. Every mock hit is labelled `MOCKLIB-SYNTHETIC-1.0` and every response
carries a synthetic banner, so exports made against the mock cannot be mistaken for analytical
results. See `docs/MOCK_BRIDGE.md`. The browser test selects a non-top hit, exercises an all-weak unassigned case, and verifies the actual exported CSV fields.

## Adjustable processing

The interface exposes controls for minimum retention time, TIC peak height, peak separation, local half-window, ion-shape correlation, spectral cutoff, ion-apex intensity, trace intensity, local sharpness, model-ion fraction, maximum model ions, and common column-bleed exclusion. Presets can be exported, imported, and reset.

## Archive contents

- `software/index.html` - self-contained browser application
- `docs/` - limitations, parameter-optimization guidance, reproducibility instructions, mock-bridge scope, and release notes
- `data/` - synthetic example, the aggregate Lake Biwa class-summary table used for Figure 4, derived accounting tables, and the full-length validation mzML (7,680 MS1 spectra) with validation and timing notes
- `scripts/` - the licensed-NIST production bridge and result parser, the offline mock bridge, mzML validation, statistics reproduction, figure generation, browser validation, parameter and literature-rule extraction, and checksum verification
- `provenance/` - analysis, conversion, NIST, AI-use, and run-record templates plus machine-readable literature rules and sources
- `tests/` - compact reproducibility checks, the production-bridge HTTP contract test, exported-candidate invariants I1-I6, and numerical deconvolution tests D1-D6
- `CHECKSUMS.sha256` - archive-relative SHA-256 manifest verified by `scripts/run_checks.py`

## Reproduce the public statistics and Figure 4

```bash
python -m pip install -r requirements.txt
python scripts/reproduce_lake_biwa_statistics.py   --class-summary-csv data/application/17B_class_summary_percent.csv   --outdir reproduced
python scripts/generate_figures.py   --outdir reproduced/figures   --class-summary data/application/17B_class_summary_percent.csv
python scripts/run_checks.py --require-browser
```

Figure 4 uses only literature-classified records. Thermal-desorption runs are displayed as TD L1-L5, followed by pyrolysis runs as Py L1-L5. Unclassified records are retained in the accounting table but excluded from the compositional denominator because they can include unresolved signals, low-confidence spectra, analytical background, contaminants, and possible siloxane bleed.

## Numerical deconvolution verification

`tests/test_deconvolution_numeric.py` constructs a three-component chromatogram with known spectra and drives the released application over it. The archived assertions include exact apex recovery, isolated-spectrum cosine 1.000, separation of an overlapping pair, no background-only component, and the documented exclusion of an ion shared by both overlapping components at the default correlation threshold. This is a synthetic arithmetic check, not a claim of real-sample identification performance.

## Literature rules and performance note

The 120 embedded literature classification records and 23 source records are exported in machine-readable form under `provenance/` and checked against the application by `scripts/extract_literature_rules.py --check`. Full-length single-run timings are retained in `data/validation/PERFORMANCE_NOTE.md`; because the original run lacks hardware and browser-build metadata, they are diagnostic values rather than a portable benchmark.

## Input and licensing boundary

The public release is mzML-only. It contains the localhost bridge code needed to communicate with a user-supplied licensed NIST installation, but it contains no vendor-native reader, vendor SDK, proprietary raw-data specification, private conversion code, NIST executable, NIST library, protected spectrum collection, licence key, or API credential. Users are responsible for lawful access to conversion and search software and for verifying the conversion route used for their data.

## Maintenance

This is an archived research release associated with a SoftwareX manuscript. Active feature development and continuous support are not planned. Critical corrections affecting reproducibility may be released if necessary.

## Acknowledgements and funding

We thank Dr. Kazuhide Hayakawa (Lake Biwa Environmental Research Institute, Shiga, Japan) for his
participation in sediment sample collection. This work was supported by JSPS KAKENHI Grant Number
JP25K03248.

## Source code and archive

- Source code: https://github.com/Yasuro3/pygcms-pipeline
- Permanent archive (this version): [10.5281/zenodo.21369547](https://doi.org/10.5281/zenodo.21369547)

The Zenodo record is the citable archive and includes the full-length validation mzML. Cite the
version-specific DOI rather than the concept DOI, so that the exact artefact can be retrieved.

## Citation

Cite the version-specific Zenodo DOI for the software, and the associated SoftwareX article:

> Fuse, Y., Okuda, H., & Chu, X. (2026). PyGCMS Pipeline (v1.3.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21369547

Use the version-specific DOI rather than the concept DOI, so that the exact artefact can be retrieved.
