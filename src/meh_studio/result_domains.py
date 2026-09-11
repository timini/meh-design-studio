"""Bind saved physical axes to project sources and independently read mesh data."""
from contextlib import redirect_stdout
import io
from pathlib import Path

import meshio
import numpy as np

TARGETS = {
    "fem_nodal_pressure": "domain:fem-volume",
    "bem_boundary_pressure": "domain:bem-boundary",
    "bem_boundary_neumann": "domain:bem-boundary",
    "diaphragm_velocity": "components:electrodynamic-transducers",
    "voice_coil_current": "components:electrodynamic-transducers",
    "radiation_impedance": "components:radiators",
}
OBSERVATIONS = {"acoustic:pressure:horizontal-polar": "observation:horizontal-polar",
                "acoustic:pressure:vertical-polar": "observation:vertical-polar",
                "acoustic:pressure:sphere": "observation:sphere"}


def physical_volume_tags(mesh, groups, mesh_id):
    """Resolve declared volume names against the independently read source mesh."""
    tags = set()
    for group in groups:
        if group["mesh_id"] != mesh_id:
            continue
        if group.get("dimension", 3) != 3:
            raise ValueError("FEM volume group must have dimension 3")
        tag, name = group.get("tag"), group.get("name")
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("FEM physical volume name must not be empty")
            field = np.asarray(mesh.field_data.get(name, []))
            if field.shape != (2,) or field.dtype.kind not in "iu" or field[1] != 3:
                raise ValueError("FEM physical volume name is missing or has the wrong dimension")
            resolved = int(field[0])
            if tag is not None and tag != resolved:
                raise ValueError("FEM physical volume name and tag disagree")
            tag = resolved
        if type(tag) is not int or tag <= 0:
            raise ValueError("FEM physical volume requires a positive tag or resolvable name")
        tags.add(tag)
    return tags


