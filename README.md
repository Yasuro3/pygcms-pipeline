# PyGCMS Pipeline — v1.4.1-rc1

**Experimental Global NNLS deconvolution for supported Shimadzu QGD data, with the existing NIST bridge and identification QC.**

The new implementation is in [`pipeline_v141/`](pipeline_v141/). It is an experimental prerelease; see the [release notes](RELEASE_NOTES_v1.4.1-rc1.md), [Japanese instructions](README_v1.4.1_JA.md), and [publication validation](pipeline_v141/docs/PUBLICATION_VALIDATION_v1.4.1-rc1.md).

## Start v1.4.1-rc1 on Windows

1. Extract the complete source archive and open **`pipeline_v141`**.
2. Run **`00_INSTALL_DEPENDENCIES.cmd`** (Python 3.10+ required).
3. Start **`START_v141_GUI.cmd`** to process your QGD ZIP or directory.
4. Follow [`pipeline_v141/README.md`](pipeline_v141/README.md) for input validation and licensed local NIST MS Search setup.

The retained `software/index.html` and the bundled runtime HTML perform legacy v1.4.0 deconvolution. The new Global NNLS engine uses the Python launcher above. The v1.4.0 release remains available at [v1.4.0](https://github.com/Yasuro3/pygcms-pipeline/releases/tag/v1.4.0).

Global signal allocation passes the supplied numerical and query-mapping tests. Model overprediction and incomplete chemical-separation validation remain limitations. A four-run authentic AMDIS comparison is documented; this does not certify a stable replacement.

For v1.4.1-rc1, cite the exact GitHub tag or commit together with the SoftwareX article. A software Zenodo DOI is not assigned. The input field `software_version: "1.4.1"` identifies the compatible data contract; the publication identifier is **1.4.1-rc1**.

---

## Retained v1.4.0 workflow

**Identification QC, structure-aware classification corrections and reproducible reporting.**

The following sections describe the retained v1.4.0 workflow in `software/` and `scripts/`. The v1.4.0 tag and release were published on 19 October 2026. Use the separate `pipeline_v141/` entrypoint for experimental Global NNLS processing.

## What is new

The software preserves the component signal and original library annotations while
adding an auditable reporting layer. The final classifier is version **2.2.0**,
identification-QC rules are **1.0.0**, and the seven-group reporting model is
**JAAP-7-v1.0.0**. The software, classifier and reporting scheme have separate versions.

- Reprocess saved component-level `*_results.csv` files without re-deconvolution,
  another NIST search, or a new external-model call.
- Apply one recorded screening preset: MF >= 800, at least three retained spectral
  ions and at least 0.001% of the within-run pre-screening retained response.
- Preserve rejected/below-threshold records in the audit instead of deleting them.
- Correct explicit non-aromatic assignments, structural-class conflicts and
  formula-only aromaticity claims; retain the previous annotations separately.
- Flag conflicting identifiers, inadequate spectral information, same-formula
  nearby alternatives, multiple retention-time bands and unresolved stereochemistry.
  Do not merge molecular identities merely because their formulas or RTs are similar.
- Export conservative reporting names, complete candidate frequencies, per-run
  coverage, corrected seven-group summaries, ratios, RT diagnostics and change logs.
- Produce an offline printable all-candidate HTML table, including table borders
  and repeated column headings for printing.
- Keep the existing mzML reader, supported Shimadzu GCMSsolution QGD reader,
  deconvolution, licensed local NIST bridge, candidate archive and raw-data batch workflow.

The six native L/P/C/F/S/O marker groups, the structural-product classes and the
seven A/OAr/C/N/F/S/R report groups are **not interchangeable**. No group is a
source-pure environmental pool. See `docs/CLASSIFICATION_LAYERS.md`.

## Start the browser application

Unzip the **complete directory**. Open `software/index.html` in a current Chromium-based
browser. On Windows, `09_OPEN_QC.cmd` opens the application directly without starting
a NIST bridge. Choose **Reprocess saved CSV / QC v1.4.0** on the initial screen, or
**QC & reports v1.4.0** in the application toolbar.

1. Select one or more original `*_results.csv` files. Do not select the class-summary,
   TIC-only, candidate-catalogue or candidate-selection-audit CSV files instead.
2. Optionally load an explicit run manifest; a template and synthetic example are included.
3. Check the preset, click **Run QC**, and inspect per-run coverage and warnings.
4. Export the complete QC ZIP, candidate CSV or printable HTML table.

Processing occurs in the browser locally. The new QC module makes no external API calls.
The older application still has an optional external-model stage; enabling that is
separate from offline QC. Keep confidential material out of any public upload.
For hundreds of MB of verbose candidate exports, use the command-line route below.

## Reprocess a folder or original batch ZIP

Python 3.10+ and Playwright are used to run the **same embedded JavaScript engine** as
the browser. There is no independent Python implementation with different chemistry rules.

```bash
python -m pip install -r requirements.txt -r requirements-browser.txt
python -m playwright install chromium
python scripts/qc_reprocess.py path/to/batch.zip --out path/to/new_results
```

On Windows, replace `python` with `py` as needed. An existing Chrome/Chromium may be
used by the supplied browser helper; alternatively set `PYGCMS_CHROMIUM` to its
executable. See `README_JA.md` for the Windows workflow.

Examples:

```bash
python scripts/qc_reprocess.py path/to/results_folder --out new_results
python scripts/qc_reprocess.py batch.zip --pattern "21*_results.csv" --out survey_only
python scripts/qc_reprocess.py batch.zip --manifest run_manifest.csv --out explicit_runs
python scripts/qc_reprocess.py batch.zip --generic --min-mf 850 --out alternative_QC
```

The output directory must be empty. The CLI streams original raw CSV columns back
into the component audit after computing on a compact projection, preserving all
original candidates, ranks, scores, AI review text and measurements. Source hashes
refer to the original CSV bytes, not to the compact processing view.

## Parameters and denominator

| Parameter | Default | Meaning |
|---|---:|---|
| Minimum NIST MF | 800 | Saved selected-candidate match factor, not an identity probability |
| Minimum retained ions | 3 | Saved `PureIons`; absence is recorded, not inferred |
| Minimum relative response | 0.001% | Component intensity / pre-screening retained run response |
| Near-tie MF gap | 10 | Diagnostic between unique chemical candidate keys |
| RT band gap | 0.12 min | Diagnostic grouping only; not retention alignment |
| Nearby alternative window | 0.08 min | Same-formula/near-RT review flag; not identity merging |
| Coverage warning | 90% | Warning only; never lowers QC thresholds to force coverage |

The default **JAAP_LEGACY** profile retains the article's original annotation-based
exclusions (including exact toluene and specified siloxane/phthalate names). These
are inherited protocol exclusions, not evidence of blank contamination. For other
studies choose **NONE / generic**, which does not treat toluene as a solvent by default.
Original `AI_Action=rejected-all` records remain outside the retained annotated
population in either profile, but are present in the complete audit.

The denominator is frozen **before the new MF/ion/relative-response filters**. It is
not a TIC integral, concentration, response-factor correction or detection limit.
Coverage of all retained annotations differs from coverage of a legacy classified
subset. Explicit `eligible_fixed` flags can additionally expose legacy-primary
coverage; the software never invents this membership.

## Frequencies and summaries

TD and PY frequencies count distinct loaded runs containing at least one passing
assignment to the candidate key. Multiple peaks carrying the key in one run count
once for frequency but all measured responses remain in sums. **Either** uses the
union across complete, unambiguous TD/PY pairs. Repeated runs for one pair are not
silently collapsed. Unknown phase/pair information is reported rather than guessed.
An explicit zero-component run can be added in the manifest with
`Zero_component_run=true`; otherwise a manifest run with missing input is an error.

Two clearly named summary modes are exported:

- **corrected_candidate_conditional**: quality-screened responses grouped by the
  corrected class, conditional on the original tentative candidate name.
- **identity_conservative**: exact-name-withheld candidates are carried in R
  (residual/unresolved) instead of asserting their proposed group is correct.

They use the same passing signal population and each has its own complete seven-group
response balance. They are different inferential views, not interchangeable result
files. Ratios are not calculated when their denominator is zero. The retained raw
response, mass-normalized response (only where mass was recorded), and per-run
percentages are separate fields. A conservative R assignment does not erase signal.

## Output files

| File | Contents |
|---|---|
| `01_component_QC_audit.csv` | All original component columns plus new `QC140_*` fields |
| `02_reported_candidates.csv` | Every passing candidate key, cautious name, classification and frequencies |
| `03_run_QC_summary.csv` | Run-level retention, denominator, counts and metadata |
| `04_group_summary.csv` | Seven-group summaries for both explicitly named modes |
| `05_group_ratios.csv` | OAr/N and A/(N+C), by run and summary mode |
| `06_retention_band_diagnostics.csv` | RT bands with signal contribution; no automatic realignment |
| `07_classification_transitions.csv` | Original-to-corrected classification transitions |
| `08_author_review_queue.csv` | Candidates with unresolved or withheld precise names |
| `09_processing_manifest.json` | Parameters, versions, source hashes and reproducibility boundary |
| `10_printable_inventory.html` | Complete printable candidate table; no unsupported exact identities |

The existing regular results export receives appended QC fields. Its archived raw
candidate/score columns remain available. The former six-group GUI preview is explicitly
labelled a legacy preview; use the new reports for screened seven-group composition.

## Identification boundary

A high MF, a repeated name or consistent RT is not an authentic-standard confirmation.
No positional or stereochemical identity is newly established by this release. The
RT windows are diagnostics, not universal chromatographic tolerances. Independent
standards, characteristic-ion traces and matched retention-index evidence remain
necessary when a study needs a stronger molecular claim. No threshold targets a
particular catalogue size or a desired environmental pattern.

Recorded `IsotopeEvidenceReviewed=true` is an author-supplied review indicator, not an
automatically calculated isotope pattern. Halogenated candidates without such recorded
review are conservatively flagged/withheld, not deleted or declared absent. Similar
formula/RT flags likewise indicate possible ambiguity, not proven misidentification.

## Raw-data and licensed NIST workflow

`00_START_EN.cmd` starts the existing local NIST bridge. Copy `nistms_path.example.txt`
to `nistms_path.txt` and configure your licensed NIST MS Search installation as in
`docs/NIST_BRIDGE_SETUP.md`. Neither NIST software nor its licensed reference spectra,
keys or credentials are distributed here. Existing QGD support is for the recognized
OLE2 layouts and full-scan-like channels; unsupported variants fail with a message.
It is not a universal vendor-format reader.

## Tests and release provenance

```bash
python scripts/embed_qc140.py --check
python scripts/run_checks.py --require-browser
python scripts/verify_checksums.py CHECKSUMS.sha256
```

See `VALIDATION_REPORT.md` for the checks actually executed for this build and their
limits. Existing published/example data are retained as historical fixtures, not
relabelled as newly measured v1.4.0 validation. Private JAAP study data are **not** part
of this public software distribution.

Base: the supplied `v1.3.2 ... direct_Shimadzu_QGD_upload_ready.zip`. Public v1.3.2 main
was identified at GitHub commit `b80df88e00378655d6c1d4cc1647df1fe085a6fb`.
The direct-QGD base and public source are not asserted to be byte-identical.
Base hashes are in `provenance/v140_build_provenance.json`.

## Citation and licence

MIT licence; copyright/authors are retained from the base distribution. Cite the
associated SoftwareX article and the exact release/commit used (v1.4.0 for the legacy workflow).
`CITATION.cff` contains the software contributors, which are not necessarily the
same as the authors of an application paper. Do not reuse a v1.3.x version-specific
Zenodo DOI for this build. This package does not publish itself to GitHub or Zenodo.


## Reprocessing a v1.4.0 export / v1.4.0出力の再処理

Do not import a `QC140_*` audit back over itself. For a newly analyzed sample,
use **Component-source CSV** to save a reprocessable snapshot without appended QC
columns. This preserves previous QC outputs rather than overwriting their history.
`QC140_*`列付きの結果は再入力で上書きしません。新規測定の再処理用には、
**Component-source CSV**を保存してください。コマンドではファイルを直接指定するか、
`--pattern "*_component_source.csv"`を指定します。

For the identity-conservative view, any exact-name-withheld occurrence or conflicting
report-group assignment makes the entire candidate key R across the loaded batch.
This keeps the catalogue class and every contributing summary row consistent.
The candidate-conditional view remains separate and does not apply this propagation.
This is a deliberately conservative sensitivity view, not proof all those signals are false.
