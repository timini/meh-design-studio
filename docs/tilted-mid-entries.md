# Tilted mid-driver entries

`HornGeometry.driver_tilt_deg` permits a common entry tilt between 0 and 60 degrees.
Positive tilt turns each outward driver axis toward the throat: the x-positive
driver's axis becomes `(cos(angle), 0, -sin(angle))`. A four-driver ring rotates
this axis around the horn, preserving its common axial component and source IDs.

The angle changes the port, front chamber, diaphragm plane, rear cavity, material
parts and rigid exterior envelope. Meshing uses the resulting CAD, and the physical
driver components receive the same tilted motion axes. The original axial entry
coordinate is the tilted port centreline's intersection with the horn's main axis;
it is not the driver centre or the port's wall-intersection coordinate.

To keep a front chamber outside a curved flare, the generator clips the unported
horn air to the chamber's circular envelope and finds the furthest extent along
the tilted axis. The declared wall and duct lengths then locate the chamber beyond
that extent. Exact CAD checks still reject intersecting parts, disconnected air,
missing chamber back walls and front chambers crossing the throat or mouth plane.
This permits shorter passages in some steep flares; it does not guarantee a shorter
passage or a better acoustic result for every angle.

Zero tilt is omitted from serialized geometry, preserving existing radial design
identities and seeded searches. A tilted driver currently requires zero
`driver_axial_offset_m`; combining an eccentric port with a tilted driver is rejected.
Searches can add a gene such as:

```json
"geometry_bounds": {
  "driver_tilt_deg": [0.0, 40.0]
}
```

Angles are recorded in candidate geometry and mutation parentage and replayed from
the declared seed and fitness history. Other geometry constraints still apply, so
some proposed angles will be rejected during validation or CAD construction.

The [tilted ring example](../examples/tilted-ring-geometry.json) uses ideal circular
driver interfaces. Tilting does not supply commercial cone/basket/motor geometry,
bolt interfaces, an HF mounting package or print qualification. Rear cups can extend
toward the throat; clearance to an actual HF driver and its wiring remains a separate
mechanical requirement. Acoustic benefit requires a completed coupled simulation
and the existing numerical/response checks.
