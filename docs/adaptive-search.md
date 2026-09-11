# Simulation-driven freeform mutation

Set `SearchBrief.evolution` to enable a seeded `(mu+1)` evolutionary strategy.
The first declared feasible candidate is the baseline. Following each completed
native FEM/BEM evaluation, the search ranks successful trials by the declared
objective and mutates one of the retained elites. Every fourth proposal by default
explores randomly. Failures are excluded from elite selection and remain recorded.

Each profile has eight radial controls per axial section. Mutations can also
change declared bounds on horn length, mouth radius, port radius/length,
front/rear cavity depth and axial entry fractions. Catalogue alternatives can
change the driver source circuits, with disk areas and total driver cost recomputed.
A candidate without a freeform profile acquires three controlled sections when
mutated. Source circuits remain present in every voltage-basis solve.

`evolution` controls: `elite_size`, `explore_every`, `mutation_fraction`,
`sigma_fraction`, `profile_scale_bounds` and `geometry_bounds`. Bounds are hard
limits for seeds and offspring. Each generation uses a seed derived from the
saved search seed and trial index. New proposals depend on **preceding simulated
fitness**; this is not a preshuffled list of predetermined cones.

To isolate entry-port or chamber effects, set `evolution.mutate_profile` to
`false` and supply at least one applicable `geometry_bounds` entry. Elite
mutation and random exploration then change only those geometric controls;
the seed's profile sections remain exact, including an empty conical profile.
For example, bounds on `port_radius_m`, `port_length_m` and `front_depth_m`
explore the driver-to-horn connection without spending trials on profile changes.
Use singleton seed length/mouth/entry grids and a single source pair when those
also need to stay fixed. Bounds on overall horn dimensions and catalogue changes
still have their usual effect; this setting freezes profile controls only.
The default is `true`, omitted from saved controls to preserve historical search
identities and replay. Explicit `false` participates in the brief identity.
Fixed-profile XY searches do not require profile-mutation symmetry settings;
the existing CAD partition still checks the actual geometry's mirror symmetry.

`search.json` retains parent indices, actual control changes and rejected invalid
proposals. Each accepted candidate has its own CAD, meshes, solver fields, score
and source identities. The solver trial budget counts failed trials as well as
successful ones; up to 64 cheap parameter proposals are attempted per slot, with
all rejected parameter records retained. This is a bounded heuristic search and
has no global-optimum guarantee.

Export and finalist validation reconstruct the winner from the saved fitness and
proposal history and verify its candidate identity. Resume reuses verified whole
completed trials and preserves earlier failed trials unchanged, because retrying
them could alter every later proposal. It retries the interrupted trial and
continues the remaining budget in a new directory. The original search remains
required evidence. Resume rejects changed runtime, controls or proposal history.

The original adaptive demonstration used relative on-axis ripple and cost.
The integrated commercial workflow now also scores horizontal/vertical and sphere
coverage, crossover choices, acoustic mid/HF handover and common-amplifier loading.
Numerical holdouts and mesh refinement remain required before accepting a winner.
Synthetic experiments do not qualify commercial drivers or measured loudspeaker
performance.
