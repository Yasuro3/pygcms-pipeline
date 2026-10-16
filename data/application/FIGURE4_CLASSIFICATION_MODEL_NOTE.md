# Figure 4 and classification model 2.0.0

The deposited `17B_class_summary_percent.csv` is the archived aggregate used to generate Figure 4 in the SoftwareX manuscript (4,510 component records; 1,896 structurally classified records). Figure 4 summarizes five **structural product assemblages**, not the final L/P/C/F/O origin-marker category.

Classification model 2.0.0 corrects the downstream origin-category writer, including the exact-toluene invariant (`L`, `Aromatic hydrocarbons`, rule `EXACT_TOLUENE`). The correction does not change toluene's structural product assignment as an aromatic hydrocarbon. In the Lake Biwa double-shot experiment, toluene was the solvent of the added internal-standard solution and must not be interpreted as an environmental source marker.

The component-level rows used to create the archived Figure 4 aggregate are not included in this SoftwareX software deposit. Therefore, the published aggregate is retained without fabricating a new component-level reconstruction from a different analysis export. The software itself now exports the final origin classification, structural class, rule ID, confidence, warning, lock status, classification-model version, and a one-row-per-candidate audit table for newly processed runs.

## v1.3.2 note

ClassificationModelVersion 2.1.0 adds a separate S category for new analyses. This archived Figure 4 table remains the previously reported five-class result and is not retrospectively redistributed without the original component-level rows.
