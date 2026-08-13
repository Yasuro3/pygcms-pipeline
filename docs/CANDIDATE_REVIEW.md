# Candidate review and reselection

The candidate-review stages are deliberately non-destructive.

1. **Immutable NIST snapshot** - every returned hit is stored with original rank, MF, RMF, probability, CAS, library, identifier and RI.
2. **Deterministic QC (optional)** - flags sparse spectra, low scores, likely analytical background, formula concerns, diagnostic-ion issues, RI disagreement, and literature-rule context.
3. **External-model advice (optional)** - may recommend one of the supplied candidates or unassigned. It cannot introduce a new library hit or change original scores.
4. **Human disposition** - a user may select an alternative candidate or leave the component unassigned. Manual selection metadata are stored separately; imported candidate text is not edited.
5. **Final classification writer (model 2.0.0)** - recomputes the optional operational class from the finally selected candidate, applies exact-name/CAS invariants last, records rule/confidence/warning/lock fields, and cannot alter the immutable NIST snapshot. Optional model advice cannot overwrite a locked final class.

The five NOM marker groups and the nine structural-product groups are optional application annotations. They do not affect deconvolution or the immutable NIST hit list.
