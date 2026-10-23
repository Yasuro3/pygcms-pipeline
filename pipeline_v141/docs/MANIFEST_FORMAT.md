# Manifest format / 試料情報

Raw QGD filenames and folder names may not indicate whether a run is GC, EGA, a blank, or a correction. Set each record's `source_sha256` (64 hex digits of raw QGD **bytes**) explicitly. A filename can be renamed while the fingerprint remains stable.

Acceptable `phase`: `SS`, `TD`, `PY`, `EGA`, `GC_BLANK`.

A CSV must have columns: `source_sha256,run_id,phase,run_type,sample_id,sample_label,mass_mg` (mass optional). `run_id` has `Q01`, `Q02`, ... format, unique per acquisition. You can also use a JSON array with those keys, plus any note fields.

Sample type `FA試料` is interpreted as `is_FA=true` and used for optional FA-only NIST runs. Other sample types are included in all-run searches and blank comparisons but not the FA-only set.

A sample table with no match for a QGD checksum is rejected. A QGD without a manifest must have its `SS`, `TD`, `PY` or `EGA` phase inferable from its path; otherwise the software stops instead of assuming a method.

**Important**: EGA is time-resolved, not GC-separated. Do not send EGA mixed mass spectra as GC-separated single compounds. A source with an EGA folder but a GC blank method requires explicit `GC_BLANK` mapping.

To compute the raw QGD SHA256 on Windows PowerShell:

```powershell
(Get-FileHash -Algorithm SHA256 "C:\data\sample.qgd").Hash.ToLower()
```
