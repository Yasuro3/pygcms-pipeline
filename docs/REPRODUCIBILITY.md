# Reproducibility

## Minimal workflow

1. Record the authorized conversion route in `provenance/data_conversion_record.yaml`.
2. Validate the mzML with `scripts/validate_mzml_structure.py` and compare scan count, retention-time range, TIC, and representative spectra with the authorized source software.
3. Optimize deconvolution parameters on representative simple, weak, and coeluting regions; include blanks and standards when available.
4. Export the accepted preset from the application and apply the same preset to samples intended for comparison.
5. Complete `provenance/nist_configuration.yaml` for the licensed NIST installation and libraries.
6. Preserve all returned candidates before selection and export the component, candidate, parameter, and provenance records.
7. Recalculate reported counts and percentages from the deposited aggregate class-summary table.

## Public checks

Install the non-browser dependencies and run the portable checks:

```bash
python -m pip install -r requirements.txt
python scripts/run_checks.py
```

Browser-level invariant and numerical tests require Playwright Chromium. Use the
strict flag so a missing browser is reported as a failure rather than a skip:

```bash
python -m pip install -r requirements-browser.txt
playwright install chromium
python scripts/run_checks.py --require-browser
```

The check suite verifies the tests, regenerates the Lake Biwa aggregate
statistics, builds lightweight PDF versions of all four figures, validates the
full-length mzML structure, confirms that the machine-readable literature-rule
exports match the database embedded in the application, and verifies
`CHECKSUMS.sha256`. Full publication artwork is generated separately:

```bash
python scripts/generate_figures.py \
  --outdir reproduced/figures \
  --class-summary data/application/17B_class_summary_percent.csv
```

## Optional full-length browser validation

```bash
python scripts/validate_browser_pipeline.py \
  --html software/index.html \
  --mzml data/validation/full_length/17B_L1_PY_full_length_validation.mzML \
  --reference-json data/validation/browser_component_equivalence_full.json \
  --outdir browser_validation
```

By default this uses Playwright's bundled Chromium. `--chromium PATH` may be
supplied when a particular executable must be tested. New reports record the
browser and host environment together with single-run timings.
