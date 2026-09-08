"""Closed idealised exterior envelope for experimental FEM/BEM coupling."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .boundary_lab import _write_json, sha256
from .geometry import HornGeometry, build_geometry


def surface_integrity(path: Path) -> dict:
    """Check closed oriented triangular topology before exposing a BEM input."""
    import gmsh
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
        if not len(triangles) or len(triangles) // 3 > 8000:
            raise ValueError("exterior mesh must contain 1–8000 linear triangles")
        lookup = {int(tag): i for i, tag in enumerate(tags)}
        faces = np.array([lookup[int(tag)] for tag in triangles]).reshape(-1, 3)
        points = np.asarray(coordinates).reshape(-1, 3)
        if not np.all(np.isfinite(points)):
            raise ValueError("surface coordinates must be finite")
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
        return {"triangles": len(faces), "nodes": len(tags), "open_edges": 0,
                "orientation_errors": 0, "enclosed_volume_m3": volume, "sha256": sha256(path)}
    finally:
        gmsh.finalize()


def verify_exterior_groups(path: Path):
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
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "design_hash": design.content_hash,
              "mesh_size_m": mesh_size_m, "accuracy": "not_converged", "print_part": False,
              "units": {"step": "mm", "mesh": "m"}}
    _write_json(output / "exterior.json", report)
    try:
        air, parts, sources = build_geometry(design)
        solids = list(air.values()) + list(parts.values())
        for source in sources:
            centre = cq.Vector(*[x * 1000 for x in source["front_center_m"]])
            solids.append(cq.Solid.makeCylinder(source["radius_m"] * 1000, design.wall_m * 1000,
                                                centre, cq.Vector(*source["motion_axis"])))
        body = solids[0].fuse(*solids[1:]).clean()
        if not body.isValid() or len(body.Solids()) != 1:
            raise ValueError("exterior envelope is not one valid solid")
        cq.exporters.export(body, str(output / "envelope.step"))
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.option.setString("Geometry.OCCTargetUnit", "M")
            imported = gmsh.model.occ.importShapes(str(output / "envelope.step"))
            disk = gmsh.model.occ.addDisk(0, 0, design.length_m, design.mouth_radius_m, design.mouth_radius_m)
            gmsh.model.occ.fragment(imported, [(2, disk)])
            gmsh.model.occ.synchronize()
            volumes = gmsh.model.getEntities(3)
            if len(volumes) != 1:
                raise ValueError("exterior envelope import must contain one volume")
            exact_volume = body.Volume() / 1e9
            if not math.isclose(gmsh.model.occ.getMass(3, volumes[0][1]), exact_volume, rel_tol=1e-6):
                raise ValueError("exterior CAD unit or volume mismatch")
            interface, walls = [], []
            for dim, tag in gmsh.model.getBoundary(volumes, oriented=False):
                centre = gmsh.model.occ.getCenterOfMass(dim, tag)
                area = gmsh.model.occ.getMass(dim, tag)
                if (gmsh.model.getType(dim, tag) == "Plane" and math.dist(centre, [0, 0, design.length_m]) < 1e-7
                        and math.isclose(area, math.pi * design.mouth_radius_m**2, rel_tol=1e-6)):
                    interface.append(tag)
                else:
                    walls.append(tag)
            if len(interface) != 1 or not walls:
                raise ValueError("exterior mouth interface is not unique")
            gmsh.model.addPhysicalGroup(2, interface, 10, name="mouth_interface")
            gmsh.model.addPhysicalGroup(2, walls, 99, name="rigid_exterior")
            gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size_m)
            gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size_m)
            gmsh.option.setNumber("Mesh.ElementOrder", 1)
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.model.mesh.generate(2)
            gmsh.write(str(output / "exterior.msh"))
        finally:
            gmsh.finalize()
        integrity = surface_integrity(output / "exterior.msh")
        if not math.isclose(integrity["enclosed_volume_m3"], exact_volume, rel_tol=.02):
            raise ValueError("exterior surface volume differs from CAD by more than 2 percent")
        report.update(status="complete", surface=integrity, cad_volume_m3=exact_volume,
                      cad_sha256=sha256(output / "envelope.step"),
                      limitations=["Ideal rigid driver package fills, not detailed driver geometry",
                                   "Surface topology checks do not establish acoustic convergence",
                                   "Envelope is an acoustic domain, not a printable material part"])
    except BaseException as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output / "exterior.json", report)
    return report
