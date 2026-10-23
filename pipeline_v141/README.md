> **Public mzML-only experimental release (v1.4.1-rc2).** The text below is historical background for v1.4.1-rc1; vendor-native QGD functionality is not part of this release. The current entrypoints accept XML mzML only. See MZML_ONLY_RELEASE.md.

# PyGCMS Pipeline 1.4.1 RC — experimental globally coupled NNLS

This is the Python/Windows batch entrypoint for a **non-production, experimental** global NNLS GC-MS deconvolution pipeline. It is compatible with the released v1.4.0 NIST MS Search bridge and v1.4.0 identification/classification engine, **which remain unmodified and identifiable by their SHA256 / Git blob checksums**.

The existing v1.4.0 HTML application is intentionally **not relabelled** as v1.4.1; its browser deconvolution is the old local TIC-apex method. Start `START_v141_GUI.cmd` or `01_DECONVOLVE_QGD.cmd` to use the new engine.

## Usage

Windows / Python 3.10+ / numpy + scipy:

1. `00_INSTALL_DEPENDENCIES.cmd` (first time).
2. `START_v141_GUI.cmd`; choose QGD ZIP/directory and optional SHA256-keyed run manifest; start raw-data deconvolution.
3. `02_VERIFY_NIST_INPUTS.cmd`; check version/identity/immutability.
4. `03_CONFIGURE_NIST.cmd`; in the licensed NIST MS Search program, enable Automation, choose libraries and set printed hits >=15.
5. `04_RUN_ALL_NIST.cmd` for all GC runs; `05_RUN_FA_ONLY_NIST.cmd` for manifest-identified FA samples.
6. `06_RESUME_ALL_AFTER_IDLE.cmd` after a verified NIST idle state; `07_REBUILD_NIST_CSV_QC.cmd` for saved candidates and official v1.4.0 QC browser HTML.

Command line example:

```bash
python engine/batch_v141.py --input example_raw.zip --manifest manifest.csv --output nist_search
python nist_search/scripts/run_mssearch_v141.py --validate-only
# Licensed MS Search searches require Windows:
python nist_search/scripts/run_mssearch_v141.py --setup
python nist_search/scripts/run_mssearch_v141.py --scope all
```

Run inputs must be new; previous search checkpoints MUST NOT be mixed with a different deconvolution / MSP query list. The program refuses to overwrite existing run inputs or validated checkpoints.

## Algorithm and evidence

Per-ion baseline and noise estimation; EIC extrema; mass-wise nonnegative globally shared spectral/time-profile fit; strict duplicate-shape merging; residual seed pass; global refit. The allocated EI response area for each component is capped **jointly** at the raw measured scan × m/z value, preventing overlap in allocated counts. Record unassigned residual area and overprediction independently. This is inspired by AMDIS principles, **not the proprietary NIST AMDIS code or a claim of mathematical equivalence**.

Signal conservation is an accounting invariant only: it cannot prove that peak boundaries, coeluting isomers, identities, or raw-to-baseline allocations are chemically correct. A four-run exploratory comparison with authentic NIST AMDIS is documented in `docs/AMDIS_COMPARISON_2026-10-22_JA.md`. Comprehensive benchmarking, standards/RI checks, and independent GCMSsolution comparisons are still required.

MS library matches are candidate annotations, not definitive compound identities. The current classification/QC engine remains v1.4.0 (classification 2.2.0, identification QC 1.0.0). Its MF 800 criterion is conservative; MF 700 may be explored via the QC UI but does not validate separated spectra.

## Validation performed during package assembly

- Synthetic partially coeluting three-component NNLS fit, deliberate 2x overprediction, and near-identical duplicate retention tests.
- Real original QGD integration test on 2004 FA SS/TD and blank: 1364 candidate components, 1363 MSP spectra, full NIST bridge query identity verification; no licensed NIST execution in this environment.
- Input archive inspection: 40 original QGD mapped by SHA256 manifest into 29 GC + 11 EGA acquisitions. EGA is summarized as TIC only.

`README_FIRST_JA.md` contains the Japanese Windows procedure. Do not publish sample raw files or licensed NIST libraries with this code.

Repository: https://github.com/Yasuro3/pygcms-pipeline. Citation metadata: `CITATION.cff` (release `1.4.1-rc1`, dated 2026-10-23). License: MIT.


## Classification and subsequent validation addenda

The native classification/QC engine is **unchanged** from v1.4.0 (`classification 2.2.0`, `QC 1.0.0`). The tables in `docs/CLASSIFICATION_REFERENCE_v141_JA.md` describe provisional FA-specific candidate annotations; they are NOT new production classification rules. F denotes *Aliphatic / lipid-related*, not fatty acids alone. For later authentic AMDIS comparison, see `docs/AMDIS_COMPARISON_2026-10-22_JA.md`.

## Exact release and input-format version

The release identifier is **1.4.1-rc1**. The generated `software_version: "1.4.1"` is the compatible input-format/engine-series identifier expected by the NIST adapter; it does not claim stable-release validation. Record the exact GitHub tag or commit alongside input/settings hashes. See `docs/PUBLICATION_VALIDATION_v1.4.1-rc1.md` for the checks rerun for this publication.
