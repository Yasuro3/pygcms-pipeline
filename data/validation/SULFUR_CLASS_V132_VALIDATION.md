# Sulfur-class validation — PyGCMS Pipeline v1.3.2

ClassificationModelVersion 2.1.0 adds the S class without changing deconvolution or raw NIST candidate preservation. The browser regression tests verify the following deterministic cases:

- Thiophene (C4H4S) -> S / `S_ORGANOSULFUR_NAME`
- 2-Methylthiophene (C5H6S) -> S / `S_ORGANOSULFUR_NAME`
- Benzothiophene (C8H6S) -> S / `S_ORGANOSULFUR_NAME`
- Benzothiazole (C7H5NS) -> S / `S_ORGANOSULFUR_NAME`, with mixed N/S warning
- An unmatched carbon-containing sulfur formula -> S / `FORMULA_S_S`
- Pyridine remains P, furfural remains C, hexadecane remains F, and siloxane remains locked O

Run `python scripts/run_checks.py --require-browser` to reproduce these checks.
