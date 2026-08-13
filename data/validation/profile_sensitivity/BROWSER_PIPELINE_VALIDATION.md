# Browser-pipeline validation

**Status:** PASS

- Spectra: 7,680
- Retention-time range: 2.0000-33.9958 min
- Default components: 450
- Permissive components: 543
- Selective components: 278

## Single-run diagnostic timings

| Profile | mzML load (s) | Deconvolution (s) |
|---|---:|---:|
| Default | 1.805 | 1.076 |
| Permissive | 1.131 | 0.793 |
| Selective | 1.135 | 0.597 |

These are single-run diagnostic timings for the recorded environment, not a cross-system benchmark.

## Reconstructed-ion count QC

Automatic NIST submission uses a non-destructive minimum of three reconstructed spectral ions in v1.3.1. Components below this threshold remain in the component export and can be included manually.

| Profile | 1 ion | 2 ions | 3-4 | 5-9 | >=10 | Eligible (>=3) |
|---|---:|---:|---:|---:|---:|---:|
| Default | 63 | 47 | 45 | 52 | 243 | 340 |
| Permissive | 1 | 0 | 2 | 4 | 536 | 542 |
| Selective | 37 | 15 | 23 | 66 | 137 | 226 |

## Parameter-profile spectral comparison

The profiles are matched by component-apex scan. Cosine statistics describe changes in reconstructed spectra; they are not library-identification accuracy measurements.

| Comparison | Shared apices | Left only | Right only | Median cosine | 10th percentile |
|---|---:|---:|---:|---:|---:|
| default vs permissive | 450 | 0 | 93 | 0.883 | 0.116 |
| default vs selective | 278 | 172 | 0 | 0.968 | 0.275 |
| permissive vs selective | 278 | 265 | 0 | 0.929 | 0.176 |

## Environment

- Recorded UTC: 2026-08-12T14:21:54.394396+00:00
- Platform: Linux-6.18.35-x86_64-with-glibc2.41
- Python: 3.13.5
- Browser: Chromium 144.0.7559.96
- Logical CPUs: 5
- Archived-reference mismatches: 0
- Maximum intensity difference: 0.0
