# Browser-level component validation

**Status:** PASS

The strengthened public mzML reader reproduced the previously validated default output within the stated numerical tolerance. The earlier private reference comparison established scientific equivalence between the vendor-native route and mzML for the deposited file.

- Scans: 7,680
- Retention-time range: 2.0000-33.9958 min
- Default components: 450
- Current-vs-validated output mismatches: 0
- Private-reference-vs-public-mzML scientific mismatches: 0
- Diagnostic raw-ion-count differences from excluded m/z 0 bins: 2

## Adjustable parameter profiles

| Profile | Cutoff (%BP) | Half-window | Correlation | Bleed filter | Components |
|---|---:|---:|---:|---|---:|
| Permissive | 0.5 | 4 | 0.70 | Off | 543 |
| Archived default | 1.0 | 6 | 0.85 | On | 450 |
| Selective | 2.0 | 6 | 0.95 | On | 278 |

The counts demonstrate that the controls are active; they do not define a universal optimum.
