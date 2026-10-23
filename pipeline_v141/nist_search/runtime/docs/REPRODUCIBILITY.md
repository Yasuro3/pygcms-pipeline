# Reproducibility

## Minimal workflow

1. Record the raw input format and, when mzML is used, the authorized conversion route in `provenance/data_conversion_record.yaml`.
2. For mzML, validate with `scripts/validate_mzml_structure.py`. For direct Shimadzu QGD, run `scripts/validate_shimadzu_qgd_browser.py --qgd <file.qgd>` and record the detected channels, selected channel, scan count, retention-time range, and TIC-integrity result. Compare representative TIC/spectra with GCMSsolution when establishing a new QGD variant.
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
# or set PYGCMS_CHROMIUM to a system Chromium executable
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


## Direct Shimadzu QGD validation

For an additional QGD file or a different GCMSsolution version, run:

```bash
python scripts/validate_shimadzu_qgd_browser.py --qgd path/to/sample.qgd
```

The validator executes the same browser parser distributed in `software/index.html`, reports the native-record count, selected acquisition channel, excluded records, median point counts, m/z range, and raw-sum/TIC mismatches, and builds the nominal-mass EIC matrix. A non-zero TIC mismatch or a parser error should be treated as an unsupported/native-format variation until compared with GCMSsolution or an authorized mzML export.

## Licensed NIST bridge verification

The production bridge is distributed in `scripts/nist_mssearch_bridge_server.py`
and `scripts/nist_mssearch_bridge.py`; Windows startup and diagnostic commands
are at the archive root. `tests/test_nist_bridge_contract.py` starts the released
HTTP bridge with a stub search backend and verifies application serving, response
fields and propagation of the configured top-N candidate count. This confirms
the public interface without redistributing or launching licensed software.

A real NIST automation search can only be verified on a Windows machine with a
licensed installation and licensed libraries. On such a machine, follow
`docs/NIST_BRIDGE_SETUP.md` and run `05_NIST_BACKGROUND_SELFTEST.cmd`. Preserve
the local NIST build, library configuration, search settings and test log with
the run provenance.

## Reviewer-driven profile comparison

`data/validation/profile_sensitivity/` contains the full-length accepted-ion distribution and matched-apex spectral comparison for default, permissive, and selective presets. To compare real licensed-NIST results across those profiles, run each profile with an identical NIST build, library, and search configuration, export the three result CSV files, and use `scripts/compare_profile_nist_exports.py`. The public archive does not claim chemical-identification agreement without those licensed outputs.

## Classification reproducibility

Record both the software version and `ClassificationModelVersion`. In v1.3.2 the latter is `2.1.0`. The results CSV and candidate-audit CSV retain the final rule ID, confidence, interpretation, warning, source IDs and lock state for every selected or retained candidate. Reclassification can therefore be audited without altering original NIST ranks or scores.

## Classification model

Reproducibility requires recording both `SoftwareVersion` and `ClassificationModelVersion`. Version 1.3.2 uses classification model 2.1.0. Run `tests/test_classification_model_v2.py` or the full strict suite to verify exact-name/CAS invariants, final audit fields, and long-format candidate preservation.
