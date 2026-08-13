# Data files

- `application/17B_class_summary_percent.csv`: aggregate ten-run Lake Biwa summary used for Figure 4.
- `derived/`: classified-composition and excluded-record accounting tables.
- `example/synthetic_gc_ms.mzML`: synthetic quick-start fixture. At v1.3.1 defaults it produces three NIST-eligible components; `tests/test_example_workflow.py` enforces this.
- `example/ri_calibration_example.csv`: retention-index documentation example.
- `validation/full_length/17B_L1_PY_full_length_validation.mzML`: full-length Py-GC/MS validation mzML (7,680 MS1 spectra).
- `validation/profile_sensitivity/`: accepted-ion distributions and spectrum-sensitivity summaries for default, permissive, and selective deconvolution profiles.

The release does not include component/candidate-level Lake Biwa application records or licensed NIST outputs. Therefore the public package can reproduce extraction/profile statistics and candidate-handling invariants, but it does not claim to reproduce chemical identification changes across NIST libraries or search configurations.

## Classification-model backport

`data/validation/classification_model_v2_validation.json` and `CLASSIFICATION_MODEL_V2_VALIDATION.md` record the browser-tested origin-classification model 2.0.0 backported into software v1.3.1. `data/application/FIGURE4_CLASSIFICATION_MODEL_NOTE.md` explains why the archived Figure 4 structural-product aggregate is retained without an unsupported reconstruction from a different export.
