# Release notes - v1.3.2

Peer-review revision of v1.3.0.

## v1.3.2 sulfur-class extension (classification model 2.1.0)

- Added **S — sulfur-containing / sulfurization-associated products** to the application layer, giving L/P/C/F/S/O.
- Thiophenes, alkylthiophenes, benzothiophenes, dibenzothiophenes, reduced-sulfur compounds and mixed N/S heterocycles are no longer folded into P solely because they contain S.
- Formula fallback now routes S-bearing formulas to S and N-only formulas to P; N+S formulas remain S for sulfur accounting and carry a mixed-N/S warning.
- Added literature provenance for sulfur-containing pyrolysis products, early-diagenetic sulfur uptake, laboratory sulfurization of carbohydrates, and the known elemental-sulfur pyrolysis artifact caveat.
- The archived five-class Lake Biwa Figure 4 is not retrospectively recalculated; new analyses can report the separate S fraction.
- Deconvolution, NIST candidate preservation, match scores, and raw candidate ranks are unchanged.


## Corrections

- The quick-start mzML now yields three components at defaults and is tested end-to-end.
- Manual candidate selection is idempotent; static licensed-NIST text is no longer appended to mutable candidate fields.
- Python cache files are excluded from the archive and checksum manifest.
- All distributed version strings are synchronized to 1.3.2.

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
- Clarified that the six NOM / diagenetic groups are application-specific and the nine-class scheme is separate.
- Added accepted-ion distribution and profile-sensitivity summaries.
- Added browser tests for the public example and candidate-selection regression.

## Full-length validation summary

The 7,680-scan validation mzML still gives 450 default components and 6,706 reconstructed ions, with zero differences from the archived reference. At the v1.3.2 three-ion automatic-search gate, 340 components are eligible; 63 contain one ion and 47 contain two ions and remain retained but are not automatically submitted. The permissive and selective presets give 543 and 278 components, respectively. Matched-apex spectrum comparisons are archived under `data/validation/profile_sensitivity/`; they describe extraction sensitivity, not NIST identification accuracy.

## Inherited v1.3.1 classification foundation (model 2.0.0)

- v1.3.1 introduced the final classification writer from the tested v1.4.1 branch; v1.3.2 retains that foundation and extends it with the S class in model 2.1.0.
- Added the `EXACT_TOLUENE` invariant for toluene aliases and CAS 108-88-3; final category L, structural class `Aromatic hydrocarbons`, confidence C, locked.
- Prevented C/H-only and non-N aromatic hydrocarbons from being assigned to the protein/microbial group by a late matrix-specific rule.
- Added final rule, confidence, interpretation, warning, source, lock and classification-model fields to component and candidate exports.
- Added a long-format candidate-audit CSV and regression tests for direct, imported, selected and exported classifications.
- Kept exact toluene out of the Lake Biwa Figure 4 environmental-composition denominator because it was the solvent for the internal standard; the audit record still classifies it as L.
