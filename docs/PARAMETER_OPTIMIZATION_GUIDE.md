# Parameter optimization guide

The interface defaults are starting values, not universal optima. Optimize on representative chromatograms before comparative batch processing.

| Parameter | Lower value generally | Higher value generally |
|---|---|---|
| TIC peak threshold | Increases weak-peak sensitivity and background detections | Suppresses background and weak components |
| Half-window | Favors narrow peaks and crowded regions | Accommodates broader peaks but can include neighbours |
| Ion-shape correlation | Retains more imperfect/coeluting ions | Produces more selective component spectra |
| Spectrum cutoff | Retains minor fragments | Produces compact spectra dominated by abundant ions |
| Start retention time | Includes early peaks and solvent-front structure | Excludes early background |
| Common-bleed exclusion | Disabled: retains all base-peak types | Enabled: removes common column-bleed-dominated components |

Use the TIC, reconstructed component spectrum, blank, known standards and matrix context together. Once accepted, export the parameter JSON and apply the same values to samples that will be compared.
