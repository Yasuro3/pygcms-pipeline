# PyGCMS Pipeline v1.4.1-rc1

Experimental prerelease of the Python/Windows Global NNLS deconvolution workflow. This adds `pipeline_v141/` alongside the retained v1.4.0 application.

## Changes

- Shared global nonnegative fitting of EIC-derived component models, duplicate-shape handling, and residual candidate refinement.
- Joint allocation of observed baseline-corrected ion signal without double-counting; separate residual and model-overprediction diagnostics.
- QGD/settings hashes, stable MSP/query identities, and checks preventing reuse of incompatible NIST checkpoints.
- Windows GUI and batch launchers; the v1.4.0 NIST bridge and classification/QC runtime remain pinned and byte-identical.
- Japanese classification definitions and the dated four-run exploratory AMDIS comparison.
- Corrected publication metadata, startup paths, response-scale labels and source checksums. The Windows test launcher runs both supplied test programs.

## Validation and limitations

On 2026-10-23, the synthetic numerical tests, NIST response-mapping contract tests and all 18 upstream runtime hash checks passed. All 12 Python files parse successfully. See `pipeline_v141/docs/PUBLICATION_VALIDATION_v1.4.1-rc1.md`.

The 40-run QGD and four-run AMDIS results are historical package records; they were not rerun during publication checks. Historical model overprediction was 7.5–27.9%. Conservation of allocated signal is an accounting property and does not establish correct chemical separation. Full Windows NIST Automation and comprehensive separation validation remain incomplete in the packaging environment.

## Start

Extract the complete source archive, open `pipeline_v141/`, run `00_INSTALL_DEPENDENCIES.cmd`, then `START_v141_GUI.cmd`. `software/index.html` is the retained v1.4.0 browser workflow. Licensed NIST software and libraries must be supplied separately.

## Citation

Use version **1.4.1-rc1**, this GitHub tag or its immutable commit, and the associated SoftwareX article. No software Zenodo DOI is assigned. Existing v1.4.0 and earlier tags remain unchanged.
