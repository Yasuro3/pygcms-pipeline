# PyGCMS Pipeline v1.4.0 — validation report

Prepared 18 October 2026. These are executed software checks, not experimental
confirmation of chemical identities.

## Automated public test suite

**PASS: all 15 test programs, including browser tests; no browser-test skips.**
The new v1.4.0 test contains **41 assertion groups**, including browser interaction
and the generated ZIP's integrity.

- Original candidate preservation, alternative-rank history and immutable scores.
- Numerical deconvolution against a synthetic ground truth.
- Existing synthetic three-component mzML workflow.
- Mock/local NIST bridge HTTP contract with a stub (not licensed NIST execution).
- Original extraction-parameter controls and search eligibility.
- Supported direct-QGD decoder with a synthetic OLE2/mixed-channel fixture.
- Sulfur rules and previous classification invariants.
- Explicit non-aromatic corrections, long-chain nitrile structural class and
  cyclopentenone/carbonyl distinction.
- MF999 single-ion rejection from the reporting table while retaining the source record.
- Immutable original values, quoted CSV parsing, duplicates/missing metadata and zero runs.
- Run frequency, paired-union frequency, response denominator and seven-group closure.
- RT/near-tie/isomer/halogen flags without invented exact identities.
- Consistent catalogue and per-record conservative classification.
- Prevent overwriting a prior QC audit by reimporting it as original input.
- Canonical JavaScript/embedded source equality, metadata, literature-rule export and checksums.

The complete log is `provenance/v140_automated_checks.log`. The independently prepared
CLI synthetic example completed with 2 runs, 10 records, 9 passing rows and 7 keys;
the user-visible CSV import and ZIP download were exercised without JavaScript errors.

## Saved Lake Biwa application outputs — separate private check

The final CLI was exercised on the 60 environmental component CSVs, selected from the
existing batch archive, without reading new instrument data or rerunning NIST.

| Check | Result |
|---|---:|
| Environmental runs | 60 |
| Original component records | 26,987 |
| Positive records surviving inherited exclusions | 20,613 |
| Passing records, MF800 / >=3 ions / >=0.001% | 6,281 |
| Distinct retained candidate-label keys | 638 |
| Complete TD/PY pairs | 30 |
| Original CSV column-name union preserved | 311 |
| Original cell-value mismatches | 0 |
| Independent candidate-frequency mismatches | 0 |
| Independent class-response-sum mismatches | 0 |

The **set of passing sample/component IDs** matched the prior MF800 audit exactly.
The original input fields were compared cell by cell with the restored audit columns;
canonical aggregate digests of those values were identical. All four diagnosed
non-aromatic old-OAr examples were assigned to R in the corrected numerical output.

These checks establish input preservation and computational consistency, not that all
638 candidate labels are correct or that every environmental interpretation is validated.
The conservative summary is deliberately stricter and can redistribute substantial
response into R; it is not interchangeable with the candidate-conditional summary.
The software package contains no private JAAP study rows or full private audit CSV.
The study outputs are provided separately to the owner.

## Scope of compatibility

The source bodies of readQGD, readRawFile, decodeSpec, buildEIC and deconvolveAt were
compared with the supplied direct-QGD v1.3.2 base and were unchanged. Function-region
hashes are recorded in `provenance/v140_core_preservation.json`.

This run used Linux, Python and installed Chromium. The Windows licence-dependent NIST
application, actual laboratory instruments and all possible vendor QGD layouts were
not executed. The old QGD reader and local bridge are retained; the synthetic tests do
not certify every vendor file. No molecular structure was authenticated with a standard
as part of this software build.

## Reproduction

```text
python -m pip install -r requirements.txt -r requirements-browser.txt
python -m playwright install chromium
python scripts/run_checks.py --require-browser
```

Run after unzipping the complete package. Merely changing CITATION or README after the
build changes their hashes: regenerate the manifest intentionally with
`python scripts/generate_checksums.py` before packaging a modified release. Do not call
a skipped browser test or a locally modified manifest a reproduced original release.
