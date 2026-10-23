# Direct Shimadzu GCMSsolution QGD input

## Purpose

PyGCMS Pipeline v1.3.2 can load supported Shimadzu GCMSsolution `.qgd` files directly in a Chromium-based browser. No intermediate mzML file, Shimadzu DLL, COM automation, or Windows-only converter is required. The decoded spectra are mapped to the same nominal-mass representation used by the mzML reader and then enter the unchanged EIC/deconvolution/NIST workflow.

## Native streams used

The reader opens the QGD OLE2/CFB container and requires:

- `GCMS Raw Data/Retention Time` — signed 32-bit milliseconds
- `GCMS Raw Data/Spectrum Index` — 32-bit offsets into the MS raw-data stream
- `GCMS Raw Data/TIC Data` — 64-bit native TIC values
- `GCMS Raw Data/MS Raw Data` — native spectrum records

Optional `File Property` metadata are read only for display/validation context.

## Spectrum records

The direct reader supports the native point encodings observed during validation:

- flag 1: 6 bytes/point; 24-bit intensity plus status byte
- flag 2: 4 bytes/point; 16-bit intensity
- flag 3: 5 bytes/point; 24-bit intensity
- stored m/z is decoded with scale 20 (`m/z = stored / 20`)

Two native header layouts are accepted. The encoding flag / point count may occur at byte offsets 20/22 (ordinary full-scan records in the validated specimen) or 24/26 (secondary records in the validated specimen). A record is accepted only when the encoding is known and the point payload fits inside the native record boundary.

## Mixed full-scan + secondary/SIM acquisitions

QGD can contain more than one acquisition channel at the same retention time. Interleaving those records as if they were consecutive full scans distorts chromatographic peak shapes. The direct importer therefore:

1. decodes native record headers;
2. groups records by the native acquisition-channel identifier;
3. calculates the median point count for each channel;
4. selects the channel with the largest median point count as the full-scan-like channel; and
5. excludes other channels from EIC construction/deconvolution.

The browser log reports every detected channel and the selected/excluded record counts. A single-channel file is used directly. This rule is intentionally simple and auditable; unusual methods with two dense channels should be independently checked before quantitative comparison.

## Integrity check

For every native record, including excluded secondary records, PyGCMS Pipeline sums the decoded raw intensities and compares the result to the QGD-native TIC entry. The number of exact matches/mismatches is printed during loading. A non-zero mismatch should be investigated rather than silently accepted.

## External validation performed for this revision

A GCMSsolution 4.53 QGD specimen supplied for development (not redistributed) produced:

- native records: 8,366
- detected channel 0: 4,183 records; median 560 points; header layout 20/22
- detected channel 1: 4,183 records; median 23 points; header layout 24/26
- automatically selected records for deconvolution: 4,183 (channel 0)
- raw-intensity/TIC exact matches: 8,366 / 8,366
- TIC mismatches: 0
- browser JavaScript errors during direct load/EIC construction: 0
- default deconvolution completed successfully: 270 components, 240 meeting the current automatic NIST minimum-ion gate in that validation run

These values validate the implementation against that specimen; they are not claimed as universal characteristics of QGD files.

## Testing another QGD variant

Use:

```bash
python scripts/validate_shimadzu_qgd_browser.py --qgd path/to/sample.qgd
```

For a GCMSsolution version or acquisition mode not previously tested, compare the reported retention-time range, TIC, and representative spectra with GCMSsolution. If the reader rejects the file or reports TIC mismatches, use an authorized mzML export rather than modifying the parser by guesswork.
