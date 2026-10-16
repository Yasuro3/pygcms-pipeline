# Licensed NIST MS Search bridge: setup and recording guide

## Boundary

PyGCMS Pipeline communicates only with a user-supplied, locally licensed NIST MS Search installation on Windows. The archive contains the localhost bridge, not the NIST executable, library, spectra, licence, or keys.

## Step-by-step setup

1. **Locate NIST MS Search.** Find the full path to `NISTMS$.EXE` in the licensed installation. NIST20-era and newer installations may use different folders.
2. **Configure the path.** Copy `nistms_path.example.txt` to `nistms_path.txt`; enter one absolute executable path and save it.
3. **Open NIST MS Search once.** Confirm that the intended EI library or libraries are visible and that a manual spectrum search succeeds.
4. **Set Automation output.** Enable NIST Automation and set “number of hits to print” to at least the browser's candidate-count setting. The software cannot preserve hits that NIST did not print.
5. **Record search options.** Before analytical searching, complete `provenance/nist_configuration.yaml`: product build, library release and names, search type, preprocessing, mass range, constraints, RI use, top-N, output format, operating system, and date.
6. **Start the bridge.** Run `00_START_EN.cmd`. The terminal should report the NIST path and bridge URL.
7. **Connect the browser.** Open `software/index.html`; keep `http://127.0.0.1:18789` unless changed; press **Check connection**.
8. **Run a diagnostic.** Use `05_NIST_BACKGROUND_SELFTEST.cmd` or the synthetic quick-start workflow before an analytical batch.
9. **Run the search.** Deconvolute an mzML file, choose candidate count and minimum spectral-ion count, and press **Run NIST search**.
10. **Archive the record.** Save the results CSV, candidate columns, parameter JSON, run manifest, NIST configuration, input hash, and bridge log.

## Search-eligible spectra

Version 1.3.2 defaults to withholding reconstructed spectra with fewer than three accepted ions from automatic NIST submission. These components remain in the table and CSV with `NIST_SearchEligible=no` and an explicit reason. This prevents the software from silently treating a sparse spectrum as an identification, while preserving the measured/extracted record. The threshold is configurable, and the analyst remains responsible for judging whether a spectrum is adequate for the intended identification level.

## NIST search settings are not inferred

NIST match factors depend on library release, search type, mass range, constraints, preprocessing, and software build. The bridge imports what NIST reports; it does not reconstruct missing settings. If a historical run lacks a setting, record it as `not recorded` rather than guessing.

## NIST20, NIST23, NIST26 and MS Search versions

The interface relies on the documented text/automation exchange and preserves returned fields. Version 1.3.2 includes a regression fix for repeated candidate selection and does not append the static licensing notice to candidate text. A contract test verifies the public bridge with a stub backend. Real NIST builds must still be checked locally because licensed software is not distributed or launched by the public test suite.

## Troubleshooting

- **Bridge not connected:** check that the bridge terminal is still open, the URL/port match, and a firewall is not blocking localhost.
- **NIST path missing:** verify `nistms_path.txt`; paths containing spaces are supported when entered as one full line.
- **Fewer hits than requested:** increase NIST Automation's printed-hit count, then rerun the search.
- **0 hits:** retain the component as unidentified; do not fabricate a candidate. Use “continue on 0-hit/error” for batch completion.
- **Sparse spectrum:** inspect `PureIons` and the eligibility reason; optimize deconvolution or raise/lower the workflow threshold only with analytical justification.
- **Repeated names:** enable “group duplicate CAS in view.” Raw ranks remain in the CSV.
- **Candidate display grows after repeated clicking:** this was fixed in v1.3.2 and is covered by browser invariant I7.

## Licence-free interface verification

`tests/test_nist_bridge_contract.py` starts the real HTTP bridge with a stub search backend and verifies field mapping and top-N propagation. `scripts/mock_nist_bridge.py` verifies candidate handling with clearly synthetic data. Neither test validates licensed NIST match factors or chemical identification.
