# Deconvolution method statement

PyGCMS Pipeline uses conventional chromatographic deconvolution operations: TIC peak localization, local ion-trace screening, construction of a representative chromatographic model, least-squares estimation of baseline/trend/model coefficients, ion-shape correlation filtering and base-peak-relative spectrum filtering.

The software does not claim a new fundamental deconvolution theory. Its analytical contribution is the integration of adjustable processing, parameter capture, top-N candidate preservation, evidence tracking and auditable export in one browser workflow.

The exact distributed implementation is defined by `software/index.html` and the v1.3.0 archive checksum manifest. The manuscript and Supplementary Information describe the algorithm and parameter effects.
