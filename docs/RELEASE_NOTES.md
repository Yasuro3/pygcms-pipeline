# Release notes

## 1.4.0 — prepared 18 October 2026

New offline saved-CSV QC/reporting engine (1.0.0), classification model 2.2.0,
JAAP-7-v1.0.0, configurable screening, conservative names, RT review flags,
frequency/coverage aggregation and original-to-corrected transitions.
Raw input preservation is tested. The full existing application is included, not
only an index.html patch. Unsupported QGD formats and exact isomers are not newly
claimed to be solved.

The former render-time aliphatic/dehalogenation assignment override is no longer
allowed to replace the final classification writer. Historical code/evidence is
retained, but the v1.4.0 report does not change a fluorinated formula into an
invented non-fluorinated identity. Exact-name withholding and R are used instead.

The native results CSV keeps its prior fields with added QC columns; its schema
identifier is advanced to PyGCMS-results-v2.2. Existing scripts should select fields
by header rather than fixed column position. Native group values can intentionally
change where classification bugs were corrected. Prior release data are not rewritten.

The citation, launchers, metadata, tests and checksum manifest are updated together.
Public release/DOI issuance remains a repository owner action.

## Historical release notes (retained)

# Release notes - v1.3.2

Peer-review revision of v1.3.0.

## v1.3.2 direct Shimadzu QGD input revision

- Added direct browser-side reading of supported Shimadzu GCMSsolution `.qgd` OLE2 compound documents; no intermediate mzML conversion, vendor DLL, or COM automation is required.
- Reads native retention-time, spectrum-index, TIC, and MS raw-data streams and verifies raw ion-intensity sums against the QGD-stored TIC.
- Supports the two observed native spectrum-header layouts (20/22 and 24/26 byte encoding/count positions) and intensity encodings 1, 2, and 3.
- Detects mixed acquisition channels and automatically selects the full-scan-like channel by median spectral point count; interleaved secondary/SIM-like records are excluded from deconvolution.
- External GCMSsolution 4.53 validation specimen: 8,366 source records, 4,183 selected full-scan records, 4,183 excluded 23-ion secondary records, and 8,366/8,366 exact TIC checks; default deconvolution completed without browser errors.
- Fixed class-summary CSV generation so the S category is explicitly emitted in L/P/C/F/S/O summaries.


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
