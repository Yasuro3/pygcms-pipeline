# Identification QC v1.0.0 in PyGCMS Pipeline 1.4.0

## Not a new measurement or identity confirmation

The input is an archived selected candidate per detected component. No mass-spectral
signal, original rank, score or candidate list is rescaled or overwritten. No external
AI call is made during the new QC pass. Missing MF, ion counts or RT are not generated.

## Three separate decisions

**Eligibility:** minimum selected-candidate MF, retained-ion count and within-run
relative response must hold on the same component record. A good occurrence in one
sample does not promote low-quality occurrences in other samples into the frequency.

**Classification:** structure/formula corrections apply to all rows, including excluded
rows, for an auditable transition record. Numerical reporting uses passing records only.

**Name specificity:** flags can downgrade an exact name even when the numeric thresholds
pass. Repeated names and MF999 do not certify molecular identity. The software currently
has no automatic authentic-standard confirmation path in the saved-CSV QC layer.

## Principal flags

- INSUFFICIENT_ION_COUNT / ION_COUNT_NOT_RECORDED: no precise-name reporting.
- LOW_MF / MF_NOT_RECORDED: selected candidate below the recorded reporting threshold.
- LOW_RELATIVE_RESPONSE: record preserved but not in the screened catalogue.
- MULTIPLE_RT_BANDS: one candidate key spans disconnected RT groups; inspect the
  characteristic ions/retention index. The engine does not align chromatograms.
- SAME_FORMULA_NEAR_RT: candidate labels are nearby under one method/window.
  They remain separate IDs, and this is a review cue, not a proof of identity.
- NEAR_TIE_UNIQUE_CANDIDATES: similar scores after grouping duplicate CAS/name keys.
- IDENTIFIER_FORMULA_CONFLICT: exact-name/CAS rule and recorded formula disagree.
- Halogen/metal composition without suitable author-reviewed evidence: withhold a
  detailed name rather than erase the signal or claim anthropogenic compounds absent.
- RT_METHOD_UNSPECIFIED: diagnostic cross-run comparison lacks explicit method metadata.

Actual flag strings are exported; the canonical definitions are in software/qc140.js.

## Relative response and coverage

R_i (%) = 100 S_i / sum(S_j) within the same run, where the sum includes positive
records surviving the selected pre-existing exclusion profile before new QC thresholds.
S_i is the exported sum of deconvoluted ion intensities, not time-integrated peak area.
Raw and mass-normalized coverage are not interchangeable. Overall coverage does not
imply every run exceeds 90%; a warning is reported, without relaxing the thresholds.

## Frequency identities and denominators

A checksum-valid CAS forms the candidate key; otherwise normalized name plus formula
forms the key. Formula alone never merges candidates. Contradictory formulas sharing
a CAS are flagged, not corrected by choosing a convenient formula. The catalogue
counts annotation keys, not independently confirmed molecular species.

Each passing record contributes once to its class response. Repeated records of the
same key in one run count once for frequency. TD/PY phase assignments and pair IDs
come from the manifest, explicit input metadata, or documented filename inference.
Either excludes ambiguous/incomplete pairs and reports its actual paired denominator.
Zero-component runs are explicit. Importing duplicate component IDs is an error.

## Verification and extensibility

Synthetic tests cover normal records, one-ion MF999, zeros, missing fields, duplicate
inputs, repeated candidates, same-formula/RT alternatives, multiband candidates,
non-aromatic corrections, immutable raw fields, class-sum closure and browser ZIP output.
The supplied CLI and browser execute the same engine. Different external name/structure
parsers or calibrated RI tolerances are not silently substituted.

Adding future authenticated structural evidence should use a separately versioned
rule set and preserve both the earlier result and new evidence. Do not tune rules to
obtain a particular catalogue count or improve a paper's environmental trend.


## Reprocessing a v1.4.0 export / v1.4.0出力の再処理

Do not import a `QC140_*` audit back over itself. For a newly analyzed sample,
use **Component-source CSV** to save a reprocessable snapshot without appended QC
columns. This preserves previous QC outputs rather than overwriting their history.
`QC140_*`列付きの結果は再入力で上書きしません。新規測定の再処理用には、
**Component-source CSV**を保存してください。コマンドではファイルを直接指定するか、
`--pattern "*_component_source.csv"`を指定します。

For the identity-conservative view, any exact-name-withheld occurrence or conflicting
report-group assignment makes the entire candidate key R across the loaded batch.
This keeps the catalogue class and every contributing summary row consistent.
The candidate-conditional view remains separate and does not apply this propagation.
This is a deliberately conservative sensitivity view, not proof all those signals are false.
