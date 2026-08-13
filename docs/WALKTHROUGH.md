# Quick walkthrough

A silent 25-second visual walkthrough is archived at `walkthrough/PyGCMS_Pipeline_v1_3_1_walkthrough.webm`. It demonstrates loading the public quick-start mzML, recovering three components at the default settings, importing a complete synthetic top-N candidate list through the licence-free mock path, changing only the CAS-grouped/near-tie view, and exporting both the full Results CSV and the compact Ambiguity/QC CSV. The complete raw candidate rows remain preserved throughout.

## Licence-free demonstration

1. Start `python scripts/mock_nist_bridge.py`.
2. Open `software/index.html` and press **Check connection**.
3. Load `data/example/synthetic_gc_ms.mzML`.
4. Press **Run deconvolution**. Three components should be shown at the defaults.
5. Inspect `Pure`, `Search eligibility`, and the reconstructed spectrum for each component.
6. Press **Run NIST search**. The returned candidates are synthetic and visibly labelled.
7. Open a component. Toggle **group duplicate CAS in view** and adjust **MF gap** to see the presentation/QC layers.
8. Select a non-top candidate. Repeat the click; the imported description and licensing notice must not grow.
9. Press **Optional review/QC** only when you want deterministic or model-assisted review. This is separate from the NIST snapshot.
10. Export **Results CSV** and **Ambiguity/QC CSV**. Confirm that the Results CSV still contains all raw ranked candidates.

## Licensed analytical run

Follow `docs/NIST_BRIDGE_SETUP.md`, record search options, optimize a representative mzML, freeze/export the deconvolution preset, and apply it unchanged to the comparative batch. Use calibrated RI only when the appropriate phase/program metadata and anchors are available.