def load_domains(root: Path, manifest: dict, system: dict, meshes: dict, *, project: dict | None = None) -> dict:
    from .boundary_lab import _contained, _read_json, sha256
    if project is None:
        project = _read_json(_contained(root, manifest["project_file"]))
    preferences = project.get("project_preferences", {})
    metadata = _read_json(_contained(root, manifest["domains_metadata_file"]))
    items = metadata["domains"]
    domains = {d["id"]: d for d in items}
    if len(domains) != len(items):
        raise ValueError("duplicate result domain identities")
    mesh_contracts = {}
    project_meshes = {m["id"]: m for m in system["meshes"]}
    with np.load(_contained(root, manifest["domains_file"]), allow_pickle=False) as arrays:
        result = {}
        for identity, domain in domains.items():
            if any(not isinstance(domain.get(key),dict) for key in ("coordinates","topology","metadata")):
                raise ValueError("domain coordinates, topology and metadata must be objects")
            coordinates = {k: arrays[v] for k, v in domain["coordinates"].items()}
            topology = {k: arrays[v] for k, v in domain["topology"].items()}
            for values in (*(v for k, v in coordinates.items() if k in {"points_m", "angle_deg"}), *topology.values()):
                if values.dtype.kind in "fc" and not np.all(np.isfinite(values)):
                    raise ValueError("non-finite result domain coordinates")
            entry = {"coordinates": coordinates, "topology": topology, "metadata": domain["metadata"]}
            if identity in {"domain:fem-volume", "domain:bem-boundary"}:
                ids = domain["metadata"]["mesh_ids"]
                purpose = "fem_volume" if identity == "domain:fem-volume" else "bem_surface"
                if set(ids) != {mid for mid, m in meshes.items() if m["purpose"] == purpose} or len(set(ids)) != len(ids):
                    raise ValueError("domain mesh identities differ from the project")
                points = []
                counts = []
                face_count = 0
                expected_faces = []
                face_counts = []
                expected_tetra = []
                tetra_counts = []
                for mid in ids:
                    if mid not in mesh_contracts:
                        path = Path(meshes[mid]["file"])
                        if sha256(path) != meshes[mid]["sha256"]:
                            raise ValueError("source mesh changed before domain verification")
                        try:
                            with redirect_stdout(io.StringIO()):
                                raw = meshio.read(path)
                        except (Exception, SystemExit) as exc:
                            raise ValueError("cannot read source mesh for domain verification") from exc
                        mesh_contracts[mid] = raw
                    raw = mesh_contracts[mid]
                    transform = project_meshes[mid]
                    xyz = raw.points * transform.get("scale_to_m", 1.0) + np.asarray(transform.get("translation_m", [0,0,0]))
                    triangles = np.vstack([c.data for c in raw.cells if c.type == "triangle"]) if any(c.type == "triangle" for c in raw.cells) else np.empty((0,3),dtype=int)
                    if purpose == "fem_volume":
                        regions = [r for r in system["regions"] if r["kind"] == "bounded_air" and mid in r["mesh_ids"]]
                        if len(regions) != 1 or regions[0]["mesh_ids"] != [mid]:
                            raise ValueError("pinned Boundary Lab requires one FEM mesh per bounded region and one owning region per mesh")
                        tags = physical_volume_tags(raw, regions[0].get("volume_groups", []), mid)
                        physical = raw.cell_data.get("gmsh:physical", [])
                        if not tags or len(physical) != len(raw.cells):
                            raise ValueError("FEM source requires selected physical volume tags")
                        for block, block_tags in zip(raw.cells,physical):
                            if np.asarray(block_tags).shape != (len(block.data),):
                                raise ValueError("source cell tags do not align with connectivity")
                            if block.dim == 3 and block.type not in {"tetra","tetra10"} and np.any(np.isin(block_tags,list(tags))):
                                raise ValueError("selected FEM volume contains unsupported non-tetrahedral cells")
                        selected = [c.data[np.isin(t, list(tags))] for c,t in zip(raw.cells,physical)
                                    if c.type in {"tetra", "tetra10"} and np.any(np.isin(t,list(tags)))]
                        if not selected or len({c.shape[1] for c in selected}) != 1:
                            raise ValueError("FEM source requires supported same-order tetrahedra")
                        cells = np.vstack(selected)
                        active = np.unique(cells)
                        if np.any(active < 0) or np.any(active >= len(xyz)):
                            raise ValueError("FEM connectivity references nonexistent source nodes")
                        compact = np.full(len(xyz),-1,dtype=int)
                        compact[active] = np.arange(len(active))
                        expected_tetra.append(compact[cells] + sum(counts))
                        tetra_counts.append(len(cells))
                        xyz = xyz[active]
                    expected_faces.append(triangles + sum(counts))
                    triangle_count = len(triangles)
                    face_counts.append(triangle_count)
                    points.append(xyz)
                    counts.append(len(xyz))
                    face_count += triangle_count
                expected_points = np.vstack(points)
                actual_points = coordinates["points_m"]
                if actual_points.shape != expected_points.shape or not np.allclose(actual_points, expected_points, rtol=1e-6, atol=1e-9):
                    raise ValueError("result domain nodes differ from the hashed source mesh")
                if domain["metadata"].get("node_counts") != counts:
                    raise ValueError("domain node counts differ from the source mesh")
                entry["node_counts"] = counts
                if identity == "domain:fem-volume":
                    if len({c.shape[1] for c in expected_tetra}) != 1:
                        raise ValueError("mixed FEM element orders are unsupported")
                    cells = np.vstack(expected_tetra)
                    actual = topology.get("tetrahedra")
                    if actual is None or actual.dtype.kind not in "iu" or not np.array_equal(actual,cells[:,:4]):
                        raise ValueError("FEM tetrahedral connectivity differs from the source mesh")
                    if cells.shape[1] == 10:
                        quadratic = topology.get("tetrahedra10")
                        if quadratic is None or quadratic.dtype.kind not in "iu" or not np.array_equal(quadratic,cells):
                            raise ValueError("quadratic FEM connectivity differs from the source mesh")
                    elif "tetrahedra10" in topology:
                        raise ValueError("unexpected quadratic FEM connectivity")
                    if (domain["metadata"].get("tetra_counts") != tetra_counts
                            or domain["metadata"].get("tetra_offsets") != [sum(tetra_counts[:i]) for i in range(len(ids))]
                            or domain["metadata"].get("element_order") != (2 if cells.shape[1] == 10 else 1)):
                        raise ValueError("FEM topology inventory differs from source meshes")
                if identity == "domain:bem-boundary":
                    triangles = topology["triangles"]
                    if triangles.dtype.kind not in "iu" or triangles.shape != (face_count, 3) or not np.array_equal(triangles, np.vstack(expected_faces)):
                        raise ValueError("result domain face count differs from the source mesh")
                    entry["face_count"] = face_count
                    entry["face_counts"] = face_counts
            if identity in OBSERVATIONS.values():
                distance = float(preferences.get("polar_observation_distance_m", 1.0))
                step = float(preferences.get("polar_angle_step_deg", 10.0))
                if not np.isfinite(distance) or distance <= 0 or not np.isfinite(step) or step <= 0 or 360/step > 100000:
                    raise ValueError("unsupported observation grid")
                if identity == "observation:sphere":
                    angle = min(max(float(preferences.get("balloon_angle_precision_deg", 2.5)), .5), 15.)
                    count = max(int(round(41253/angle**2)), 1)
                    indices = np.arange(count, dtype=float)
                    z = 1 - 2*(indices+.5)/count
                    radius = np.sqrt(np.maximum(0, 1-z*z))
                    phi = np.pi*(3-np.sqrt(5))*indices
                    expected = distance*np.column_stack((radius*np.cos(phi),radius*np.sin(phi),z))
                else:
                    angles = np.clip(np.arange(-180.,180.+.5*step,step,dtype=np.float32),-180.,180.)
                    radians = np.deg2rad(angles.astype(float))
                    side, axis = np.sin(radians), np.cos(radians)
                    expected = distance*np.column_stack((side, np.zeros_like(side), axis) if identity.endswith("horizontal-polar")
                                                         else (np.zeros_like(side), side, axis))
                    if not np.array_equal(coordinates.get("angle_deg"), angles):
                        raise ValueError("observation angles differ from the project")
                if coordinates["points_m"].shape != expected.shape or not np.allclose(coordinates["points_m"], expected, rtol=1e-6, atol=1e-9):
                    raise ValueError("observation coordinates differ from the project grid")
            if identity in {"components:radiators", "components:electrodynamic-transducers"}:
                ids = coordinates["component_id"].tolist()
                expected = [c["id"] for c in system["components"] if identity == "components:radiators"
                            or c["kind"] == "electrodynamic_transducer"]
                if ids != expected:
                    raise ValueError("result domain component identities differ from the project")
            result[identity] = entry
    return result


