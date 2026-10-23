# PyGCMS Pipeline v1.4.1-rc2 — public mzML-only entrypoint

This release is an **experimental, non-production** Global NNLS Py-GC/MS pipeline.

## Public input format

- Accepted: XML **.mzML** (MS1 centroid or profile), folder of .mzML, or ZIP containing .mzML.
- Supported binary arrays: 32-/64-bit IEEE floats, uncompressed or zlib compressed.
- Retention times: minute, second, or hour units in mzML cvParams; converted to minutes.
- MS2 and above are ignored; MS1 spectra are binned to nominal m/z 35–550.
- Rejected: .qgd and other proprietary vendor-native files; the public v1.4.1-rc2 command-line and GUI do not import a vendor-native parser.
- MS-Numpress, incompatible encodings, malformed XML and missing required arrays fail with diagnostic errors.

## Windows

1. Extract the source ZIP and open `pipeline_v141`.
2. Run `00_INSTALL_DEPENDENCIES.cmd`.
3. Launch `START_v141_GUI.cmd`, select XML mzML/ZIP/folder, select SS, TD, PY, EGA, or GC_BLANK, then use preview and deconvolution.
4. For CLI use `01_DECONVOLVE_MZML.cmd`. To specify exact acquisition metadata for multiple runs, supply a SHA-256 based manifest.
5. After deconvolution, run `02_VERIFY_NIST_INPUTS.cmd` before licensed NIST searching.

Example:

```bat
py -3 engine\batch_v141.py --input sample_PY.mzML --phase PY --output nist_search
```

## Reproducibility and limitations

Global NNLS 0.3.1 and NIST query identity/QC contracts remain experimental. A numerical mass-closure test does not validate chromatographic peak identities. Native Shimadzu input is maintained separately for local research and is **not part of the public v1.4.1-rc2 workflow**. The v1.4.1-rc1 release tag and historic commits remain available. Historical v1.4.0 files are retained for licensed NIST/QC hash checking, not as a v1.4.1-rc2 deconvolution entrypoint.

Older tags and Git history still contain previous QGD-reader implementations. Removing them from Git history would require disruptive history rewriting and is not claimed here.

This software contains no licensed NIST libraries or private raw GC-MS files.
