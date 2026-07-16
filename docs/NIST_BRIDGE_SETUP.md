# Licensed NIST MS Search bridge

## Scope and licensing boundary

PyGCMS Pipeline can submit reconstructed component spectra to a **locally installed,
separately licensed** copy of NIST MS Search on Windows. The archive provides only
the localhost bridge and launch/diagnostic scripts. It does **not** contain a NIST
executable, library, reference spectrum, licence key, or NIST-derived spectral index.

The production bridge:

1. receives user-generated MSP spectra from `software/index.html`;
2. invokes the user's local `NISTMS$.EXE` through its file-automation route;
3. parses the resulting `SRCRESLT.TXT`; and
4. returns candidate names, ranks, MF/RMF, probability and related identifiers to
   the browser application.

The server binds to `127.0.0.1` by default. Do not expose it to an external network.

## Requirements

- Windows 10 or 11
- Python 3.9 or later
- a legitimately licensed local NIST MS Search installation
- at least one licensed search library selected in NIST MS Search

The standard file-automation backend uses only the Python standard library. The
optional DLL backend in `scripts/nist_dll_backend.py` is not required.

## Configure the NIST executable path

1. Copy `nistms_path.example.txt` to `nistms_path.txt`.
2. Replace the example with the full path to the installed `NISTMS$.EXE`, for
   example:

   ```text
   C:\NIST20\MSSEARCH\NISTMS$.EXE
   ```

`nistms_path.txt` is intentionally excluded from version control because it is a
machine-specific path.

## Configure NIST MS Search

In NIST MS Search, open:

```text
Options > Library Search Options > Automation
```

Then:

1. enable Automation;
2. set **Number of hits to print** to the same value as the candidate count in
   PyGCMS Pipeline, or higher;
3. select at least one licensed library; and
4. leave NIST MS Search running while a batch is searched.

## Start the application and production bridge

Run:

```text
00_START_EN.cmd
```

This starts `scripts/nist_mssearch_bridge_server.py` on
`http://127.0.0.1:18789`, waits for its health endpoint, and opens the released
application at `http://127.0.0.1:18789/app`.

The same server can be started manually:

```bash
python scripts/nist_mssearch_bridge_server.py \
  --nistms "C:\NIST20\MSSEARCH\NISTMS$.EXE" \
  --port 18789 \
  --workdir bridge_work
```

In the application, press **Check bridge** before running the licensed search.

## Diagnostics

- `02_CHECK_BRIDGE.cmd` - open bridge and NIST-path status
- `04_LAUNCH_NIST.cmd` - start NIST MS Search only
- `05_NIST_BACKGROUND_SELFTEST.cmd` - submit a tiny test spectrum through the
  NIST automation route
- `06_NIST_DOCTOR.cmd` - report executable, work-directory and result-file paths
- `07_NIST_PROBE.cmd` - test supported NIST command-switch combinations
- `03_STOP_BRIDGE.cmd` - stop the localhost bridge

If the bridge is connected but `SRCREADY.TXT` or `SRCRESLT.TXT` is not produced,
confirm that Automation is enabled, the printed-hit count is greater than zero,
a licensed library is selected, and the NIST work directory is writable.

## Production bridge versus mock bridge

`scripts/nist_mssearch_bridge_server.py` is the production bridge for a licensed
NIST installation. `scripts/mock_nist_bridge.py` is a licence-free test double
that returns clearly labelled synthetic candidates. The mock verifies candidate
handling and export invariants; it does not validate NIST match factors or
compound identifications. See `docs/MOCK_BRIDGE.md`.

## Verification included in this archive

`tests/test_nist_bridge_contract.py` checks the production bridge's public HTTP
contract, candidate-count propagation and result parser without launching NIST.
A real NIST search cannot be executed on a machine that lacks the licensed
software and libraries; users with a licence should run
`05_NIST_BACKGROUND_SELFTEST.cmd` and retain the resulting local log with their
run provenance.
