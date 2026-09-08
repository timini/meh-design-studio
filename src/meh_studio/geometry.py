"""Experimental straight MEH geometry: one source of CAD for air and material.

Dimensions are SI in the design and converted to millimetres at the CAD boundary.
The shapes use ideal circular diaphragm interfaces, not detailed purchased drivers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import model_validator

from .domain import Positive, Record


class HornGeometry(Record):
    length_m: Positive
    throat_radius_m: Positive
    mouth_radius_m: Positive
    wall_m: Positive
    entry_positions_m: tuple[Positive, ...]
    port_radius_m: Positive
    port_length_m: Positive
    front_radius_m: Positive
    front_depth_m: Positive
    rear_depth_m: Positive
    mesh_size_m: Positive
    tessellation_tolerance_m: Positive = 0.0001

    @model_validator(mode="after")
    def valid_family(self):
        if len(self.entry_positions_m) not in (1, 2):
            raise ValueError("one or two symmetric entry pairs are supported")
        if self.mouth_radius_m <= self.throat_radius_m:
            raise ValueError("mouth must exceed throat radius")
        if self.front_radius_m <= self.port_radius_m:
            raise ValueError("front chamber radius must exceed port radius")
        margin = self.front_radius_m + self.wall_m
        flare_slope = (self.mouth_radius_m - self.throat_radius_m) / self.length_m
        if self.wall_m + self.port_length_m <= flare_slope * margin:
            raise ValueError("entry chamber envelope is buried by the horn flare")
        if self.tessellation_tolerance_m < 1e-6:
            raise ValueError("tessellation tolerance must be at least 1 micrometre")
        if any(not margin < z < self.length_m - margin for z in self.entry_positions_m):
            raise ValueError("entry chambers must clear throat and mouth planes")
        if any(b - a <= 2 * margin for a, b in zip(self.entry_positions_m, self.entry_positions_m[1:])):
            raise ValueError("entry pairs must be ordered with non-overlapping chamber envelopes")
        if self.wall_m >= min(self.throat_radius_m, self.front_radius_m):
            raise ValueError("wall thickness exceeds the supported feature proportions")
        if max(self.port_length_m, self.front_depth_m, self.rear_depth_m) > 1:
            raise ValueError("chamber/duct length exceeds the supported metre-scale domain")
        if self.mesh_size_m < 0.0005:
            raise ValueError("mesh target is below the supported 0.5 mm lower bound")
        if self.mesh_size_m > 2 * self.port_radius_m:
            raise ValueError("mesh target exceeds port diameter")
        if self.tessellation_tolerance_m >= min(self.wall_m, self.port_radius_m) / 2:
            raise ValueError("tessellation tolerance is too large for the smallest feature")
        # Bound this experimental generator's dimensional domain before kernel work.
        if not 0.02 <= self.length_m <= 2 or not 0.001 <= self.throat_radius_m < self.mouth_radius_m <= 1:
            raise ValueError("geometry is outside the generator's supported scale")
        return self

    @property
    def driver_count(self) -> int:
        return 1 + 2 * len(self.entry_positions_m)


def build_geometry(design: HornGeometry):
    """Return experimental air regions, material parts and semantic source locations."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()

    mm = 1000.0
    length, throat, mouth, wall = (v * mm for v in (
        design.length_m, design.throat_radius_m, design.mouth_radius_m, design.wall_m))
    front_air = cq.Solid.makeCone(throat, mouth, length)
    material = cq.Solid.makeCone(throat + wall, mouth + wall, length)
    air_regions, parts, sources = {}, {}, []
    for pair, entry in enumerate(design.entry_positions_m):
        z = entry * mm
        local_radius = throat + (mouth - throat) * z / length
        duct_end = local_radius + wall + design.port_length_m * mm
        diaphragm = duct_end + design.front_depth_m * mm
        for sign, side in ((1, "positive"), (-1, "negative")):
            label = f"entry_{pair}_{side}"
            direction = cq.Vector(sign, 0, 0)
            def cylinder(radius, start, depth):
                return cq.Solid.makeCylinder(radius, depth, cq.Vector(sign * start, 0, z), direction)
            tube = cylinder(design.port_radius_m * mm, 0, duct_end)
            chamber = cylinder(design.front_radius_m * mm, duct_end, design.front_depth_m * mm)
            front_air = front_air.fuse(tube, chamber)
            material = material.fuse(
                cylinder(design.port_radius_m * mm + wall, 0, duct_end + wall),
                cylinder(design.front_radius_m * mm + wall, duct_end, design.front_depth_m * mm + wall))
            # Open mounting aperture; the missing driver is an explicit reserved volume.
            material = material.cut(cylinder(design.front_radius_m * mm, diaphragm, wall * 2))
            rear_start = diaphragm + wall
            rear_air = cylinder(design.front_radius_m * mm, rear_start, design.rear_depth_m * mm)
            rear_cup = cylinder(design.front_radius_m * mm + wall, rear_start,
                                design.rear_depth_m * mm + wall).cut(rear_air)
            air_regions[f"rear_{label}"] = rear_air
            parts[f"rear_cup_{label}"] = rear_cup
            sources.append({"id": label, "front_center_m": [sign * diaphragm / mm, 0, entry],
                            "rear_center_m": [sign * rear_start / mm, 0, entry],
                            "motion_axis": [sign, 0, 0], "radius_m": design.front_radius_m})
    parts["horn"] = material.cut(front_air).clean()
    air_regions["front"] = front_air.clean()
    for name, solid in {**parts, **air_regions}.items():
        if not solid.isValid() or solid.Volume() <= 0 or len(solid.Solids()) != 1:
            raise ValueError(f"geometry kernel produced an invalid or disconnected solid: {name}")
    return air_regions, parts, sources