def check_quantity_domain(quantity: dict, values: np.ndarray, domains: dict):
    name = quantity["quantity"]
    target = OBSERVATIONS.get(quantity["id"]) if name == "exterior_pressure" else TARGETS[name]
    if target is None or quantity.get("target_id") != target or target not in domains:
        raise ValueError("quantity references the wrong or missing physical domain")
    domain = domains[target]
    if name in {"fem_nodal_pressure", "bem_boundary_pressure", "exterior_pressure"}:
        points = domain["coordinates"]["points_m"]
        if points.ndim != 2 or points.shape[1] != 3 or values.shape[1] != len(points):
            raise ValueError("quantity sample count differs from its physical domain")
    if name in {"fem_nodal_pressure", "bem_boundary_pressure", "bem_boundary_neumann"}:
        metadata = quantity.get("metadata", {})
        if "mesh_ids" in metadata and metadata["mesh_ids"] != domain["metadata"]["mesh_ids"]:
            raise ValueError("quantity mesh order differs from its physical domain")
        if name == "bem_boundary_pressure" and "vertex_counts" in metadata and metadata["vertex_counts"] != domain["node_counts"]:
            raise ValueError("quantity vertex counts differ from the source mesh")
        if name == "bem_boundary_neumann" and "face_counts" in metadata and metadata["face_counts"] != domain["face_counts"]:
            raise ValueError("quantity face counts differ from the source mesh")
    if name == "fem_nodal_pressure" and quantity["metadata"]["node_counts"] != domain["node_counts"]:
        raise ValueError("quantity node counts differ from the source mesh")
    if name == "bem_boundary_neumann" and values.shape[1] != domain["face_count"]:
        raise ValueError("quantity face count differs from its physical domain")
    if name in {"radiation_impedance", "voice_coil_current", "diaphragm_velocity"}:
        ids = domain["coordinates"]["component_id"].tolist()
        if values.shape[-1] != len(ids):
            raise ValueError("quantity component count differs from its domain")
        if name != "radiation_impedance" and quantity["metadata"]["component_ids"] != ids:
            raise ValueError("quantity component order differs from its domain")
