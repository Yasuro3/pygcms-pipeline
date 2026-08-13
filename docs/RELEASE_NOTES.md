# Release notes - v1.3.1

Peer-review revision of v1.3.0.

## Corrections

- The quick-start mzML now yields three components at defaults and is tested end-to-end.
- Manual candidate selection is idempotent; static licensed-NIST text is no longer appended to mutable candidate fields.
- Python cache files are excluded from the archive and checksum manifest.
- All distributed version strings are synchronized to 1.3.1.

## Added QC and presentation layers

- Configurable minimum-ion threshold for automatic NIST submission; low-ion components remain exported.
- Top-two unique-species MF-gap calculation and near-tie filter.
- CAS/name-based duplicate grouping in the view with raw-ranked-hit preservation.
- Ambiguity/QC CSV export.
- Clear stage separation: immutable NIST snapshot, deterministic QC, optional external-model advice, human disposition.

## Documentation and validation

- Expanded NIST setup and search-option recording.
- Added retention-index guide and example.
- Clarified applicability to conventional full-scan nominal-mass GC-MS while limiting validation claims.
- Clarified that the five NOM groups are application-specific and the nine-class scheme is separate.
- Added accepted-ion distribution and profile-sensitivity summaries.
- Added browser tests for the public example and candidate-selection regression.

## Full-length validation summary

The 7,680-scan validation mzML still gives 450 default components and 6,706 reconstructed ions, with zero differences from the archived reference. At the v1.3.1 three-ion automatic-search gate, 340 components are eligible; 63 contain one ion and 47 contain two ions and remain retained but are not automatically submitted. The permissive and selective presets give 543 and 278 components, respectively. Matched-apex spectrum comparisons are archived under `data/validation/profile_sensitivity/`; they describe extraction sensitivity, not NIST identification accuracy.

## v1.3.1 classification-model backport (model 2.0.0)

- Backported the independently tested final classification writer from the v1.4.1 classification branch while retaining software version 1.3.1 and all reviewer-response features.
- Added the `EXACT_TOLUENE` invariant for toluene aliases and CAS 108-88-3; final category L, structural class `Aromatic hydrocarbons`, confidence C, locked.
- Prevented C/H-only and non-N aromatic hydrocarbons from being assigned to the protein/microbial group by a late matrix-specific rule.
- Added final rule, confidence, interpretation, warning, source, lock and classification-model fields to component and candidate exports.
- Added a long-format candidate-audit CSV and regression tests for direct, imported, selected and exported classifications.
- Kept exact toluene out of the Lake Biwa Figure 4 environmental-composition denominator because it was the solvent for the internal standard; the audit record still classifies it as L.
