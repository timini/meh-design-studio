# Solana 2.0 comparison reference

Checked 11 September 2026. The [current JW Sound download page](https://www.jwsound.live/solana-diy)
links John White's **Solana DIY Guide, revision 2.0, 31 August 2026**.
The locally inspected PDF has SHA-256
`048337887f969f89303ed295ec9d573cfcc25183999f87aaed0a3587d503a637`.

The guide specifies 90° horizontal/vertical coverage, four B&C 6NDL38 mids,
a DH450 HF driver and a **1,200 Hz LR6 acoustic crossover**. Pages 3, 4 and 7
were visually inspected. Published measurements use ground plane, 1/48-octave
smoothing and a 30-cycle frequency-dependent window. The polar reference is
10° off axis. The 3%/10% THD output plots use one-third-octave stepped bursts,
683 ms below 300 Hz and 171 ms above, with 2 seconds between bursts.

The linked 16-file build package contains CAD/STL/DXF, the guide and an Ath
configuration, but no raw polar, impedance or distortion measurement dataset.
Its advanced configuration describes a 140 mm waveguide with a 353 mm mouth
target and superformula/morph controls. The files remain local reference
material and are not redistributed here.

The designer's [31 August comparison](https://www.diyaudio.com/community/threads/solana-project-thread.439795/page-4)
shows measured and Boundary Lab FEM/BEM polars; the accompanying discussion
identifies 10° measurement spacing versus 1° simulation spacing. This is useful
external evidence for the method, but is not validation of our meshes or sources.

## Consequences for this project

Keep the maintainer's 350 Hz lower handover and 3–5 kHz vocal-mid handover. The
reference does not establish that those requirements can be met by our selected
drivers. Do not replace them with Solana's crossover to obtain a passing score.

Current searches use unsmoothed samples, an on-axis reference and 20 m finite
distance. Those results cannot be equated directly to the published measurement
plots. A future comparison needs matched axes, angular/frequency sampling,
distance, DSP, level and distortion protocol. Our linear model does not predict
THD-limited output. Raw reference data and clarified absolute level/distance
conditions would be needed for a quantitative equivalence claim.

The reference's short waveguide also motivates testing a wider range of axial
lengths and entry arrangements after the current curved seeds are evaluated.
Changing those controls must still produce feasible cavities and source
interfaces; shortening the horn alone does not guarantee shorter entry ducts.
