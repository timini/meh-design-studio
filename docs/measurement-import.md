# Complex measurement import

`meh-measurements` implements the first B07 ingestion step. It imports one complex pressure or impedance trace into a private, immutable-by-convention bundle. Imported evidence is always `imported_not_qualified`; the origin field records the user's declaration, not proof that a physical measurement happened. No measurement equipment or rights-cleared driver data is supplied by this increment.

```sh
meh-measurements import examples/measurements/synthetic-pressure.csv \
  --metadata examples/measurements/synthetic-pressure.json --output runs/import-example
meh-measurements inspect runs/import-example
```

The supplied example is invented synthetic data. Its calibration, stimulus voltage and uncertainty are unknown, and it must not establish speaker performance. The same commands are available through `python -m meh_studio.measurement_cli`.

CSV has exactly the header `frequency_hz,real,imag`, followed by positive strictly increasing frequencies and finite real/imaginary values. UTF-8 with or without BOM and normal CSV quoting are accepted. Files are capped at 16 MiB and 100,000 samples. Duplicate/unsorted frequencies, missing values and nonfinite numbers fail before output creation; they are never silently sorted, discarded or repaired.

The metadata records quantity/unit, RMS/peak/unknown amplitude, positive/negative-time phasor convention, declared valid band, source description, fixture identity, signal and processing definitions, stimulus RMS voltage (or unknown), observation coordinates for pressure, calibration hash (or absent), and declared constant magnitude/phase uncertainty. Standard and expanded uncertainty remain distinct; expanded uncertainty requires an explicit coverage factor greater than one. Missing uncertainty stays null. These declarations are retained without conversion or independent verification. Pressure is accepted only in Pa and impedance only in ohms. There is no implicit dB reference, distance scaling, phase inversion, time-zero alignment, smoothing or gain fitting.

All samples remain in the bundle. A Boolean array marks samples inside the declared band; it is a declaration mask, not a tested validity or qualification decision. At least one sample must lie in the band. A declaration does not imply unsampled parts of that band are covered by the trace.

When calibration is declared, supply the matching original file with `--calibration PATH`. The importer copies its exact bytes and verifies the declared hash. It does not apply a calibration curve or assert that the instrument is calibrated. Missing calibration remains visible as unknown. Calibration-file meaning, dates, instrument identity and traceability require subsequent evidence review.

The bundle copies the exact raw CSV and metadata bytes, optionally calibration bytes, and stores frequency/real/imaginary/validity arrays in NPZ. A final manifest publishes their hashes and sizes only after all artifacts are written. Existing output paths are never overwritten. A failed/interrupted import may leave a partial directory without a complete manifest; it cannot be read as a completed import and a retry must use a new path. Hashes establish content integrity, not authenticity or a digital signature.

Every inspection rechecks the copied artifacts and recomputes the arrays from raw CSV, detecting substituted/smoothed values even when someone updates the array hash. Archive entry sizes, header sizes, expected dtype and shape are checked before allocating array data. [NumPy documents the bounded header reader used for this check](https://numpy.org/doc/stable/reference/generated/numpy.lib.format.read_array_header_1_0.html). Symlinked bundle files are rejected. Consumers must use this verified read path rather than trusting an old successful import message.

Tests cover exact raw-byte and phase preservation, retained out-of-band samples, unknown uncertainty, calibration mismatch/corruption, altered derived arrays, compressed archive expansion, invalid inputs, partial output and overwrite refusal. The example command is also exercised end to end. Still required: multi-excitation/polar collections, instrument-format adapters, per-bin uncertainty and noise/window evidence, registered prediction overlays, calibration processing and reviewed qualification decisions. This importer alone does not pass B07 or a physical release gate.
