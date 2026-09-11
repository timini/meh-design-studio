"""Experimental straight MEH geometry: one source of CAD for air and material.

Dimensions are SI in the design and converted to millimetres at the CAD boundary.
The shapes use ideal circular diaphragm interfaces, not detailed purchased drivers.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_serializer, model_validator

from .domain import Positive, Record
from .waveguide_profile import ProfileSection, validate_profile, horn_solids, mouth_face, entry_support_radius, cad_volume, imported_volume


class ThroatBody(Record):
    """Rigid cylindrical HF package behind the throat; not a printable part."""
    radius_m: Annotated[float, Field(strict=True, gt=0, le=.5)]
    depth_m: Annotated[float, Field(strict=True, gt=0, le=.5)]


class HornGeometry(Record):
    length_m: Positive
    throat_radius_m: Positive
    throat_body: ThroatBody | None = None
    mouth_radius_m: Positive
    wall_m: Positive
    entry_positions_m: tuple[Positive, ...]
    driver_axial_offset_m: Annotated[float, Field(strict=True,ge=-.5,le=.5)] = 0.
    driver_tilt_deg: Annotated[float, Field(strict=True, ge=0, le=60)] = 0.
    entry_layout: Literal['opposed_pairs', 'four_driver_ring'] = 'opposed_pairs'
    profile_sections: tuple[ProfileSection, ...] = ()
    profile_interpolation: Literal['legacy', 'periodic_cubic'] = 'legacy'
    profile_loft: Literal['smooth', 'ruled'] = 'smooth'
    port_radius_m: Positive
    port_length_m: Positive
    front_radius_m: Positive
    front_depth_m: Positive
    rear_depth_m: Positive
    mesh_size_m: Positive
    rear_axial_mesh_size_m: Annotated[float, Field(strict=True, ge=0.0001)] | None = None
    solver_symmetry: Literal['off', 'xy'] = 'off'
    tessellation_tolerance_m: Positive = 0.0001
    maximum_tetrahedra: Annotated[int, Field(strict=True, ge=1, le=10_000_000)] = 2_000_000
    maximum_exterior_triangles: Annotated[int, Field(strict=True, ge=1, le=32_000)] = 8000
    maximum_raw_exterior_triangles: Annotated[int, Field(strict=True, ge=1, le=64_000)] | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy_pair_identity(self, handler):
        value = handler(self)
        if self.throat_body is None:
            value.pop('throat_body', None)
        if self.entry_layout == 'opposed_pairs':
            value.pop('entry_layout', None)
        if self.driver_axial_offset_m == 0:
            value.pop('driver_axial_offset_m',None)
        if self.driver_tilt_deg == 0:
            value.pop('driver_tilt_deg', None)
        if not self.profile_sections:
            value.pop('profile_sections', None)
        if self.profile_interpolation == 'legacy':
            value.pop('profile_interpolation', None)
        if self.profile_loft == 'smooth':
            value.pop('profile_loft', None)
        if self.rear_axial_mesh_size_m is None:
            value.pop('rear_axial_mesh_size_m', None)
        if self.maximum_tetrahedra == 2_000_000:
            value.pop('maximum_tetrahedra', None)
        if self.maximum_exterior_triangles == 8000:
            value.pop('maximum_exterior_triangles', None)
        if self.maximum_raw_exterior_triangles is None:
            value.pop('maximum_raw_exterior_triangles', None)
        if self.solver_symmetry == 'off':
            value.pop('solver_symmetry', None)
        return value

    @model_validator(mode="after")
    def valid_family(self):
        validate_profile(self.profile_sections)
        if self.rear_axial_mesh_size_m is not None and self.rear_axial_mesh_size_m > self.mesh_size_m:
            raise ValueError('rear axial mesh spacing must not exceed the general mesh size')
        if len(self.entry_positions_m) not in (1, 2):
            raise ValueError("one or two symmetric entry pairs are supported")
        if self.entry_layout == 'four_driver_ring' and len(self.entry_positions_m) != 1:
            raise ValueError('four-driver ring requires exactly one axial entry position')
        if self.mouth_radius_m <= self.throat_radius_m:
            raise ValueError("mouth must exceed throat radius")
        if self.throat_body is not None and self.throat_body.radius_m < self.throat_radius_m + self.wall_m:
            raise ValueError('throat body must cover the throat and its wall')
        if self.front_radius_m <= self.port_radius_m:
            raise ValueError("front chamber radius must exceed port radius")
        if self.driver_tilt_deg and self.driver_axial_offset_m:
            raise ValueError('tilted entries currently require concentric driver and port axes')
        if abs(self.driver_axial_offset_m)+self.port_radius_m >= self.front_radius_m:
            raise ValueError('eccentric port must fit inside the front chamber face')
        margin = self.front_radius_m + self.wall_m
        flare_slope = (self.mouth_radius_m - self.throat_radius_m) / self.length_m
        if not self.driver_tilt_deg and not self.profile_sections and self.wall_m + self.port_length_m <= flare_slope * margin:
            raise ValueError("entry chamber envelope is buried by the horn flare")
        if self.entry_layout == 'four_driver_ring' and not self.driver_tilt_deg:
            radius = self.throat_radius_m + flare_slope * (self.entry_positions_m[0]+self.driver_axial_offset_m)
            if radius + self.port_length_m <= margin:
                raise ValueError('adjacent ring chamber envelopes overlap')
        if self.tessellation_tolerance_m < 1e-6:
            raise ValueError("tessellation tolerance must be at least 1 micrometre")
        if any(z+self.driver_axial_offset_m >= self.length_m-margin or
               (self.throat_body is None and z+self.driver_axial_offset_m <= margin)
               for z in self.entry_positions_m):
            raise ValueError("entry chambers must clear throat and mouth planes")
        port_margin=self.port_radius_m+self.wall_m
        if any(not port_margin < z < self.length_m-port_margin for z in self.entry_positions_m):
            raise ValueError('entry ports must clear throat and mouth planes')
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
        return 1 + len(self.entry_sites)

    @property
    def solver_entry_sites(self):
        """Physical representatives; the complete CAD retains every driver."""
        if self.solver_symmetry == 'off':
            return self.entry_sites
        return [site for site in self.entry_sites if site[2][0] >= 0 and site[2][1] >= 0]

    @property
    def entry_sites(self):
        """Canonical source identities and outward axes used by CAD and solver."""
        directions = [('positive', (1, 0, 0)), ('negative', (-1, 0, 0))]
        if self.entry_layout == 'four_driver_ring':
            directions += [('positive_y', (0, 1, 0)), ('negative_y', (0, -1, 0))]
        if self.driver_tilt_deg:
            angle = math.radians(self.driver_tilt_deg)
            directions = [(name, (x * math.cos(angle), y * math.cos(angle), -math.sin(angle)))
                          for name, (x, y, _) in directions]
        return [(f'entry_{index}_{side}', entry, axis)
                for index, entry in enumerate(self.entry_positions_m)
                for side, axis in directions]


def build_geometry(design: HornGeometry):
    """Return experimental air regions, material parts and semantic source locations."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()

    mm = 1000.0
    length, throat, mouth, wall = (v * mm for v in (
        design.length_m, design.throat_radius_m, design.mouth_radius_m, design.wall_m))
    unported_air, material = horn_solids(design)
    front_air = unported_air
    air_regions, parts, sources = {}, {}, []
    for label, entry, axis in design.entry_sites:
        z = entry * mm
        driver_entry=entry+design.driver_axial_offset_m
        driver_z=driver_entry*mm
        local_radius = entry_support_radius(design, unported_air, driver_entry, axis) * mm
        duct_end = local_radius + wall + design.port_length_m * mm
        diaphragm = duct_end + design.front_depth_m * mm
        direction = cq.Vector(*axis)
        def cylinder(radius, start, depth, axial=z):
            return cq.Solid.makeCylinder(radius, depth, cq.Vector(axis[0] * start, axis[1] * start, axial + axis[2] * start), direction)
        tube = cylinder(design.port_radius_m * mm, 0, duct_end)
        chamber = cylinder(design.front_radius_m * mm, duct_end, design.front_depth_m * mm,driver_z)
        if design.driver_tilt_deg:
            envelope = cylinder(design.front_radius_m * mm + wall, duct_end - wall,
                                design.front_depth_m * mm + 2 * wall, driver_z).BoundingBox()
            if (design.throat_body is None and envelope.zmin <= 0) or envelope.zmax >= length:
                raise ValueError('tilted front chamber must clear throat and mouth planes')
        front_air = front_air.fuse(tube, chamber)
        material = material.fuse(
            cylinder(design.port_radius_m * mm + wall, 0, duct_end + wall),
            cylinder(design.front_radius_m * mm + wall, duct_end - wall, design.front_depth_m * mm + 2 * wall,driver_z))
        # Open mounting aperture; the missing driver is an explicit reserved volume.
        material = material.cut(cylinder(design.front_radius_m * mm, diaphragm, wall * 2,driver_z))
        rear_start = diaphragm + wall
        rear_air = cylinder(design.front_radius_m * mm, rear_start, design.rear_depth_m * mm,driver_z)
        rear_cup = cylinder(design.front_radius_m * mm + wall, rear_start,
                            design.rear_depth_m * mm + wall,driver_z).cut(rear_air)
        air_regions[f"rear_{label}"] = rear_air
        parts[f"rear_cup_{label}"] = rear_cup
        sources.append({"id": label, "front_center_m": [axis[0] * diaphragm / mm, axis[1] * diaphragm / mm, driver_entry + axis[2] * diaphragm / mm],
                        "rear_center_m": [axis[0] * rear_start / mm, axis[1] * rear_start / mm, driver_entry + axis[2] * rear_start / mm],
                        "motion_axis": list(axis), "radius_m": design.front_radius_m})
    parts["horn"] = material.cut(front_air).clean()
    air_regions["front"] = front_air.clean()
    if design.throat_body is not None:
        body = throat_body_solid(design)
        occupied = list(air_regions.values()) + list(parts.values())
        for source in sources:
            occupied.append(cq.Solid.makeCylinder(source['radius_m'] * mm, wall,
                cq.Vector(*[v * mm for v in source['front_center_m']]),
                cq.Vector(*source['motion_axis'])))
        if any(body.intersect(shape).Volume() > 1e-3 for shape in occupied):
            raise ValueError('mid chamber, air or reserved diaphragm intersects the throat body')
    for name, solid in {**parts, **air_regions}.items():
        if not solid.isValid() or solid.Volume() <= 0 or len(solid.Solids()) != 1:
            raise ValueError(f"geometry kernel produced an invalid or disconnected solid: {name}")
    verify_front_chamber_back_walls(design, front_air, parts["horn"], unported_air=unported_air)
    if design.profile_sections or design.driver_axial_offset_m or design.driver_tilt_deg:
        for air in air_regions.values():
            if any(air.intersect(part).Volume() > 1e-3 for part in parts.values()):
                raise ValueError('freeform air intersects material')
        solids=list(parts.values())
        if any(a.intersect(b).Volume()>1e-3 for i,a in enumerate(solids) for b in solids[i+1:]):
            raise ValueError('freeform driver chamber parts intersect')
    return air_regions, parts, sources


