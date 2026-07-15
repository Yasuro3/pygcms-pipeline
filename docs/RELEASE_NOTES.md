# Release notes - v1.3.0

- Added `scripts/mock_nist_bridge.py`, an offline test double of the licensed-search bridge. It
  re-implements the bridge interface contract and returns synthetic candidates from a fictitious
  library (`MOCKLIB-SYNTHETIC-1.0`), so the complete workflow from mzML through deconvolution,
  candidate import, deterministic review, and candidate-preserving export can be executed with no
  NIST software, no NIST library, no NIST spectrum, and no vendor-native file.
- The mock verifies software behaviour only. Match-factor accuracy and compound identification are
  outside its scope and are not claimed. Every mock hit is labelled as synthetic and every response
  carries a banner, so exports made against the mock cannot be mistaken for analytical results.
- Added an adversarial fixture (`--mode adversarial`) engineered so that a lossy implementation
  fails: a near-tie at ranks 1 and 2 (MF 912 vs 909), a rank-1/rank-2 pair in different
  natural-organic-matter classes, an all-weak component that must remain unassigned, a zero-hit
  component that must be retained as unidentified, records with absent CAS and formula, a repeated
  name at consecutive ranks, and a 20-candidate list truncated to the selected top-N.
- Added `tests/test_mock_bridge_contract.py` (no browser required) and
  `tests/test_candidate_preservation.py` (Playwright), which drive the released application against
  the adversarial fixture and assert invariants I1-I6: all candidates preserved, original ranks
  preserved, match factor / reverse match factor / probability / CAS / library preserved, selection
  never removes alternatives, all-weak components may remain unassigned, and zero-hit components are
  retained without fabricated candidates.
- `scripts/run_checks.py` now executes the candidate-preservation checks. The Playwright test skips
  with a clear message when Playwright or Chromium is unavailable, so the suite remains runnable on a
  bare Python installation.
- Added `docs/MOCK_BRIDGE.md` documenting the scope, the epistemic boundary, and the limits of the mock.
- Removed absolute local paths from `data/derived/reproduced_statistics.json` and the full-length
  mzML structure report; provenance records now use archive-relative paths.

# Release notes - v1.2.0

- Public input restricted to mzML; no vendor-native parser or conversion code is distributed.
- Configurable nominal-mass chromatographic deconvolution documented in the interface, manuscript, and Supplementary Information.
- Adjustable controls now include minimum retention time, TIC height, peak separation, half-window, shape correlation, ion cutoff, ion-apex intensity, trace-intensity threshold, sharpness threshold, model-ion fraction, maximum model ions, and common-bleed exclusion.
- Added **Export settings**, **Import settings**, and **Reset defaults** controls.
- Parameter presets use schema `PyGCMS-deconvolution-parameters-v1` and can be applied across comparative batches.
- Current parameter values are exported to JSON and repeated in component-result CSV columns.
- Top-N candidate preservation, decision rationale, and provenance records retained.
- Optional external-model review separated from deterministic local QC.
- Lake Biwa Figure 4 is normalized only to literature-classified records and is ordered TD L1-L5 followed by Py L1-L5. Unclassified signals remain in audit tables but are excluded from class-composition axes to avoid treating siloxanes, background, contaminants, or unsupported assignments as natural-organic-matter classes.
- Deterministic figure-generation script and classified-only source table included; generated publication artwork is submitted separately to the journal.
- Fixed Zenodo-oriented research release; active feature development is not planned.
