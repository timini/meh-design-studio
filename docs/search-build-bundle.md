# Export a completed search

Create an experimental build bundle from an existing search without rerunning CAD
or the acoustic solver:

```sh
meh export-search runs/search --output horn-build.zip
```

Run this against the original search directory while its referenced solver files
remain available. The exporter verifies the saved winner, driver revisions, score,
original evaluation and geometry before creating the ZIP. It refuses to replace an
existing output file and publishes only a fully written bundle.

The ZIP contains:

- `geometry/`: original declared STEP/STL/3MF and air-domain CAD exports, with their
  geometry manifest. Use material files in `geometry/parts` for print planning;
  air domains are not print parts. Raw solver meshes and arrays remain in the
  original search evidence and are not copied into this build bundle.
- `bom.json`: throat and side driver models, revisions, quantities, supplied unit
  prices and driver-only total in the search currency. Amplification, DSP, material,
  printing, hardware and assembly costs are excluded.
- `gain-settings.json`: the winning relative voltage-basis multipliers, with channel
  identities and zero added phase/delay. This is not a calibrated hardware crossover
  preset; no frequency-dependent filters or absolute amplifier voltage are inferred.
- `assembly.json`: material STL references, identity placement transforms and source
  locations. The material parts already share their assembled millimetre coordinate
  frame; source locations retain their explicitly labelled metre units.
- `candidate.json`, `brief.json`, `score.json` and `bundle.json`: selected parameters,
  source records, inputs, score, runtime identity and per-file SHA-256 hashes.

This is a **search export**, not a new simulation or a finalist-validation report.
An exported search may still need denser frequency sampling and mesh refinement.
The bundle preserves the electrical-consistency outcome and always leaves physical
and print qualification false. Synthetic drivers remain synthetic. Practical driver
mounts, seals, supports, two-slicer checks and a physical build remain required.

This implements the metadata/export portion of B06. It does not complete B06's
manufacturing and slicer acceptance gate. The command has been exercised against
the completed compact native search; no new acoustic solve was needed.
