"""Closed idealised exterior envelope for experimental FEM/BEM coupling."""
from __future__ import annotations

import math
import hashlib
import re
import sys
import importlib.metadata
from pathlib import Path

import numpy as np

from .boundary_lab import _write_json, sha256
from .geometry import HornGeometry, build_geometry, throat_body_solid
from .waveguide_profile import mouth_face, cad_volume, imported_volume


def meshing_runtime_identity():
    return {'python':sys.version,
        'packages':{name:importlib.metadata.version(name) for name in ('cadquery','cadquery-ocp','gmsh','numpy')},
        'source_sha256':{name:sha256(Path(__file__).with_name(name)) for name in ('geometry.py','reduced_geometry.py','radiation_geometry.py','waveguide_profile.py','interface_coordinates.py','native_mouth_conform.py')}}


def step_geometry_sha256(path: Path) -> str:
    """Hash the STEP data section, excluding timestamp-bearing header metadata."""
    payload = path.read_text(encoding='utf-8')
    if payload.count('DATA;') != 1:
        raise ValueError('expected a single STEP data section')
    data = payload.split('DATA;', 1)[1]
    if 'ENDSEC;' not in data:
        raise ValueError('unterminated STEP data section')
    data = data.split('ENDSEC;', 1)[0].strip()
    # OCCT also increments a process-local counter in its default product labels.
    data = re.sub(r"'Open CASCADE STEP translator ([0-9.]+) [0-9]+'",
                  r"'Open CASCADE STEP translator \1'", data)
    return hashlib.sha256(data.encode()).hexdigest()


def surface_integrity(path: Path, *, maximum_triangles: int = 8000, symmetry: str = 'off') -> dict:
    """Check closed oriented triangular topology before exposing a BEM input."""
    import gmsh
    if type(maximum_triangles) is not int or not 1 <= maximum_triangles <= 64_000:
        raise ValueError('exterior workload limit must be an integer in [1, 64000]')
    if symmetry not in ('off', 'xy'):
        raise ValueError('generated exterior supports off or xy symmetry')
    if gmsh.isInitialized():
        raise ValueError("surface inspection requires an isolated Gmsh process")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.open(str(path))
        types, _, _ = gmsh.model.mesh.getElements(2)
        if any(kind != 2 for kind in types):
            raise ValueError("exterior must contain only linear triangle surface elements")
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        _, triangles = gmsh.model.mesh.getElementsByType(2)
        if not len(triangles) or len(triangles) // 3 > maximum_triangles:
            raise ValueError(f"exterior mesh must contain 1–{maximum_triangles} linear triangles")
        lookup = {int(tag): i for i, tag in enumerate(tags)}
        faces = np.array([lookup[int(tag)] for tag in triangles]).reshape(-1, 3)
        points = np.asarray(coordinates).reshape(-1, 3)
        if not np.all(np.isfinite(points)):
            raise ValueError("surface coordinates must be finite")
        native_triangles, native_nodes = len(faces), len(tags)
        reduction = {}
        if symmetry == 'xy':
            native_edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
            _, counts = np.unique(np.sort(native_edges, axis=1), axis=0, return_counts=True)
            reduction = {'symmetry': 'xy', 'native_open_edges': int(np.sum(counts == 1)),
                         'validation': 'closed_oriented_fourfold_reflection',
                         'native_mesh_unchanged': True}
            points, faces, snap = _reflect_quarter_surface(points, faces)
            reduction['maximum_plane_roundoff_snap_m'] = snap
        edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
        _, inverse, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
        signs = np.where(edges[:, 0] < edges[:, 1], 1, -1)
        if np.any(counts != 2) or np.any(np.bincount(inverse, weights=signs) != 0):
            raise ValueError("exterior surface is open, nonmanifold or inconsistently oriented")
        # Faces must connect through edges, and each vertex must have one fan.
        edge_faces = {}
        vertex_faces = {}
        for face_id, face in enumerate(faces):
            for vertex in face:
                vertex_faces.setdefault(int(vertex), set()).add(face_id)
            for left, right in zip(face, np.roll(face, -1)):
                edge_faces.setdefault(tuple(sorted((int(left), int(right)))), []).append(face_id)
        adjacent = [set() for _ in faces]
        vertex_adjacent = {vertex: {} for vertex in vertex_faces}
        for edge, (left, right) in edge_faces.items():
            adjacent[left].add(right)
            adjacent[right].add(left)
            for vertex in edge:
                vertex_adjacent[vertex].setdefault(left, set()).add(right)
                vertex_adjacent[vertex].setdefault(right, set()).add(left)
        def connected(members, links):
            seen, pending = set(), [next(iter(members))]
            while pending:
                current = pending.pop()
                if current not in seen:
                    seen.add(current)
                    pending.extend(links[current] - seen)
            return seen == members
        if not connected(set(range(len(faces))), adjacent):
            raise ValueError("exterior surface must be connected through shared edges")
        if any(not connected(members, vertex_adjacent[vertex])
               for vertex, members in vertex_faces.items()):
            raise ValueError("exterior contains a nonmanifold vertex")
        a, b, c = (points[faces[:, i]] for i in range(3))
        if np.any(np.linalg.norm(np.cross(b-a, c-a), axis=1) <= 1e-14):
            raise ValueError("exterior contains degenerate triangles")
        volume = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)
        if volume <= 0 or not math.isfinite(volume):
            raise ValueError("exterior orientation or enclosed volume is invalid")
        return {"triangles": native_triangles, "nodes": native_nodes, "open_edges": 0,
                "orientation_errors": 0, "enclosed_volume_m3": volume / (4 if symmetry == 'xy' else 1),
                "sha256": sha256(path), **reduction}
    finally:
        gmsh.finalize()


