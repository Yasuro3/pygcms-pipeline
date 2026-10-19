# PyGCMS Pipeline v1.3.2

PyGCMS Pipeline is a fixed, English-language research-software release for nominal-mass, MS1, full-scan GC-MS chromatograms, with development and real-data validation centered on pyrolysis GC-MS. The browser application reads either a documented mzML subset or supported Shimadzu GCMSsolution `.qgd` files directly in the browser, performs configurable chromatographic deconvolution, sends search-eligible reconstructed spectra to a separately licensed local NIST MS Search installation, and preserves the complete returned top-N candidate list with original ranks, scores, identifiers, selected status, rationale, analysis parameters, and run provenance. The QGD path uses no vendor DLL, COM object, or external conversion step.

The release does **not** call, wrap, or depend on PyMassSpec/PyMS for deconvolution. The extraction code is an independent JavaScript implementation of established chromatographic concepts. PyMassSpec/PyMS is cited in the associated manuscript only as an established programmable GC-MS framework. The release does not claim a new deconvolution theory or definitive compound identification.

> **Zenodo note for this peer-review revision:** upload this directory as version 1.3.2, then insert the new version-specific Zenodo DOI into `CITATION.cff`, this README, and the revised manuscript. The previous v1.3.0 DOI must not be presented as the v1.3.2 archive DOI.

## What changed in v1.3.2

- Added **direct Shimadzu GCMSsolution `.qgd` input** in the browser. The reader parses the OLE2/CFB container, reads retention time, spectrum index, TIC and MS raw-data streams, checks reconstructed ion sums against the file-stored TIC, maps spectra to nominal m/z, and feeds them directly into the same deconvolution path used for mzML.
- Mixed-acquisition QGD files are handled automatically: acquisition channels are detected from the native records and the channel with the largest median point count is selected as the full-scan-like channel for deconvolution. Secondary/SIM-like records are excluded from the chromatographic sequence rather than interleaved with full scans.
- Added QGD validation documentation and a browser-side validator script for testing additional GCMSsolution variants.
- Corrected the class-summary exporter so the v1.3.2 **S** category is included in class-summary CSV output.
- Added a sixth operational class, **S — sulfur-containing / sulfurization-associated products**, so sulfur-bearing pyrolysis products are no longer merged into P.
- Added explicit thiophene, benzothiophene, dibenzothiophene, reduced-S, mixed N/S and oxidized-S rules plus a sulfur-aware formula fallback.
- Added sulfur-specific literature provenance and cautions: S is a compositional/process-associated class, not a stand-alone diagnosis of anoxia or sulfate reduction, and alkylthiophenes can form during pyrolysis in the presence of elemental sulfur.
- Bumped `ClassificationModelVersion` from 2.0.0 to **2.1.0** while leaving chromatographic deconvolution and candidate preservation unchanged.

- Replaced the public quick-start mzML with a synthetic file that produces three components at the documented defaults.
- Added a configurable minimum spectral-ion count for automatic NIST submission. Low-ion components remain in the component table and CSV with an explicit search-eligibility reason.
- Added a configurable match-factor gap between the first two **unique chemical species** and a `near-tie` filter. The full raw top-N list is always retained.
- Added a CAS-based duplicate-species view. Repeated NIST entries are collapsed only on screen; their original ranks and values remain in the CSV.
- Added an optional compact ambiguity/QC CSV.
- Fixed repeated candidate selection so it is idempotent and no static NIST notice or reason text grows with repeated clicks.
- Clarified the optional classification layers. New analyses use six application-specific L/P/C/F/S/O marker groups, while the archived paper figure remains a historical five-group L/P/C/F/O aggregate; the separate nine-class structural-product summary is unchanged.
- Expanded NIST setup, NIST-search-record, retention-index, candidate-review, and walkthrough documentation.
- Added a short silent walkthrough video at `walkthrough/PyGCMS_Pipeline_v1_3_1_walkthrough.webm`.
- Added browser regression tests for the public example, candidate-text idempotence, match-gap metrics, CAS grouping, and raw-candidate preservation.
- Added public summaries of spectral-ion distributions and profile sensitivity for the full-length validation mzML.

