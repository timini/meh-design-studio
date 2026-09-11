"""Compile generated air domains to a small-signal interior FEM experiment.

The mouth termination is an anechoic tube approximation, not free-field radiation.
The throat is an ideal piston with no rear acoustic load. No source qualifies here.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil
from pydantic import model_validator

from .boundary_lab import _contained, _read_json, _write_json, sha256
from .domain import Positive, Record, SourceModel
from .geometry import HornGeometry


class HornSources(Record):
    throat: SourceModel
    side: SourceModel
    density_kg_m3: Positive = 1.21
    sound_speed_m_s: Positive = 343.0

    @model_validator(mode='after')
    def throat_only_transform(self):
        if self.side.ideal_outlet_area_m2 is not None:
            raise ValueError('ideal outlet transform is supported only for the throat; mids have explicit front and rear air')
        return self


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
        if not math.isclose(source.outlet_area_m2, math.pi * radius**2, rel_tol=1e-6):
            raise ValueError("source effective area must match its projected diaphragm disk")
    axes = {name: list(axis) for name, _, axis in design.entry_sites}
    expected_sources = set(axes)
    source_locations = {s["id"]: s for s in geometry["sources"]}
    if set(source_locations) != expected_sources or len(source_locations) != len(geometry["sources"]):
        raise ValueError("geometry source inventory differs from the selected family")
    if any(source_locations[name]['motion_axis'] != axis for name, axis in axes.items()):
        raise ValueError('geometry source motion axes differ from the selected family')
    if mesh.get('solver_symmetry', 'off') != design.solver_symmetry:
        raise ValueError('mesh reduction differs from the selected design')
    if design.solver_symmetry == 'xy':
        partition_path = root / 'analysis/partition.json'
        if sha256(partition_path) != mesh.get('partition_sha256'):
            raise ValueError('quarter CAD partition identity mismatch')
        partition = _read_json(partition_path)
        if partition.get('mode') != 'xy':
            raise ValueError('quarter CAD partition mode mismatch')
        full_files = {item['path']: item['sha256'] for item in geometry['files']}
        if set(partition['full_cad_sha256']) != set(geometry['air_volume_m3']):
            raise ValueError('quarter partition must bind every physical air solid')
        for name, digest in partition['full_cad_sha256'].items():
            relative = f'air/{name}.step'
            if digest != full_files[relative] or sha256(_contained(root, relative)) != digest:
                raise ValueError('full CAD changed after quarter partition')
        for item in partition['cad_files'].values():
            if sha256(_contained(root, item['path'])) != item['sha256']:
                raise ValueError('quarter CAD changed after meshing')
        expected_sources = {name for name, _, _ in design.solver_entry_sites}
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
            assignments.append((name, sources.side, axes[name],
                [f"boundary:front:{name}_front_source", f"boundary:rear_{name}:{name}_rear_source"]))
        for name, source, axis, boundary_ids in assignments:
            component = "component:" + name
            if source.ideal_outlet_area_m2 is not None:
                system['metadata'].setdefault('ideal_outlet_transforms', {})[component] = {
                    'source_sha256': source.content_hash, 'diaphragm_area_m2': source.sd_m2,
                    'outlet_area_m2': source.outlet_area_m2,
                    'outlet_velocity_per_diaphragm_velocity': source.outlet_velocity_ratio,
                    'model': 'lossless_zero_length_area_transformer'}
            system["components"].append({"id": component, "name": name, "kind": "electrodynamic_transducer",
                "boundary_ids": boundary_ids, "parameters": source.outlet_piston_parameters() |
                    {"motion_axis": axis, "motion_profile": "rigid_translation"}})
            system["excitation_ports"].append({"id": "excitation:" + name, "name": name + " native 2.83 V",
                "kind": "voltage", "component_id": component})
        project = {"schema_version": 9, "physical_system": system, "symmetry": design.solver_symmetry,
                   "stitch_exterior_meshes": False, "imported_meshes": [], "observation_planes": [],
                   "component_channel_by_id": {c["id"]: c["name"] for c in system["components"]},
                   "project_preferences": {"freq_min_hz": 100, "freq_max_hz": 2000, "freq_count": 10,
                       "polar_angle_step_deg": 5.0, "polar_observation_distance_m": 1.0,
                       "spherical_sampling_enabled": False}}
        if design.solver_symmetry == 'xy':
            from .driver_symmetry import driver_symmetry_from_meshes
            manifest = {'meshes': [{'id': f'mesh:{name}', 'file': str(output / f'meshes/{name}.msh'),
                                    'sha256': region['sha256']} for name, region in regions.items()]}
            inferred = driver_symmetry_from_meshes(project, manifest)
            for component, value in inferred.items():
                throat = component == 'component:throat'
                if (value['physical_driver_orbit_count'] != (1 if throat else 2)
                        or value['surface_completion_factor'] != (4 if throat else 2)):
                    raise ValueError('saved source patches do not represent the physical driver inventory')
            if sum(value['physical_driver_orbit_count'] for value in inferred.values()) != design.driver_count:
                raise ValueError('quarter driver count differs from the complete physical horn')
            report['solver_symmetry'] = 'xy'
            report['driver_symmetry'] = inferred
            report['represented_component_count'] = len(assignments)
            report['partition_sha256'] = mesh['partition_sha256']
        _write_json(output / "project.blab.json", project)
        _write_json(output / "sources.json", sources.model_dump(mode="json"))
        report.update(status="complete" if _report is None else "running", project_sha256=sha256(output / "project.blab.json"),
                      driver_count=design.driver_count, limitations=[
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
