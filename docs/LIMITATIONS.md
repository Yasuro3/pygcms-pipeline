# Limitations

- The reader targets a documented subset of nominal-mass, MS1, full-scan mzML and is not a universal mzML implementation.
- Accurate-mass profile information is mapped to nominal-mass bins; the release is not intended for high-resolution exact-mass interpretation.
- MS-Numpress, MSn acquisition, ion mobility, GCxGC-specific structures, and unsupported parameter-reference patterns are outside the validated scope.
- Browser parsing of very large mzML files is limited by available memory.
- Deconvolution results depend on chromatographic quality and the selected parameters. Defaults are starting points, not universal optima.
- High thresholds or correlation requirements can remove weak components; permissive settings can admit noise or neighboring ions.
- Coeluting compounds with highly similar ion profiles may remain unresolved.
- The public release does not read vendor-native files and does not establish universal native-file/mzML equivalence.
- NIST library candidates remain putative unless supported by standards or independent evidence.
- NIST results can change with product build, library release, search mode, preprocessing, and top-N settings.
- Literature-guided classes are matrix- and context-dependent and should remain traceable to reviewed sources.
- Optional external-model output is advisory, version-dependent, and subject to data-governance requirements.
- NIST software, libraries, vendor converters, vendor-native files, licensed spectra, and credentials are not distributed.
- The production NIST bridge is Windows-specific and depends on the file-automation behaviour of the user's NIST MS Search build. The included contract test does not replace a licensed-installation self-test.
- The release is an archived research output; active maintenance is not guaranteed.

## Shared fragments between co-eluting components

Ion grouping is based on how closely an extracted-ion trace co-varies with the
local component model profile. An ion that is produced by two components eluting
close together carries two apices within the same window, so it co-varies poorly
with either single-component profile and is admitted to neither reconstructed
spectrum at the archived default correlation threshold.

`tests/test_deconvolution_numeric.py` demonstrates this against a synthetic
ground truth in which two components 12 scans apart share m/z 39. The unique
ions of each component are recovered with a cosine similarity of about 0.95-0.96
to their synthetic spectra, and with no cross-contamination between the two
(cosine 0.00), but the shared ion appears in neither.

The practical consequence matters most for low-mass fragments such as m/z 39, 41,
43 and 55, which are common to many pyrolysis products. Where such ions are
shared by co-eluting components, the reconstructed spectra will be missing them
and library match factors may be lower than for an isolated peak of the same
compound. Lowering the shape-correlation threshold admits more of these ions at
the cost of also admitting neighbouring and background signals; this is one of
the trade-offs the exposed controls exist to let the analyst make against
representative data. Analysts who need shared fragments apportioned rather than
excluded should compare against a tool that implements an apportioning model.

## Deposited application data and timing scope

The Lake Biwa application deposit contains the aggregate ten-run class-summary
table used to generate Figure 4, not component-level candidate records or peak
areas. Component-count composition can be reproduced; abundance-weighted
composition and candidate-level sensitivity metrics cannot be reconstructed
from this release.

The archived full-length loading and deconvolution times are single-run
diagnostics. Hardware, memory, operating-system build, and browser build were
not captured for that original run, so the values are not a portable benchmark.


## v1.3.1 reviewer-driven clarifications

- Components with few reconstructed ions can be chromatographically real but inadequate for reliable EI library interpretation. Automatic-search eligibility is therefore separated from component retention. The default of three ions is a workflow flag, not an identification threshold or guarantee.
- Match-gap and CAS grouping are presentation/QC layers. Duplicate library records and every original rank remain in the candidate export.
- The full-length default extraction contains sparse and rich spectra; accepted-ion distributions are reported under `data/validation/profile_sensitivity/`. Parameter responsiveness does not by itself establish identification superiority.
- Licensed NIST identification changes across deconvolution profiles are not claimed by the public, licence-free validation. `scripts/compare_profile_nist_exports.py` is provided for laboratories that run all profiles with the same licensed library/search configuration.
- The five NOM marker groups are application-specific literature-guided annotations, not a universal organic-matter taxonomy. The separate nine-class structural-product scheme is descriptive.
- Conventional GC-MS use is technically supported within the documented mzML scope, but real-data validation outside Py-GC/MS remains limited.

## Operational classification limitations

ClassificationModelVersion 2.0.0 assigns operational marker groups after candidate selection; it does not convert a library candidate into a confirmed molecular identity or unique precursor source. Aromatic hydrocarbons, phenols, nitriles and other pyrolysis products can have several natural, anthropogenic or secondary thermal origins. Exact rules prevent known logical misclassification, but they do not remove this chemical ambiguity. Sample-specific analytical additions (for example toluene used as an internal-standard solvent) must be excluded from environmental-composition denominators separately and documented.

## Classification-model boundary

Model 2.0.0 provides operational marker groups and structural-product labels, not confirmed source apportionment. Exact-name/CAS rules prevent known overwrite errors, but a correct class label does not establish a unique precursor. The archived Figure 4 table is an aggregate from the analysis version used for the manuscript; its underlying component-level rows are not deposited, so it is not retrospectively reconstructed from a different export.