def export_geometry(design: HornGeometry, output: Path) -> dict:
    """Export assembly-coordinate CAD and triangle meshes; no print verification claim."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    state = {"schema_version": 1, "status": "running", "design_hash": design.content_hash,
             "evidence": "experimental_geometry", "print_verified": False,
             "units": {"design": "m", "cad_and_stl": "mm"}}
    manifest = output / "geometry.json"
    try:
        regions, parts, sources = build_geometry(design)
        files = []
        for group, shapes in (("air", regions), ("parts", parts)):
            directory = output / group
            directory.mkdir()
            for name, shape in shapes.items():
                for extension in (("step",) if group == "air" else ("step", "stl", "3mf")):
                    path = directory / f"{name}.{extension}"
                    cq.exporters.export(shape, str(path), tolerance=design.tessellation_tolerance_m * 1000,
                                        angularTolerance=0.1)
                    files.append({"path": path.relative_to(output).as_posix(),
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "size_bytes": path.stat().st_size})
        state.update(status="complete", design=design.model_dump(mode="json"),
                     driver_count=design.driver_count, sources=sources, files=files,
                     air_volume_m3={name: solid.Volume() / 1e9 for name, solid in regions.items()},
                     material_volume_m3={name: solid.Volume() / 1e9 for name, solid in parts.items()},
                     limitations=["Ideal circular source interfaces, not qualified purchased-driver mounting geometry",
                                  "No mounting hardware, seals, print-bed segmentation or structural validation",
                                  "No acoustic solve or mesh-convergence claim"])
    except BaseException as exc:
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        temporary = output / "geometry.json.tmp"
        temporary.write_text(json.dumps(state, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(manifest)
    return state


def mesh_geometry(output: Path) -> dict:
    """Mesh the exported air solids in metres with named physical boundary groups."""
    import math
    import gmsh

    output = Path(output).resolve()
    geometry = json.loads((output / "geometry.json").read_text(encoding="utf-8"))
    if geometry["status"] != "complete":
        raise ValueError("CAD generation must complete before meshing")
    design = HornGeometry.model_validate(geometry["design"])
    if design.content_hash != geometry["design_hash"]:
        raise ValueError("geometry design identity mismatch")
    files = {item["path"]: item for item in geometry["files"]}
    for region in geometry["air_volume_m3"]:
        if not region.replace("_", "").isalnum():
            raise ValueError("invalid region identifier")
        relative = f"air/{region}.step"
        path = output / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != files[relative]["sha256"]:
            raise ValueError("air solid changed after geometry export")
    if gmsh.isInitialized():
        raise ValueError("meshing requires an isolated Gmsh process with no active model")
    directory = output / "analysis"
    directory.mkdir(exist_ok=False)
    report = {"schema_version": 1, "status": "running", "units": "m",
              "design_hash": design.content_hash, "accuracy": "not_converged", "regions": []}
    try:
        for region, expected_volume in geometry["air_volume_m3"].items():
            if 6 * expected_volume / design.mesh_size_m**3 > 2_000_000:
                raise ValueError("estimated tetrahedral workload exceeds this generator's mesh budget")
            gmsh.initialize()
            try:
                gmsh.option.setNumber("General.Terminal", 0)
                gmsh.option.setString("Geometry.OCCTargetUnit", "M")
                gmsh.model.occ.importShapes(str(output / "air" / f"{region}.step"))
                gmsh.model.occ.synchronize()
                volumes = gmsh.model.getEntities(3)
                if len(volumes) != 1:
                    raise ValueError("air region must import as one solid")
                volume = gmsh.model.occ.getMass(3, volumes[0][1])
                if not math.isclose(volume, expected_volume, rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError("CAD-to-analysis volume or unit mismatch")
                expected = {}
                if region == "front":
                    expected["throat_source"] = ([0, 0, 0], design.throat_radius_m, "source")
                    expected["mouth_interface"] = ([0, 0, design.length_m], design.mouth_radius_m, "radiation_interface")
                    for source in geometry["sources"]:
                        expected[source["id"] + "_front_source"] = (source["front_center_m"], source["radius_m"], "source")
                else:
                    source = next(s for s in geometry["sources"] if region == "rear_" + s["id"])
                    expected[source["id"] + "_rear_source"] = (source["rear_center_m"], source["radius_m"], "source")
                tags = {name: [] for name in expected}
                walls = []
                for dimension, tag in gmsh.model.getBoundary(volumes, oriented=False):
                    centre = gmsh.model.occ.getCenterOfMass(dimension, tag)
                    area = gmsh.model.occ.getMass(dimension, tag)
                    matches = [name for name, (point, radius, role) in expected.items()
                               if gmsh.model.getType(dimension, tag) == "Plane"
                               and math.dist(centre, point) < 1e-7
                               and math.isclose(area, math.pi * radius**2, rel_tol=1e-6)]
                    if len(matches) > 1:
                        raise ValueError("ambiguous source boundary")
                    if matches:
                        tags[matches[0]].append(tag)
                    else:
                        walls.append(tag)
                if any(len(values) != 1 for values in tags.values()) or not walls:
                    raise ValueError("an expected source/interface face was not uniquely identified")
                gmsh.model.addPhysicalGroup(3, [volumes[0][1]], 1, name="air_" + region)
                groups = []
                for physical_tag, (name, surfaces) in enumerate(tags.items(), start=10):
                    gmsh.model.addPhysicalGroup(2, surfaces, physical_tag, name=name)
                    groups.append({"name": name, "tag": physical_tag, "role": expected[name][2]})
                gmsh.model.addPhysicalGroup(2, walls, 99, name="rigid_walls")
                groups.append({"name": "rigid_walls", "tag": 99, "role": "rigid_wall"})
                gmsh.option.setNumber("Mesh.MeshSizeMin", design.mesh_size_m)
                gmsh.option.setNumber("Mesh.MeshSizeMax", design.mesh_size_m)
                gmsh.option.setNumber("Mesh.ElementOrder", 1)
                gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
                gmsh.option.setNumber("Mesh.Binary", 0)
                gmsh.model.mesh.generate(3)
                tetrahedra, _ = gmsh.model.mesh.getElementsByType(4)
                if not len(tetrahedra):
                    raise ValueError("mesher produced no tetrahedra")
                qualities = gmsh.model.mesh.getElementQualities(tetrahedra)
                if min(qualities) <= 0:
                    raise ValueError("mesh contains inverted or degenerate tetrahedra")
                path = directory / f"{region}.msh"
                gmsh.write(str(path))
                report["regions"].append({"id": region, "path": path.relative_to(output).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "volume_m3": volume,
                    "tetrahedra": len(tetrahedra), "minimum_quality": float(min(qualities)), "boundaries": groups})
            finally:
                gmsh.finalize()
        report["status"] = "complete"
    except BaseException as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        temporary = directory / "mesh.json.tmp"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(directory / "mesh.json")
    return report
