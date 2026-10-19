# Classification model 2.2.0 and reporting model JAAP-7-v1.0.0

PyGCMS Pipeline 1.4.0 retains the prior candidate archive and native six-category UI.
The final writer now applies model 2.2.0 after the inherited 2.1.0 annotation logic.
Saved input columns are never replaced during CSV reprocessing. Fresh native candidate
objects store their originalClassification210 alongside their corrected final fields.
Manual or model-assisted re-selection recomputes the final classification.

## Distinct layers

1. Original NIST candidate name, formula, rank, MF/RMF, CAS and library remain evidence.
2. Native L/P/C/F/S/O is a broad operational marker partition.
3. Structural classes describe product structure; nitriles/amides are not hydrocarbons,
   and cyclopentenones are carbonyls rather than furans.
4. The seven report groups A/OAr/C/N/F/S/R use the corrected writer and explicit
   formula guards. They do not correspond to seven mutually exclusive biological sources.
5. Identification QC controls reporting eligibility and name specificity independently.

## Priority and corrections

Exact name/CAS corrections are listed in `provenance/classification_corrections_2_2_0.json`.
An available contradictory formula sends the assignment to unresolved R; the formula
is not silently edited. Toluene aliases/CAS retain L / aromatic-hydrocarbon status
unless their identifiers contradict each other. JAAP's solvent exclusion is a separate
reporting setting, not a structural classification of toluene as non-aromatic.

Sulfur has priority over N in the mutually exclusive report. Independent formula flags
remain available conceptually; this is not total-N quantification. Specified long-chain
nitriles and amides remain in the broad F marker group but receive the proper structural
class. Named cyclopentenones retain the C precursor convention with carbonyl structure.

Formula-only low H/C or low O/C cannot establish an aromatic ring. Such unsupported
aromatic assignments are put in R. A low DBE can contradict some asserted aromatic
classes, but a high DBE is never used alone to prove aromaticity. Exact corrections
cover the diagnosed non-aromatic examples rather than claiming a universal name-to-
structure parser. Other inherited name-based annotations remain tentative.

## One computation, two explicit summaries

The corrected-candidate-conditional summary uses the new group for passing records.
The identity-conservative summary moves exact-name-withheld records to R, not out of
the response balance. Both outputs include all seven groups and identify their mode.
No small RSD or desired station/depth trend is used in assigning a class.

The native six-group GUI summary is a legacy preview, not the screened report.
Use the v1.4.0 QC outputs for quantitative comparisons under the stated settings.

## Chemical references

The inherited literature database and original source IDs remain intact. Specific
non-aromatic structure checks can be independently inspected in the NIST Chemistry
WebBook records for CAS 592-57-4, 628-41-1, 4505-38-8 and 123-91-1.
These public structure records support a rule conditional on a name, not confirmation
that a chromatographic signal is that compound. NIST references are links only;
licensed EI reference spectra are not bundled.

- https://webbook.nist.gov/cgi/cbook.cgi?ID=C592574
- https://webbook.nist.gov/cgi/cbook.cgi?ID=C628411
- https://webbook.nist.gov/cgi/cbook.cgi?ID=C4505388
- https://webbook.nist.gov/cgi/cbook.cgi?ID=C123911
- Sumner et al. (2007), https://doi.org/10.1007/s11306-007-0082-2

See `docs/IDENTIFICATION_QC_V140.md` for reporting rules and limitations.
