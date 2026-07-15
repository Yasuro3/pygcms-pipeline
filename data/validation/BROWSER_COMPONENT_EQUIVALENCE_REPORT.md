# Browser-level component validation

**Status:** PASS

The public mzML reader reproduced the archived default output within the stated
numerical tolerance. The earlier private-reference comparison found no
scientific component differences between the vendor-native and public mzML
routes for the deposited validation file.

- Scans: 7,680
- Retention-time range: 2.0000-33.9958 min
- Default components: 450
- Current-vs-validated output mismatches: 0
- Private-reference-vs-public-mzML scientific mismatches: 0
- Maximum reconstructed-intensity difference: 0.00390625
- Diagnostic raw-ion-count differences from excluded m/z 0 bins: 2

## Adjustable parameter profiles

| Profile | Cutoff (%BP) | Half-window | Correlation | Bleed filter | Components | Accepted ions |
|---|---:|---:|---:|---|---:|---:|
| Permissive | 0.5 | 4 | 0.70 | Off | 543 | 19,923 |
| Archived default | 1.0 | 6 | 0.85 | On | 450 | 6,706 |
| Selective | 2.0 | 6 | 0.95 | On | 278 | 3,144 |

The counts demonstrate that the controls are active; they do not define a
universal optimum.

## Single-run diagnostic timings

| Profile | mzML load (s) | Deconvolution (s) |
|---|---:|---:|
| Archived default | 3.254 | 1.462 |
| Permissive | 2.468 | 1.088 |
| Selective | 2.537 | 1.095 |

The original run did not record hardware or browser-build metadata. These are
therefore diagnostic timings, not a cross-system performance benchmark. See
`PERFORMANCE_NOTE.md`.
