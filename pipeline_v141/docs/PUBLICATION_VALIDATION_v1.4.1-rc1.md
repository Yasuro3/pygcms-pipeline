# Publication validation: v1.4.1-rc1

Date: 2026-10-23. Status: experimental prerelease.

## Source and changes

This release uses the GitHub-upload source archive prepared on 2026-10-22, SHA-256 `5b66877686fd458613745c932f2f5ac2271c18357e1ddb42233e28c02d7c24bc`.

Publication changes correct the two current citation records, launcher/documentation paths, historical validation wording, response-scale labels in the QC adapter, and the Windows test launcher. They regenerate stale documentation checksums. The Global NNLS calculation and the 18 pinned v1.4.0 runtime files remain unchanged.

## Checks actually rerun

Environment: Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0.

From `pipeline_v141/`:

```bash
python engine/test_global.py
python engine/test_nist_contract.py
```

- Global numerical tests: PASS. Partially coeluting synthetic components, reconstruction/closure, deliberate overprediction, and duplicate/retention separation cases passed.
- NIST query-result contract tests: PASS. Out-of-order results are keyed correctly; unknown and duplicate identities are rejected.
- All 18 upstream runtime files: SHA-256, size and Git blob hashes agree with `UPSTREAM_MANIFEST.json` and the pinned public v1.4.0 commit `7d7ab77cef342cf5061eb87c412126789f152a3f`.
- All 12 distributed Python files parse successfully.
- Publication checksum manifests are regenerated after the documentation changes and checked before uploading.

`08_TESTS.cmd` now runs both numerical and contract tests, then validates generated NIST inputs if present.

## Scope

This source archive contains no study QGD/MSP files or licensed NIST program/library. The historical 40-run QGD analysis, Windows NIST Automation, and authentic AMDIS benchmark were not rerun during this publication check. Their dated prior records remain separately identified. Passing numerical and contract checks does not establish chemical separation accuracy.

The 2026-10-22 four-run AMDIS comparison remains exploratory. Historical model overprediction remains a limitation; see `VALIDATION_v141.md` and `AMDIS_COMPARISON_2026-10-22_JA.md`.

The exact release is `1.4.1-rc1`; `software_version: "1.4.1"` remains the compatible input-format/engine-series identifier. Cite the GitHub tag or commit and the SoftwareX article. No software Zenodo DOI is assigned by this publication.