## Quick start without a NIST licence

```bash
python -m pip install -r requirements-browser.txt
python scripts/run_checks.py --require-browser
```

1. Start the synthetic bridge in one terminal:

   ```bash
   python scripts/mock_nist_bridge.py
   ```

2. Open `software/index.html` in a Chromium-based desktop browser.
3. Keep the bridge URL at `http://127.0.0.1:18789` and press **Check connection**.
4. Load `data/example/synthetic_gc_ms.mzML`.
5. Run deconvolution with the defaults. The example is regression-tested to produce three NIST-eligible components.
6. Run the mock NIST search, inspect candidates, select an alternative if desired, and export the results CSV.

The mock verifies software behaviour, not chemistry. Every mock hit is labelled `MOCKLIB-SYNTHETIC-1.0`.

## Licensed NIST MS Search on Windows

1. Install and license NIST MS Search locally. No NIST file is included here.
2. Copy `nistms_path.example.txt` to `nistms_path.txt` and enter the full path to `NISTMS$.EXE`.
3. In NIST MS Search, enable Automation and set the number of hits printed to at least the candidate count requested by the browser.
4. Start `00_START_EN.cmd`.
5. In the browser, press **Check connection**, then **Run NIST search**.
6. Record the NIST MS Search build, library release, library names, search type/options, mass range, constraints, preprocessing, top-N, and output configuration in `provenance/nist_configuration.yaml`.

See `docs/NIST_BRIDGE_SETUP.md` for the detailed procedure and troubleshooting.

## Search eligibility, ambiguity, and repeated library entries

The default automatic-search threshold is three reconstructed spectral ions. This is a workflow QC flag, not a claim that three ions guarantee a reliable identification. Analysts may raise the threshold for their application or explicitly include low-ion components. In all cases, deconvoluted components are retained and exported.

The interface computes `MF(rank 1 unique species) - MF(rank 2 unique species)`. Species are grouped by CAS when available and otherwise by normalized name. A user-set threshold flags narrow gaps. The raw NIST hit list is never reduced: grouping and near-tie filtering are presentation/QC layers only.

## Retention index

Retention-index evidence is optional and independent of the NIST scores. The application supports documented RT-to-RI calibration using manual anchors or an n-alkane ladder and retains calculated RI, external reference RI, and their difference separately. See `docs/RETENTION_INDEX_GUIDE.md`, the in-app RI controls, and `data/example/ri_calibration_example.csv`.

## Optional review layers

The stages are deliberately separated:

1. **NIST candidate snapshot**: immutable original ranks/scores/identifiers.
2. **Deterministic QC**: optional rules for low scores, artefact names, formula plausibility, ion support, RI, and literature markers.
3. **External-model advice**: optional and constrained to the supplied candidates or an unassigned outcome.
4. **Human disposition**: final selection or unassigned result, stored separately from the raw candidate snapshot.

No review stage invents a candidate, deletes the archived alternatives, or overwrites original NIST scores.

## Direct Shimadzu GCMSsolution QGD input

Select or drop `.qgd` exactly as you would `.mzML`. No prior conversion is required for supported files. The browser reader currently uses the native streams `GCMS Raw Data/Retention Time`, `GCMS Raw Data/Spectrum Index`, `GCMS Raw Data/TIC Data`, and `GCMS Raw Data/MS Raw Data`. It supports the point encodings observed in the validated files (flags 1, 2, and 3) and both observed spectrum-header layouts (encoding/count at byte offsets 20/22 and 24/26).

For mixed acquisitions, PyGCMS Pipeline groups native records by acquisition-channel identifier and automatically selects the group with the largest median number of spectral points. This is intended to keep full-scan spectra contiguous for chromatographic deconvolution while excluding interleaved SIM/secondary records. The selected channel, channel sizes, median point counts, excluded-record count, and TIC-integrity result are printed in the browser log. A QGD containing only one channel is used as-is.

