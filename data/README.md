# Data files

- `application/17B_class_summary_percent.csv`: aggregate ten-run source summary used for the Lake Biwa class-composition example.
- `derived/class_composition_classified_records_percent.csv`: long-form classified-only composition, ordered TD L1-L5 then Py L1-L5.
- `derived/excluded_record_counts_by_sample.csv`: accounting table for records excluded from the compositional denominator.
- `example/`: synthetic mzML and selected-component example for format testing only.
- `validation/full_length/17B_L1_PY_full_length_validation.mzML`: full-length processed mzML used for reader and parameter-responsiveness validation.
- `validation/`: structural, round-trip, browser-level equivalence, and single-run timing notes.

The release does **not** contain component-level or candidate-level Lake Biwa
application records, nor component peak areas. Figure 4's component-count
proportions can be reproduced from the aggregate summary; an abundance-weighted
analysis cannot be reconstructed from this deposit.

Unclassified records are not used as a natural-organic-matter class or as an
analytical-performance axis. They remain accounted for separately because the
pool may include unresolved products, weak or mixed spectra, contaminants,
analytical background, and possible siloxane bleed.
