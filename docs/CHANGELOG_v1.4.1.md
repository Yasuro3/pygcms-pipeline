# PyGCMS Pipeline 1.4.1 release candidate — 2026-10-21

- **Changed deconvolution**: add an experimental Python-based shared global NNLS fit. A local EIC candidate model and residual pass replace the v1.4.0 TIC-only apex selection for the new batch entrypoint.
- **Mass accounting**: fitted response for each scan × m/z is allocated among components without exceeding the observed baseline-corrected signal; export both overprediction and unassigned area.
- **Early retention segment**: start at the first scan, without the old default 2-minute exclusion; flag early peaks for artifact review.
- **Provenance**: QGD source SHA-256, settings checksum, stable query IDs, and immutable NIST input audit.
- **Classification / QC**: unchanged released v1.4.0 engine (class model 2.2.0 / identity QC 1.0.0), shipped with source-hash manifest; source data and previous v1.4.0 interpretation remain unchanged.
- **NIST adapter**: experimental v1.4.1 MSP index accepted, while upstream v1.4.0 bridge version/hash remains verified; no existing result checkpoints can be mixed with changed spectra.
- **Limitations**: experimental algorithm is not authentic NIST AMDIS. Area mass balance is a necessary accounting check, not a validation of spectral separation. Baseline, coelution, quantitation, and sample-specific tuning remain under validation.
