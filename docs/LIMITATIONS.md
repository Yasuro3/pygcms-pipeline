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
