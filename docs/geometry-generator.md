# Experimental MEH geometry generator

The generator implements a constrained starting point for A04/B02: a straight circular conical horn with one or two symmetric pairs of side entries. Three and five physical source interfaces are supported, counting the throat source. This is geometry infrastructure, not a completed printable speaker design or an acoustic optimisation result.

One SI parameter record builds the main horn air volume, radial entry ducts, circular front chambers and separate rear air chambers. The same construction builds a horn shell and detachable rear cups. CadQuery uses millimetres at the CAD boundary; STEP air solids are imported into Gmsh with metres as its explicit target unit. CAD and imported volumes must agree before meshing.

## Use

Install the optional CAD tools into the MEH environment:

```sh
python -m pip install -e ".[dev,cad]"
meh-geometry examples/three-driver-geometry.json --output runs/my-horn --mesh
```

The output directory must be new. Without `--mesh`, only CAD and surface files are generated. Gmsh must run with no other active model; use a dedicated worker process when embedding this operation.

Outputs include `geometry.json`, editable STEP air solids, STEP/STL/3MF material parts, and optional Gmsh 4.1 ASCII tetrahedral meshes with `analysis/mesh.json`. STL is documented in millimetres; 3MF includes the millimetre unit. Part coordinates are assembly coordinates, not slicer bed placements. Filenames and hashes are recorded. Interrupted or failed operations retain a failed manifest rather than a completion claim.

## Geometry assumptions

The current flare is conical. Adjustable quantities include horn length and throat/mouth radii, side-entry positions, port radius/length, front-chamber radius/depth, rear depth and wall thickness. Each entry pair lies on the positive and negative X sides at the same Z position. The horn axis is positive Z.

The source interfaces are ideal circular disks. Front and rear disks are offset by the reserved mounting-wall thickness; they are intended for a later common mechanical-degree-of-freedom model. These are not detailed purchased-driver geometries: motor intrusion, actual frame shape, suspension travel and mounting screws are not modelled. No driver from the catalogue is automatically qualified by fitting these dimensions.

The main part includes side mounting apertures; rear cups meet its mounting plane. The mounting gap reserves the omitted driver. Hardware, gaskets, sealing, assembly tolerances, reinforcement, print orientation and bed segmentation remain future work. The horn's throat and mouth are intentional open apertures in the material design. Material parts are nevertheless closed solids suitable for mesh export; this does not establish a successful print or assembly.

## Checks and evidence

Inputs reject intersecting chamber envelopes, invalid flare dimensions, unsupported counts, extreme lengths and unsuitable mesh/tessellation targets. Kernel output must consist of positive-volume valid connected solids. Tests additionally check that material does not overlap air and separate parts do not overlap each other for both initial families.

For acoustic meshes, source disks and the mouth must be identified uniquely by planar geometry, centre and area. Remaining constructed faces are rigid walls. Each region has a named volume and physical boundary groups. The front volume contains `throat_source`, one source per side entry and `mouth_interface`; each rear region contains its own rear source. All required source/interface faces must be found. Tetrahedra must have positive quality, and imported air volume must match the source CAD.

The three-driver reference produced three air regions and valid positive-quality tetrahedra locally. Test coverage includes both driver counts, air/material separation, correct 3MF units, named source boundaries, STEP-to-metre conversion and overwrite refusal. A dedicated Linux CI job installs the real CAD kernels; the base test suite can skip CAD-specific tests when those optional tools are absent.

Meshes are explicitly marked `not_converged`, and exports `print_verified: false`. The mouth is tagged for later radiation coupling; this increment does not generate an exterior BEM domain or solve the horn. The next task connects these domains and source interfaces to the adapter, then adds independent numerical comparisons and refinement studies before trusting a candidate's acoustic scores.
