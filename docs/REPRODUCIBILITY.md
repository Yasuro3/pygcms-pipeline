# Reproducibility

## Minimal workflow

1. Record the authorized conversion route in `provenance/data_conversion_record.yaml`.
2. Validate the mzML with `scripts/validate_mzml_structure.py` and compare scan count, retention-time range, TIC, and representative spectra with the authorized source software.
3. Optimize deconvolution parameters on representative simple, weak, and coeluting regions; include blanks and standards when available.
4. Export the accepted preset from the application and apply the same preset to samples intended for comparison.
5. Complete `provenance/nist_configuration.yaml` for the licensed NIST installation and libraries.
6. Preserve all returned candidates before selection and export the component, candidate, parameter, and provenance records.
7. Recalculate reported counts and percentages from deposited source tables.

## Public checks

```bash
python -m pip install -r requirements.txt
python scripts/run_checks.py
```

The optional browser-level validation additionally requires Playwright and Chromium:

```bash
python -m pip install -r requirements-browser.txt
python scripts/validate_browser_pipeline.py   --html software/index.html   --mzml data/validation/full_length/17B_L1_PY_full_length_validation.mzML   --reference-json data/validation/browser_component_equivalence_full.json   --outdir browser_validation
```