def _reflect_quarter_surface(points, faces):
    """Diagnostic only: share the same native vertex across its mirror cuts."""
    points = points.copy()
    near = np.abs(points[:, :2]) < 1e-12
    snap = float(np.max(np.abs(points[:, :2][near]))) if near.any() else 0.
    points[:, :2][near] = 0.
    if points[:, :2].min() < 0:
        raise ValueError('quarter exterior extends outside the positive XY domain')
    lookup, vertices, reflected = {}, [], []
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        indices = []
        for index, point in enumerate(points):
            key = (index, 0 if point[0] == 0 else sx, 0 if point[1] == 0 else sy)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(point * [sx, sy, 1])
            indices.append(lookup[key])
        mirrored = np.asarray(indices)[faces]
        reflected.append(mirrored[:, [0, 2, 1]] if sx * sy < 0 else mirrored)
    return np.asarray(vertices), np.concatenate(reflected), snap


def verify_exterior_groups(path: Path, front_mesh: Path | None = None):
    import contextlib
    import io
    import meshio
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            mesh = meshio.read(path, file_format='gmsh')
        except (meshio.ReadError, SystemExit) as exc:
            raise ValueError('invalid conformed exterior mesh') from exc
    expected = {'mouth_interface': (10, 2), 'rigid_exterior': (99, 2)}
    if {name: tuple(map(int, value)) for name, value in mesh.field_data.items()} != expected:
        raise ValueError('conformed exterior physical-group names/tags differ')
    physical = mesh.cell_data.get('gmsh:physical', [])
    if len(physical) != len(mesh.cells) or any(cell.type != 'triangle' for cell in mesh.cells):
        raise ValueError('conformed exterior must cover only physical triangles')
    used = set()
    for cell, tags in zip(mesh.cells, physical):
        if len(tags) != len(cell.data):
            raise ValueError('conformed exterior physical coverage differs')
        used.update(map(int, tags))
    if used != {10, 99}:
        raise ValueError('conformed exterior has missing or unexpected physical elements')
    if front_mesh is not None:
        from collections import Counter
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                front = meshio.read(front_mesh, file_format='gmsh')
            except (meshio.ReadError, SystemExit) as exc:
                raise ValueError('invalid authoritative FEM mesh') from exc
        mouth = front.field_data.get('mouth_interface')
        if mouth is None or tuple(map(int, mouth))[1] != 2:
            raise ValueError('authoritative FEM mouth group is missing')
        def facets(surface, tag):
            triangles = []
            for cell, tags in zip(surface.cells, surface.cell_data.get('gmsh:physical', [])):
                if cell.type == 'triangle':
                    for face in cell.data[np.asarray(tags) == tag]:
                        triangles.append(tuple(sorted(tuple(point) for point in np.round(surface.points[face], 12))))
            return Counter(triangles)
        expected = facets(front, int(mouth[0]))
        selected = facets(mesh, 10)
        if not expected or selected != expected or any(face in expected for face in facets(mesh, 99)):
            raise ValueError('conformed mouth triangle membership differs from authoritative FEM interface')