def throat_body_solid(design: HornGeometry):
    """Assembly-coordinate package used for both clearance and BEM geometry."""
    if design.throat_body is None:
        raise ValueError('no throat body declared')
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    body = design.throat_body
    return cq.Solid.makeCylinder(body.radius_m * 1000, body.depth_m * 1000,
        cq.Vector(0, 0, -body.depth_m * 1000), cq.Vector(0, 0, 1))


def verify_front_chamber_back_walls(design, front_air, horn, *, unported_air=None):
    """Check material behind the chamber back faces independently of STL closure."""
    from .cad_runtime import load_cadquery
    cq=load_cadquery();mm=1000.;wall=design.wall_m*mm
    # Stay away from coincident faces while testing almost the entire wall thickness.
    inset=min(wall/1000.,1e-3);depth=wall-2*inset;checks=[]
    if unported_air is None and (design.profile_sections or design.driver_tilt_deg):
        unported_air=horn_solids(design)[0]
    for label,entry,axis in design.entry_sites:
        driver_entry=entry+design.driver_axial_offset_m
        local_radius=entry_support_radius(design,unported_air,driver_entry,axis)
        start=(local_radius+design.port_length_m)*mm+inset
        nominal=cq.Solid.makeCylinder(design.front_radius_m*mm,depth,cq.Vector(axis[0]*start,axis[1]*start,driver_entry*mm + axis[2]*start),cq.Vector(*axis))
        # The port and any intended intersection with horn air remain open.
        required=nominal.cut(front_air);volume=required.Volume()
        missing=required.cut(horn).Volume()
        if volume<=1e-9 or missing>max(1e-6,volume*1e-7):
            raise ValueError('front chamber back wall is not covered by material')
        checks.append({'source_id':label,'required_volume_m3':volume/1e9,'missing_volume_m3':missing/1e9})
    return checks


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
        mouth_cap=mouth_face(design,regions['front'])
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
        if design.throat_body is not None:
            directory = output / 'reference'
            directory.mkdir()
            path = directory / 'throat-body.step'
            body = throat_body_solid(design)
            cq.exporters.export(body, str(path))
            files.append({'path': path.relative_to(output).as_posix(),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'size_bytes': path.stat().st_size})
            state['throat_body'] = {'kind': 'ideal_rigid_driver_envelope', 'print_part': False,
                'clearance_checked': True, 'file': path.relative_to(output).as_posix(),
                'volume_m3': body.Volume() / 1e9,
                'limitations': ['Cylindrical package approximation; mounting holes, terminals and internal driver acoustics are not represented.']}
        state.update(status="complete", design=design.model_dump(mode="json"),
                     driver_count=design.driver_count, sources=sources, files=files,
                     mouth_interface={'center_m':[v/1000 for v in mouth_cap.Center().toTuple()],
                                      'area_m2':mouth_cap.Area()/1e6},
                     front_chamber_back_walls_verified=True,
                     air_volume_m3={name: cad_volume(design, solid) / 1e9 for name, solid in regions.items()},
                     material_volume_m3={name: cad_volume(design, solid) / 1e9 for name, solid in parts.items()},
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


CURVATURE_ELEMENTS = 48
SOURCE_AREA_RELATIVE_TOLERANCE = .01


def estimated_curved_tetrahedra(design, region, volume):
    """Heuristic size-field estimate for the supported conical/cylindrical family."""
    import math
    h=design.mesh_size_m
    local=lambda radius:min(h,2*math.pi*radius/CURVATURE_ELEMENTS)
    if region!='front':return 6*volume/local(design.front_radius_m)**3
    slope=(design.mouth_radius_m-design.throat_radius_m)/design.length_m
    split=h*CURVATURE_ELEMENTS/(2*math.pi)
    fine_high=min(design.mouth_radius_m,split)
    cells=0.
    if fine_high>design.throat_radius_m:
        cells+=CURVATURE_ELEMENTS**3/(8*math.pi**2*slope)*math.log1p((fine_high-design.throat_radius_m)/design.throat_radius_m)
    coarse_low=max(design.throat_radius_m,split)
    if design.mouth_radius_m>coarse_low:
        cells+=math.pi*((design.mouth_radius_m-coarse_low)*(design.mouth_radius_m**2+design.mouth_radius_m*coarse_low+coarse_low**2))/(3*slope*h**3)
    count=design.driver_count-1
    cells+=count*math.pi*design.front_radius_m**2*design.front_depth_m/local(design.front_radius_m)**3
    port_length=design.port_length_m+design.wall_m+(2*design.front_radius_m+abs(design.driver_axial_offset_m))*slope
    cells+=count*math.pi*design.port_radius_m**2*port_length/local(design.port_radius_m)**3
    shape_factor=1.
    if design.profile_sections:
        # Axial taper is not azimuthal anisotropy. A circular section has aspect
        # one even when its radius changes strongly between axial stations.
        shape_factor=max((max(section.radial_scales)/min(section.radial_scales))**3
                         for section in design.profile_sections)
    return max(6*cells*shape_factor,6*volume/h**3)


def source_area_checks(path, radii):
    """Independently measure saved linear facets against the circular CAD boundaries."""
    import math
    import meshio
    import numpy as np
    mesh=meshio.read(path)
    checks=[]
    for name,radius in radii.items():
        tag=int(mesh.field_data[name][0]);area=0.
        for cell,physical in zip(mesh.cells,mesh.cell_data['gmsh:physical']):
            if cell.type=='triangle':
                vertices=mesh.points[cell.data[np.asarray(physical)==tag]]
                area+=float(np.linalg.norm(np.cross(vertices[:,1]-vertices[:,0],vertices[:,2]-vertices[:,0]),axis=1).sum()/2)
        exact=math.pi*radius**2
        error=abs(area/exact-1)
        if not math.isfinite(error) or error>SOURCE_AREA_RELATIVE_TOLERANCE:
            raise ValueError(f'{name} mesh area differs from CAD by more than one percent')
        checks.append({'name':name,'cad_area_m2':exact,'mesh_area_m2':area,'relative_area_error':error})
    return checks


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
    if design.solver_symmetry == 'xy':
        from .reduced_geometry import mesh_quarter_geometry
        return mesh_quarter_geometry(output, geometry, design)
    directory = output / "analysis"
    directory.mkdir(exist_ok=False)
    report = {"schema_version": 1, "status": "running", "units": "m",
              "design_hash": design.content_hash, "accuracy": "not_converged", "regions": [],
              "size_policy":{"maximum_m":design.mesh_size_m,
                  "minimum_m":min(design.mesh_size_m,math.pi*min(design.throat_radius_m,design.port_radius_m,design.front_radius_m)/CURVATURE_ELEMENTS),
                  "curvature_elements_per_revolution":CURVATURE_ELEMENTS,
                  "source_area_relative_tolerance":SOURCE_AREA_RELATIVE_TOLERANCE}}
    report['workload_limit_tetrahedra_per_region']=design.maximum_tetrahedra
    try:
        for region, expected_volume in geometry["air_volume_m3"].items():
            estimated=estimated_curved_tetrahedra(design,region,expected_volume)
            if estimated > design.maximum_tetrahedra:
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
                volume = imported_volume(design,gmsh.model.occ.getMass(3, volumes[0][1]),directory/f'{region}-imported.step')
                if not math.isclose(volume, expected_volume, rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError("CAD-to-analysis volume or unit mismatch")
                expected = {}
                if region == "front":
                    expected["throat_source"] = ([0, 0, 0], design.throat_radius_m, "source")
                    mouth=geometry.get('mouth_interface',{'center_m':[0,0,design.length_m],
                          'area_m2':math.pi*design.mouth_radius_m**2})
                    expected["mouth_interface"] = (mouth['center_m'], math.sqrt(mouth['area_m2']/math.pi), "radiation_interface")
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
                layered = None
                if region != 'front' and design.rear_axial_mesh_size_m is not None:
                    from .rear_meshing import layered_rear_volume
                    name = next(iter(tags))
                    volumes, tags[name], walls, layered = layered_rear_volume(
                        gmsh, volumes, tags[name][0], source['motion_axis'],
                        design.rear_depth_m, design.rear_axial_mesh_size_m)
                gmsh.model.addPhysicalGroup(3, [volumes[0][1]], 1, name="air_" + region)
                groups = []
                for physical_tag, (name, surfaces) in enumerate(tags.items(), start=10):
                    gmsh.model.addPhysicalGroup(2, surfaces, physical_tag, name=name)
                    groups.append({"name": name, "tag": physical_tag, "role": expected[name][2]})
                gmsh.model.addPhysicalGroup(2, walls, 99, name="rigid_walls")
                groups.append({"name": "rigid_walls", "tag": 99, "role": "rigid_wall"})
                gmsh.option.setNumber("Mesh.MeshSizeMin", report["size_policy"]["minimum_m"])
                gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", CURVATURE_ELEMENTS)
                gmsh.option.setNumber("Mesh.MeshSizeMax", design.mesh_size_m)
                gmsh.option.setNumber("Mesh.ElementOrder", 1)
                gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
                gmsh.option.setNumber("Mesh.Binary", 0)
                if layered is not None:
                    from .rear_meshing import check_layered_workload
                    check_layered_workload(gmsh, layered, design.maximum_tetrahedra)
                gmsh.model.mesh.generate(3)
                tetrahedra, _ = gmsh.model.mesh.getElementsByType(4)
                if len(tetrahedra)>design.maximum_tetrahedra:
                    raise ValueError("actual tetrahedral workload exceeds the mesh budget")
                if not len(tetrahedra):
                    raise ValueError("mesher produced no tetrahedra")
                qualities = gmsh.model.mesh.getElementQualities(tetrahedra)
                if min(qualities) <= 0:
                    raise ValueError("mesh contains inverted or degenerate tetrahedra")
                path = directory / f"{region}.msh"
                gmsh.write(str(path))
                areas=source_area_checks(path,{name:values[1] for name,values in expected.items()})
                report["regions"].append({"id": region, "estimated_tetrahedra":estimated, "source_area_checks":areas, "path": path.relative_to(output).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "volume_m3": volume,
                    "tetrahedra": len(tetrahedra), "minimum_quality": float(min(qualities)), "boundaries": groups})
                if layered is not None:
                    report['regions'][-1]['layered_rear_mesh'] = layered
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
