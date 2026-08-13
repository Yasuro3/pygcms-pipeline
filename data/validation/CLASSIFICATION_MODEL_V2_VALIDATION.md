# Classification model 2.0.0 backport validation

**Software:** PyGCMS Pipeline v1.3.1  
**Classification model:** 2.0.0  
**Result:** PASS

## Scope

- downstream candidate classification and audit export
- exact-name/CAS invariants
- post-selection reclassification
- candidate preservation and non-destructive audit

## Toluene invariant

Aliases and CAS forms are classified as **L / Aromatic hydrocarbons** under `EXACT_TOLUENE`, confidence C, with the final classification locked. The warning explicitly states that toluene is a multi-origin operational marker rather than a unique source tracer.

## Browser regression cases

- **Toluene aliases/CAS**: PASS (L / EXACT_TOLUENE / locked)
- **Benzene and naphthalene**: PASS (L / L_AROMATIC_HYDROCARBON)
- **Pyridine**: PASS (P)
- **Furfural**: PASS (C)
- **Hexadecane**: PASS (F)
- **Siloxane background**: PASS (O / locked)
- **Results CSV visibility**: PASS (classification model and Final* audit fields)
- **Long candidate audit**: PASS (one row per retained candidate, original ranks preserved)

## Unchanged analytical stages

- mzML decoding
- peak detection
- deconvolution
- reconstructed spectra
- NIST query spectra
- raw NIST candidate names/ranks/scores
- Figure 4 archived structural-product aggregate

## Strict public test suite

`python scripts/run_checks.py --require-browser`

PASS: all public reproducibility checks completed; browser tests executed; 106-file SHA-256 manifest verified

## Figure 4 boundary

Figure 4 uses the archived structural-product aggregate. The origin-category P-to-L correction does not change the structural class Aromatic hydrocarbons. No numerical reconstruction from a different export was fabricated.