The direct reader was validated against an external GCMSsolution 4.53 QGD specimen containing 8,366 native records: two equal 4,183-record channels were detected, the 560-point-median channel was selected over the 23-point-median secondary channel, and reconstructed ion sums matched the stored TIC for 8,366/8,366 records. The external validation specimen is not redistributed in this archive. See `docs/SHIMADZU_QGD_DIRECT_INPUT.md`. Because QGD is a proprietary native format and this reader does not use an official vendor SDK, unsupported GCMSsolution/QGD variants should be verified with `scripts/validate_shimadzu_qgd_browser.py`; exporting mzML from authorized vendor software remains the fallback for a variant that is not decoded exactly.

## Conventional GC-MS scope

Nothing in the core raw-data reader, chromatographic deconvolution, candidate-preservation, or provenance model requires a pyrolysis-specific input. The software can therefore be applied to conventional nominal-mass, MS1, full-scan GC-MS profiles such as complex extracts or headspace chromatograms after dataset-specific parameter optimization. The public real-data validation and application example are Py-GC/MS datasets; performance for other matrices and chromatographic modes has not been systematically benchmarked.

## Classification layers

The current L/P/C/F/S/O groups are application-specific, literature-guided marker groups; S separately reports sulfur-containing / sulfurization-associated products. The archived Figure 4 was produced with the earlier five-group L/P/C/F/O scheme and is preserved as a historical result rather than numerically reconstructed. They are not proposed as universally accepted organic-matter classes. The separate nine-class view describes product structure more neutrally. Both layers are optional downstream annotations and are independent of deconvolution and candidate preservation.

## Archive contents

- `software/index.html`: self-contained browser application.
- `docs/`: setup, direct Shimadzu QGD input, RI, classification-layer, candidate-review, walkthrough, limitations, release-note, and reproducibility guidance.
- `data/example/`: working synthetic quick-start mzML and RI example.
- `data/validation/`: full-length validation mzML, accepted-ion distributions, and profile-sensitivity summaries.
- `scripts/`: bridge, mock, validation, statistics, comparison utilities, and checksum verification.
- `tests/`: numerical extraction, bridge contracts, public-example regression, candidate-preservation invariants I1-I8, and browser tests.
- `provenance/`: parameter, conversion, NIST, literature-rule, AI-use, and run-record templates.
- `CHECKSUMS.sha256`: archive-relative SHA-256 manifest. Python cache files are excluded.

## Reproducibility checks

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-browser.txt
playwright install chromium  # optional when a system Chromium is available
python scripts/run_checks.py --require-browser
```

Browser helpers use `PYGCMS_CHROMIUM`, system Chromium, or Playwright Chromium in that order.

## Source and citation

- Source: `https://github.com/Yasuro3/pygcms-pipeline`
- Version-specific archive: **insert the Zenodo DOI assigned to v1.3.2 after upload**.

Suggested citation after the DOI has been assigned:

> Fuse, Y., Okuda, H., & Chu, X. (2026). PyGCMS Pipeline (v1.3.2) [Software]. Zenodo. https://doi.org/[VERSION-SPECIFIC-DOI]

## Classification model 2.1.0

Software version 1.3.2 uses **ClassificationModelVersion 2.1.0**. It retains the final-writer, exact-name/CAS invariants, auditable rule/confidence/warning fields, and long-format candidate-audit design from model 2.0.0, and adds a separate S category so sulfur-bearing products are not merged into P. Chromatographic deconvolution and raw candidate preservation are unchanged.

Exact toluene aliases and CAS 108-88-3 are locked to category L and the structural class `Aromatic hydrocarbons`; they cannot be overwritten by a later literature, matrix or optional model-review step. This is an operational multi-origin group, not a unique lignin or fulvic-acid assignment. In the Lake Biwa double-shot experiment, toluene was the solvent of the added internal-standard solution and must not be interpreted as an environmental source marker. Figure 4 is an archived structural-product aggregate; the P-to-L origin-category correction does not change toluene's structural assignment as an aromatic hydrocarbon. See `docs/CLASSIFICATION_LAYERS.md` and `provenance/origin_classification_model_v2.json`.
