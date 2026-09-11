# Search nonconical profiles with linked symmetry controls

`evolution.profile_symmetry` lets a search preserve equivalent profile directions
while changing the actual CAD surface. It is optional; existing unconstrained
searches retain their previous control hashes and seeded proposal sequence.

```json
{
  "profile_symmetry": "quarter_turn",
  "profile_scale_bounds": [0.65, 1.5],
  "elite_size": 3,
  "explore_every": 4
}
```

Place these controls inside the search brief's `evolution` object and supply a
matching explicit seed geometry. The modes are:

| Mode | Linked azimuthal control indices (0°, 45°, … 315°) | Shape freedom |
| --- | --- | --- |
| `none` | Each control independent | Unconstrained asymmetric profiles; existing default |
| `mirror_xy` | 0/4, 2/6, 1/3/5/7 | Horizontal and vertical profiles may differ; reflection in both axial planes |
| `quarter_turn` | 0/2/4/6, 1/3/5/7 | Equivalent quarter turns; cardinal and diagonal radii may differ |

Every axial section retains its own controls. These modes permit nonconical,
noncircular lofts; they do not substitute a cone or an axisymmetric solver. The
full generated three-dimensional air and material geometry still goes through the
same coupled solver. A four-driver ring with common chamber dimensions can use
`quarter_turn` to keep its four entry directions geometrically equivalent.
Other driver layouts are not made quarter-turn symmetric by a profile setting.

Elite mutation and periodic random exploration both operate on linked groups. A
mutation record identifies every changed angular column; replay uses the saved
mode, seed and preceding solver outcomes. An incompatible seed is rejected before
CAD work, rather than silently modifying it. For example, a quarter-turn section
can use `[1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1]`; each later section may use
different values while preserving the same grouping.

This option is motivated by the dense vocal-band diagnostic: at 3 kHz, summing
the four mid-excitation transfer contributions lost about 8.6 dB relative to their
magnitude sum at the 20 m on-axis point. At 2 kHz the corresponding cancellation
was only 0.25 dB, so symmetry cannot be assumed to cure the whole midband problem.
These columns each include mutually induced driver motion; they are not isolated
diaphagm radiation measurements. The diagnostic remains numerical and unqualified.

Tests retain an exact six-proposal legacy fingerprint, verify linked mutations
and random exploration with replay, reject mismatched seeds, and compare a
nonconical offspring's actual air and material CAD against a 90° rotation. A
symmetry setting does not establish mesh symmetry, acoustic target compliance,
physical source accuracy, commercial fit or print qualification.
