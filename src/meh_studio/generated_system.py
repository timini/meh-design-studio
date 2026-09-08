"""Compile generated air domains to a small-signal interior FEM experiment.

The mouth termination is an anechoic tube approximation, not free-field radiation.
The throat is an ideal piston with no rear acoustic load. No source qualifies here.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil

from .boundary_lab import _contained, _read_json, _write_json, sha256
from .domain import Positive, Record, SourceModel
from .geometry import HornGeometry


class HornSources(Record):
    throat: SourceModel
    side: SourceModel
    density_kg_m3: Positive = 1.21
    sound_speed_m_s: Positive = 343.0


def compile_interior_system(geometry_directory: Path, sources: HornSources, output: Path, *, _report=None, _activate=None) -> dict:
    try:
        return _compile_interior_system(geometry_directory, sources, output, _report=_report, _activate=_activate)
    except (KeyError, TypeError, AttributeError, IndexError, EOFError) as exc:
        raise ValueError(f"invalid geometry compilation artifact: {exc}") from exc


def _verify_boundary_groups(path: Path, region: dict):
    import contextlib
    import io
    import meshio
    diagnostics = io.StringIO()
    with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
        try:
            mesh = meshio.read(path, file_format="gmsh")
        except (meshio.ReadError, SystemExit) as exc:
            raise ValueError("invalid generated mesh artifact: " + diagnostics.getvalue().strip()) from exc
    expected = {b["name"]: (b["tag"], 2) for b in region["boundaries"]}
    expected["air_" + region["id"]] = (1, 3)
    actual = {name: tuple(map(int, group)) for name, group in mesh.field_data.items()}
    if actual != expected or len(set(expected.values())) != len(expected):
        raise ValueError("mesh physical-group names/tags differ from boundary declarations")
    used = set()
    for cell, tags in zip(mesh.cells, mesh.cell_data.get("gmsh:physical", [])):
        used.update((int(tag), cell.dim) for tag in tags)
    if used != set(expected.values()):
        raise ValueError("mesh physical groups have missing or undeclared elements")


def _compile_interior_system(geometry_directory: Path, sources: HornSources, output: Path, *, _report=None, _activate=None) -> dict:
    root = Path(geometry_directory).resolve()
    geometry = _read_json(root / "geometry.json")
    mesh = _read_json(root / "analysis/mesh.json")
    design = HornGeometry.model_validate(geometry["design"])
    if (geometry.get("status") != "complete" or mesh.get("status") != "complete"
            or design.content_hash != geometry.get("design_hash")
            or design.content_hash != mesh.get("design_hash") or mesh.get("units") != "m"):
        raise ValueError("complete matching geometry and metre-scale meshes are required")
    for source, radius in ((sources.throat, design.throat_radius_m), (sources.side, design.front_radius_m)):
        if not math.isclose(source.sd_m2, math.pi * radius**2, rel_tol=1e-6):
            raise ValueError("source effective area must match its ideal diaphragm disk")
    expected_sources = {f"entry_{pair}_{side}" for pair in range(len(design.entry_positions_m))
                        for side in ("positive", "negative")}
    source_locations = {s["id"]: s for s in geometry["sources"]}
    if set(source_locations) != expected_sources or len(source_locations) != len(geometry["sources"]):
        raise ValueError("geometry source inventory differs from the selected family")
    expected_regions = {"front"} | {"rear_" + name for name in expected_sources}
    regions = {r["id"]: r for r in mesh["regions"]}
    if set(regions) != expected_regions or len(regions) != len(mesh["regions"]):
        raise ValueError("mesh region inventory differs from the selected family")
    paths = {}
    for name, region in regions.items():
        paths[name] = _contained(root, region["path"])
        if sha256(paths[name]) != region["sha256"]:
            raise ValueError("source mesh identity mismatch")
        expected = {"rigid_walls"}
        if name == "front":
            expected |= {"throat_source", "mouth_interface"} | {s + "_front_source" for s in expected_sources}
        else:
            expected.add(name.removeprefix("rear_") + "_rear_source")
        boundaries = region["boundaries"]
        if {b["name"] for b in boundaries} != expected or len(boundaries) != len(expected):
            raise ValueError("mesh boundary inventory differs from the selected family")
        _verify_boundary_groups(paths[name], region)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {} if _report is None else _report
    report.update({"schema_version": 1, "status": "running", "evidence": "experimental_prediction_input",
              "geometry_hash": design.content_hash, "sources_hash": sources.content_hash,
              "qualified": False, "mouth_load": "plane_wave_tube_termination",
              "throat_rear_load": "none", "mesh_accuracy": "not_converged"})
    try:
        if _activate is not None:
            _activate()
        (output / "meshes").mkdir()
        system = {"id": "system:generated-meh", "name": "Experimental generated MEH interior",
                  "model_version": 1, "metadata": {}, "meshes": [], "regions": [],
                  "boundaries": [], "components": [], "excitation_ports": [], "interfaces": []}
        for name, region in regions.items():
            relative = f"meshes/{name}.msh"
            shutil.copyfile(paths[name], output / relative)
            if sha256(output / relative) != region["sha256"]:
                raise ValueError("mesh changed while copying")
            _verify_boundary_groups(output / relative, region)
            mesh_id, region_id = f"mesh:{name}", f"region:{name}"
            system["meshes"].append({"id": mesh_id, "name": name, "file": relative,
                "purpose": "fem_volume", "scale_to_m": 1.0, "translation_m": [0, 0, 0]})
            system["regions"].append({"id": region_id, "name": name, "kind": "bounded_air",
                "density_kg_per_m3": sources.density_kg_m3, "sound_speed_m_per_s": sources.sound_speed_m_s,
                "mesh_ids": [mesh_id], "volume_groups": [{"mesh_id": mesh_id, "dimension": 3,
                    "name": "air_" + name, "tag": 1}], "loss_model": {"bulk_loss_factor": 0.0}})
            for boundary in region["boundaries"]:
                label = boundary["name"]
                kind = ("rigid" if label == "rigid_walls" else
                        "plane_wave_tube_termination" if label == "mouth_interface" else "moving")
                system["boundaries"].append({"id": f"boundary:{name}:{label}", "name": label,
                    "kind": kind, "region_id": region_id, "parameters": {},
                    "group": {"mesh_id": mesh_id, "dimension": 2, "name": label, "tag": boundary["tag"]}})
        system["metadata"]["generated_mesh_sha256"] = {
            f"mesh:{name}": region["sha256"] for name, region in regions.items()}
        assignments = [("throat", sources.throat, [0, 0, 1], ["boundary:front:throat_source"])]
        for name in sorted(expected_sources):
            assignments.append((name, sources.side, [1 if name.endswith("positive") else -1, 0, 0],
                [f"boundary:front:{name}_front_source", f"boundary:rear_{name}:{name}_rear_source"]))
        for name, source, axis, boundary_ids in assignments:
            component = "component:" + name
            system["components"].append({"id": component, "name": name, "kind": "electrodynamic_transducer",
                "boundary_ids": boundary_ids, "parameters": {"re_ohm": source.re_ohm, "le_h": source.le_h,
                    "bl_n_per_a": source.bl_n_a, "mmd_kg": source.mmd_kg, "cms_m_per_n": source.cms_m_n,
                    "rms_n_s_per_m": source.rms_ns_m, "motion_axis": axis, "motion_profile": "rigid_translation"}})
            system["excitation_ports"].append({"id": "excitation:" + name, "name": name + " native 2.83 V",
                "kind": "voltage", "component_id": component})
        project = {"schema_version": 9, "physical_system": system, "symmetry": "off",
                   "stitch_exterior_meshes": False, "imported_meshes": [], "observation_planes": [],
                   "component_channel_by_id": {c["id"]: c["name"] for c in system["components"]},
                   "project_preferences": {"freq_min_hz": 100, "freq_max_hz": 2000, "freq_count": 10,
                       "polar_angle_step_deg": 5.0, "polar_observation_distance_m": 1.0,
                       "spherical_sampling_enabled": False}}
        _write_json(output / "project.blab.json", project)
        _write_json(output / "sources.json", sources.model_dump(mode="json"))
        report.update(status="complete", project_sha256=sha256(output / "project.blab.json"),
                      driver_count=len(assignments), limitations=[
                          "Anechoic tube termination is not exterior horn radiation",
                          "Throat piston omits compression-driver internals and rear load",
                          "Ideal source disks, no breakup, nonlinear or measured qualification",
                          "Mesh convergence and independent accuracy remain unestablished"])
    except BaseException as exc:
        if report["status"] != "cancelled":
            report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output / "compilation.json", report)
    return report