def export_exterior(design: HornGeometry, output: Path, mesh_size_m: float = .02) -> dict:
    """Fill the omitted drivers to make a closed outer acoustic envelope.

    These rigid fills model an ideal mounting package; they are not print parts.
    """
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    import gmsh
    if not math.isfinite(mesh_size_m) or not .01 <= mesh_size_m <= .05:
        raise ValueError("exterior mesh target must be between 10 and 50 mm")
    if gmsh.isInitialized():
        raise ValueError("exterior generation requires an isolated Gmsh process")
    compiler_runtime = meshing_runtime_identity()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "design_hash": design.content_hash,
              "mesh_size_m": mesh_size_m, "accuracy": "not_converged", "print_part": False,
              "units": {"step": "mm", "mesh": "m"}, "compiler_runtime":compiler_runtime}
    raw_limit = design.maximum_raw_exterior_triangles or design.maximum_exterior_triangles
    report['workload_limit_triangles'] = raw_limit
    if design.maximum_raw_exterior_triangles is not None:
        report['final_workload_limit_triangles'] = design.maximum_exterior_triangles
    _write_json(output / "exterior.json", report)
    try:
        air, parts, sources = build_geometry(design)
        cap=mouth_face(design,air['front'])
        solids = list(air.values()) + list(parts.values())
        if design.throat_body is not None:
            solids.append(throat_body_solid(design))
            report['throat_body'] = {'kind': 'ideal_rigid_driver_envelope',
                'dimensions': design.throat_body.model_dump(mode='json'), 'print_part': False}
        for source in sources:
            centre = cq.Vector(*[x * 1000 for x in source["front_center_m"]])
            solids.append(cq.Solid.makeCylinder(source["radius_m"] * 1000, design.wall_m * 1000,
                                                centre, cq.Vector(*source["motion_axis"])))
        body = solids[0].fuse(*solids[1:]).clean()
        if not body.isValid() or len(body.Solids()) != 1:
            raise ValueError("exterior envelope is not one valid solid")
        if design.solver_symmetry == 'xy':
            from .reduced_geometry import quarter_envelope, adaptive_area
            body, cap, checks = quarter_envelope(design, body, air['front'])
            report['symmetry_partition'] = {'mode': 'xy', 'mirror_relative_volume_errors': checks}
            cap_area = adaptive_area(cap)
        else:
            cap_area = cap.Area() / 1e6
        cap_center = [x / 1000 for x in cap.Center().toTuple()]
        cq.exporters.export(body, str(output / "envelope.step"))
        cq.exporters.export(cap, str(output / 'mouth.step'))
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.option.setString("Geometry.OCCTargetUnit", "M")
            imported = gmsh.model.occ.importShapes(str(output / "envelope.step"))
            mouth_entities=gmsh.model.occ.importShapes(str(output/'mouth.step'))
            gmsh.model.occ.fragment(imported, mouth_entities)
            gmsh.model.occ.synchronize()
            volumes = gmsh.model.getEntities(3)
            if len(volumes) != 1:
                raise ValueError("exterior envelope import must contain one volume")
            exact_volume = cad_volume(design,body) / 1e9
            imported=imported_volume(design,gmsh.model.occ.getMass(3, volumes[0][1]),output/'fragmented.step')
            if not math.isclose(imported, exact_volume, rel_tol=1e-6):
                raise ValueError("exterior CAD unit or volume mismatch")
            interface, walls, cuts = [], [], []
            for dim, tag in gmsh.model.getBoundary(volumes, oriented=False):
                centre = gmsh.model.occ.getCenterOfMass(dim, tag)
                area = gmsh.model.occ.getMass(dim, tag)
                if (gmsh.model.getType(dim, tag) == "Plane" and math.dist(centre, cap_center) < 1e-7
                        and (design.solver_symmetry == 'xy' or math.isclose(area, cap_area, rel_tol=1e-6))):
                    interface.append(tag)
                elif design.solver_symmetry == 'xy' and gmsh.model.getType(dim, tag) == 'Plane' and any(
                        max(abs(gmsh.model.getBoundingBox(dim, tag)[axis]),
                            abs(gmsh.model.getBoundingBox(dim, tag)[axis + 3])) < 1e-6 for axis in (0, 1)):
                    cuts.append(tag)
                else:
                    walls.append(tag)
            if len(interface) != 1 or not walls:
                raise ValueError("exterior mouth interface is not unique")
            if design.solver_symmetry == 'xy' and len(cuts) != 2:
                raise ValueError('quarter exterior must have two omitted mirror cut faces')
            gmsh.model.addPhysicalGroup(2, interface, 10, name="mouth_interface")
            gmsh.model.addPhysicalGroup(2, walls, 99, name="rigid_exterior")
            if design.profile_sections or design.solver_symmetry == 'xy':
                # Independent coarse polygons of a curved rim can disagree even
                # when both originate from the same STEP face. Resolve the rim
                # before conform-interface replaces the mouth with FEM facets.
                # Only the shared edge is refined; the exterior face target and
                # all interface/volume acceptance tolerances remain unchanged.
                rim_spacing = min(mesh_size_m, design.mesh_size_m) / 2
                rim_curves = gmsh.model.getBoundary([(2, interface[0])], oriented=False)
                for dim, curve in rim_curves:
                    length = gmsh.model.occ.getMass(dim, curve)
                    gmsh.model.mesh.setTransfiniteCurve(curve, max(3, math.ceil(length / rim_spacing) + 1))
                report['mouth_rim_sampling'] = {'maximum_target_spacing_m': rim_spacing,
                                               'curve_count': len(rim_curves)}
            gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size_m)
            gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size_m)
            gmsh.option.setNumber("Mesh.ElementOrder", 1)
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.model.mesh.generate(2)
            gmsh.write(str(output / "exterior.msh"))
        finally:
            gmsh.finalize()
        integrity = surface_integrity(output / "exterior.msh",maximum_triangles=raw_limit,
                                      symmetry=design.solver_symmetry)
        if not math.isclose(integrity["enclosed_volume_m3"], exact_volume, rel_tol=.02):
            raise ValueError("exterior surface volume differs from CAD by more than 2 percent")
        if meshing_runtime_identity()!=compiler_runtime:
            raise ValueError("host meshing runtime changed during export")
        report.update(status="complete", surface=integrity, cad_volume_m3=exact_volume,
                      cad_sha256=sha256(output / "envelope.step"),
                      cad_geometry_sha256=step_geometry_sha256(output / "envelope.step"),
                      limitations=["Ideal rigid driver package fills, not detailed driver geometry",
                                   "Surface topology checks do not establish acoustic convergence",
                                   "Envelope is an acoustic domain, not a printable material part"])
    except BaseException as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output / "exterior.json", report)
    return report
