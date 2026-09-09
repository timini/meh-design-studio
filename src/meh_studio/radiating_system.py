"""Compile a generated horn plus ideal rigid exterior for FEM/BEM experiments."""
from pathlib import Path
import threading
import math

from .boundary_lab import BoundaryLabRuntime, _execute, _read_json, _write_json, _termination_guard, sha256
from .generated_system import HornSources, compile_interior_system
from .geometry import HornGeometry
from .radiation_geometry import export_exterior, surface_integrity, verify_exterior_groups


def compile_radiating_system(geometry_directory: Path, sources: HornSources, output: Path,
                             runtime: BoundaryLabRuntime, *, exterior_mesh_size_m: float = .02,
                             timeout_s: float = 600) -> dict:
    if (not isinstance(exterior_mesh_size_m, (int,float)) or not math.isfinite(exterior_mesh_size_m)
            or not .01 <= exterior_mesh_size_m <= .05):
        raise ValueError('exterior mesh target must be between 10 and 50 mm')
    if not isinstance(timeout_s, (int,float)) or not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError('timeout must be positive and finite')
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("run radiating compilation in a worker process, not a background thread")
    report = {'status': 'running'}
    with _termination_guard(report) as activate:
        try:
            return _compile_radiating_system(geometry_directory, sources, output, runtime,
                exterior_mesh_size_m=exterior_mesh_size_m, timeout_s=timeout_s,
                report=report, activate=activate)
        except BaseException as exc:
            if 'geometry_hash' in report:
                if report['status'] != 'cancelled':
                    report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                _write_json(Path(output).resolve()/'compilation.json', report)
            raise


def _compile_radiating_system(geometry_directory, sources, output, runtime, *, exterior_mesh_size_m,
                              timeout_s, report, activate):
    runtime_identity = runtime.verify()
    output = Path(output).resolve()
    report = compile_interior_system(geometry_directory, sources, output, _report=report, _activate=activate)
    report.update(status="running", mouth_load="coupled_exterior_bem", runtime=runtime_identity)
    _write_json(output / "compilation.json", report)
    try:
        activate()
        geometry = _read_json(Path(geometry_directory) / "geometry.json")
        design = HornGeometry.model_validate(geometry["design"])
        if design.content_hash != report["geometry_hash"]:
            raise ValueError("geometry changed during compilation")
        exterior = export_exterior(design, output / "exterior", exterior_mesh_size_m)
        destination = output / "meshes/exterior.msh"
        _execute([str(Path(runtime.python).absolute()), "-I", "-m", "blab.cli", "conform-interface",
                  str(output / "meshes/front.msh"), str(output / "exterior/exterior.msh"), str(destination),
                  "--fem-interface", "mouth_interface", "--bem-interface", "mouth_interface"],
                 Path(runtime.checkout), output / "conform-interface.log", timeout_s)
        integrity = surface_integrity(destination)
        verify_exterior_groups(destination, output / "meshes/front.msh")
        if abs(integrity["enclosed_volume_m3"] / exterior["cad_volume_m3"] - 1) > .02:
            raise ValueError("conforming changed the exterior volume beyond the supported tolerance")
        project = _read_json(output / "project.blab.json")
        system = project["physical_system"]
        system["metadata"]["generated_mesh_sha256"]["mesh:exterior"] = integrity["sha256"]
        system["meshes"].append({"id": "mesh:exterior", "name": "exterior", "file": "meshes/exterior.msh",
            "purpose": "bem_surface", "scale_to_m": 1.0, "translation_m": [0, 0, 0]})
        system["regions"].append({"id": "region:exterior", "name": "Exterior air", "kind": "unbounded_air",
            "density_kg_per_m3": sources.density_kg_m3, "sound_speed_m_per_s": sources.sound_speed_m_s,
            "mesh_ids": ["mesh:exterior"], "volume_groups": [], "loss_model": {}})
        for boundary in system["boundaries"]:
            if boundary["id"] == "boundary:front:mouth_interface":
                boundary["kind"] = "interface"
        for name, tag, kind in (("mouth_interface", 10, "interface"), ("rigid_exterior", 99, "rigid")):
            system["boundaries"].append({"id": "boundary:exterior:" + name, "name": name,
                "region_id": "region:exterior", "kind": kind, "parameters": {},
                "group": {"mesh_id": "mesh:exterior", "dimension": 2, "name": name, "tag": tag}})
        system["interfaces"] = [{"id": "interface:mouth", "name": "Horn mouth",
            "bounded_boundary_id": "boundary:front:mouth_interface",
            "unbounded_boundary_id": "boundary:exterior:mouth_interface", "coordinate_tolerance_m": 1e-8}]
        if runtime.verify() != runtime_identity:
            raise ValueError("runtime changed during interface preparation")
        _write_json(output / "project.blab.json", project)
        report.update(status="complete", project_sha256=sha256(output / "project.blab.json"),
            exterior_surface=integrity, exterior_mesh_size_m=exterior_mesh_size_m,
            exterior_report_sha256=sha256(output / "exterior/exterior.json"), exterior_identity={"design_hash": design.content_hash,
                "cad_geometry_sha256": exterior["cad_geometry_sha256"]}, limitations=[
                "Ideal rigid mounting package, not measured driver geometry",
                "Throat piston has no rear acoustic load or compression-driver internals",
                "FEM/BEM and frequency refinement remain unqualified",
                "No nonlinear, structural, physical speaker or print validation"])
    except BaseException as exc:
        if report["status"] != "cancelled":
            report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output / "compilation.json", report)
    return report
