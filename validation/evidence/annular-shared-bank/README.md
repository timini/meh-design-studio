# Shared mid-bank diagnostic from retained native fields

This is an offline reanalysis of the original plain/annular source commit
`381eb8cb8ef14b1feb27bb7586bbcb34f50ff093`. No CAD, mesh or acoustic solve was rerun.
Both scripts verify the archive and consumed member SHA-256 hashes before loading
arrays, and use the original observation points and excitation ordering.

The two mid-pair voltage excitations are summed with equal coefficients. Each
excitation already represents its physical symmetry group; multiplying again by
the driver orbit count would double-count the drive. This tests equal voltage at
the shared mid bank with zero throat excitation, including the saved coupled
response of the unpowered throat. It is not a crossover or calibrated SPL claim.

| Case | Frequency | Common-mid rotational field error |
|---|---:|---:|
| Plain, coarse | 700 Hz | 0.00833% |
| Plain, coarse | 2,750 Hz | 0.15868% |
| Plain, coarse | 4,000 Hz | 0.76634% |
| Annular, coarse | 700 Hz | 0.00851% |
| Annular, coarse | 2,750 Hz | 0.25357% |
| Annular, coarse | 4,000 Hz | 0.75103% |
| Annular, refined | 4,000 Hz | 0.36239% |

These auxiliary common-drive symmetry checks fall below 2%, while the original
individual-basis checks still fail. **The common-mid complex field changes by
51.07259% between coarse and refined meshes at 4 kHz.** The denominator is the
coarse common-mid field norm; horizontal and vertical observation vectors are
concatenated. This remains far above 2%, so the apparently symmetric common-drive
result does not resolve convergence or qualify the annular response dip.

Interior and exterior discretisations both change in the original refinement.
This comparison cannot isolate their contributions. Physical/source validity,
frequency-band performance and print qualification remain unproven. Original
reports and failures have not been replaced or reclassified.

Reproduce with Python and NumPy from the repository root, with the adjacent
`annular-mid-entry` and `annular-mid-refinement` archives present:

```sh
python validation/evidence/annular-shared-bank/analyse.py
python validation/evidence/annular-shared-bank/refinement.py
```

The scripts rewrite only their adjacent derived JSON reports. No native runtime
or external data is needed. The JSON files retain unrounded values.
