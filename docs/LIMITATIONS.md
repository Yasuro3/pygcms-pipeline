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
- The release is an archived research output; active maintenance is not guaranteed.
