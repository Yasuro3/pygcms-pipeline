# Retention-index evidence

Retention index (RI) is optional orthogonal evidence. It does not replace spectral inspection, and the software keeps calculated and reference values separate.

## 1. Prepare calibration anchors

Use an n-alkane ladder or manually verified compounds acquired under the same stationary phase and GC program. A minimal CSV is supplied at `data/example/ri_calibration_example.csv`:

```text
compound,rt_min,ri,role
n-Decane,7.450,1000,calibration
n-Undecane,9.210,1100,calibration
n-Dodecane,11.030,1200,calibration
```

Record the column phase, dimensions, temperature program, carrier-gas conditions, calibration compounds, run date, and whether interpolation or extrapolation was used.

## 2. Fit or enter the RT-to-RI model

The interface supports an RT-to-RI calibration from manual anchors or an n-alkane ladder. Export the calibration/model record with coefficients, interpolation range, fit statistics, and anchor table.

## 3. Keep evidence fields separate

For each candidate retain:

- calculated RI from the sample's RT-to-RI model;
- external/reference RI and source;
- `Delta_RI = calculated - reference`;
- stationary-phase compatibility;
- whether the result is interpolation or extrapolation.

Do not overwrite a NIST MF/RMF with an RI-adjusted score. If a candidate is selected partly because of RI, record that reason separately.

## 4. Limitations

RI values depend on phase, film thickness, flow, program, and calibration. A literature RI from an incompatible phase is not a confirmation. If no calibrated model is available, leave calculated RI blank rather than estimating it informally.
