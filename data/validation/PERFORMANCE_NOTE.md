# Full-length browser timing note

The archived browser-equivalence run processed the deposited full-length mzML
(7,680 MS1 spectra; 564 nominal-mass bins) with three parameter profiles.

| Profile | mzML load (s) | Deconvolution (s) | Components | Accepted ions |
|---|---:|---:|---:|---:|
| Archived default | 3.254 | 1.462 | 450 | 6,706 |
| Permissive | 2.468 | 1.088 | 543 | 19,923 |
| Selective | 2.537 | 1.095 | 278 | 3,144 |

These values are single-run diagnostic timings retained in
`browser_component_equivalence_summary.json`. The original run did not record
processor, memory, browser build, or operating-system details, so the values
must not be interpreted as a portable performance benchmark. The updated
`scripts/validate_browser_pipeline.py` records those environment fields for
future reruns.
