# Classification layers and model version 2.1.0

Classification is **not** part of chromatographic deconvolution or candidate preservation. It is an optional downstream annotation layer. All raw NIST candidates, original ranks, match scores, CAS identifiers and library identifiers remain in the candidate record whether or not a final operational class is assigned.

## Software version and classification-model version

The reviewer-response release remains **PyGCMS Pipeline v1.3.2**. It retains the prior final-writer design and extends it as **ClassificationModelVersion 2.1.0** by separating sulfur-bearing products into an S class. Keeping these versions separate makes clear that chromatographic deconvolution and candidate-preservation behaviour were not replaced.

## Final-writer design

Earlier builds could allow a late matrix-specific rule to overwrite a more appropriate structural assignment. Model 2.1.0 uses one final writer after sediment-reference, literature, aliphatic and optional review layers. The final writer:

- applies exact-name/CAS invariants after all other evidence;
- prevents C/H-only and non-N aromatic hydrocarbons from being written to the protein/microbial group;
- preserves warnings where a product has several possible precursors;
- recomputes the final class after manual or model-assisted candidate selection;
- prevents optional AI/model advice from overwriting a locked final class;
- exports rule ID, confidence, interpretation, warning, source IDs, lock status and model version.

## Toluene invariant

`Toluene`, `toluene`, `Methylbenzene`, `Benzene, methyl-`, and CAS `108-88-3`/`108883` are written as:

- Category: **L**
- Category label: **Aromatic / fulvic-acid-like / lignin-derived / humic-like**
- Structural product class: **Aromatic hydrocarbons**
- Rule: **EXACT_TOLUENE**
- Confidence: **C**
- Locked: **true**

This is an operational grouping, not a unique source assignment. Toluene can also arise from charred material, proteins, petrogenic inputs or secondary pyrolysis. In the Lake Biwa double-shot experiment, exact toluene was the solvent of the added internal-standard solution and must not be interpreted as an environmental source marker. Figure 4 uses an archived structural-product aggregate, so the corrected P-to-L origin category does not change its structural assignment as `Aromatic hydrocarbons`. The component-level rows underlying the archived Figure 4 aggregate are not part of this software deposit, and no unsupported numerical reconstruction is made.

## Six NOM / diagenetic marker groups

The current L/P/C/F/S/O labels are application-specific operational marker groups. The archived Lake Biwa Figure 4 used the earlier L/P/C/F/O scheme and remains unchanged:

- **L** - aromatic, lignin/tannin-related, phenolic or humic-/fulvic-like operational markers;
- **P** - N-containing, protein/amino-acid/microbial-related operational markers;
- **C** - carbohydrate/polysaccharide-associated markers;
- **F** - lipid/fatty-acyl/aliphatic/wax-associated markers;
- **S** - sulfur-containing / sulfurization-associated products, including thiophenes and related sulfur-bearing compounds;
- **O** - secondary, ambiguous, contaminant or other retained products.

They are not a universal taxonomy or confirmed source apportionment. In particular, S is not by itself a diagnosis of anoxia, sulfate reduction, or in-situ sulfurization. The audit warning preserves the known possibility of thiophene formation during pyrolysis in the presence of elemental sulfur.

## Neutral nine-class structural-product summary

A separate view describes product structure (aliphatics, furans, N-containing aromatics, amides, O-aromatics, aromatic hydrocarbons, carbonyls, nitriles and others). It is independent of the six NOM / diagenetic marker groups.

## Export fields

Component and candidate exports include:

- `ClassificationModelVersion`
- `FinalCategory` and `FinalCategoryLabel`
- `FinalPaperClass9` and `FinalDetailedClass`
- `FinalOriginRuleID`
- `FinalOriginConfidence`
- `FinalOriginMarkerClass`
- `FinalOriginInterpretation`
- `FinalOriginWarning`
- `FinalOriginSourceIDs`
- `FinalOriginLocked`

The separate long-format candidate-audit CSV contains one row per retained candidate and retains the original candidate rank alongside these fields.
