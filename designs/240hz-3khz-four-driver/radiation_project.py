"""Compile retained R1 meshes into a prescribed-velocity FEM/BEM experiment.

This has four independent unit-normal-velocity sources, a rigid throat, and
sealed rigid rear packages. It is not a commercial-driver speaker prediction.
"""
import argparse
import json
from pathlib import Path
import shutil

from meh_studio.boundary_lab import sha256, _read_json, _write_json
from meh_studio.radiation_geometry import surface_integrity


def compile_project(front_directory: Path, exterior_directory: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "qualified": False,
              "compiler_sha256": sha256(Path(__file__))}
    try:
        front = _read_json(front_directory / "mesh.json")
        exterior = _read_json(exterior_directory / "exterior.json")
        conformance = _read_json(exterior_directory / "conformance.json")
        front_path = front_directory / "front.msh"
        exterior_path = exterior_directory / "conformed.msh"
        if any(item.get("status") != "complete" for item in (front, exterior, conformance)):
            raise ValueError("mesh preparation is incomplete")
        front_hash, exterior_hash = sha256(front_path), sha256(exterior_path)
        if front_hash != front["files"][0]["sha256"] or front_hash != conformance["front_mesh_sha256"]:
            raise ValueError("front mesh provenance mismatch")
        if exterior_hash != conformance["conformed_mesh_sha256"]:
            raise ValueError("exterior mesh provenance mismatch")
        if front["source_step_sha256"] != exterior["source_front_air_sha256"]:
            raise ValueError("front and exterior geometries differ")
        if conformance.get("exact_triangle_membership_match") is not True:
            raise ValueError("interface membership was not verified")
        integrity = surface_integrity(exterior_path)
        if abs(integrity["enclosed_volume_m3"] / exterior["cad_volume_m3"] - 1) > .02:
            raise ValueError("conformed exterior volume differs from CAD by over 2%")
        names = {b["name"] for b in front["boundaries"]}
        if names != {"throat", "mouth", "rigid_walls", "mid_1", "mid_2", "mid_3", "mid_4"}:
            raise ValueError("expected the actual four-around-one-ring boundary inventory")
        system = dict(id="system:r1-prescribed-radiation", name="R1 prescribed velocity radiation",
                      model_version=1, meshes=[], regions=[], boundaries=[], components=[],
                      excitation_ports=[], interfaces=[], metadata={"generated_mesh_sha256": {
                          "mesh:front": front_hash, "mesh:exterior": exterior_hash}})
        (output / "meshes").mkdir()
        for name, path, digest, purpose, kind in (
            ("front", front_path, front_hash, "fem_volume", "bounded_air"),
            ("exterior", exterior_path, exterior_hash, "bem_surface", "unbounded_air")):
            dest = output / "meshes" / (name + ".msh")
            shutil.copyfile(path, dest)
            if sha256(dest) != digest:
                raise ValueError("mesh changed during copy")
            system["meshes"].append(dict(id="mesh:"+name, name=name, file="meshes/"+dest.name,
                purpose=purpose, scale_to_m=1., translation_m=[0,0,0]))
            system["regions"].append(dict(id="region:"+name, name=name, kind=kind,
                mesh_ids=["mesh:"+name], density_kg_per_m3=1.21, sound_speed_m_per_s=343.,
                loss_model={}, volume_groups=([dict(mesh_id="mesh:front", dimension=3,
                name="front_air", tag=1)] if name == "front" else [])))
        for b in front["boundaries"]:
            name = b["name"]
            system["boundaries"].append(dict(id="boundary:front:"+name, name=name,
                region_id="region:front", kind=("interface" if name == "mouth" else
                "moving" if name.startswith("mid_") else "rigid"), parameters={},
                group=dict(mesh_id="mesh:front", dimension=2, name=name, tag=b["tag"])))
        for name, tag, kind in (("mouth_interface",10,"interface"),("rigid_exterior",99,"rigid")):
            system["boundaries"].append(dict(id="boundary:exterior:"+name, name=name,
                region_id="region:exterior", kind=kind, parameters={},
                group=dict(mesh_id="mesh:exterior", dimension=2, name=name, tag=tag)))
        system["interfaces"] = [dict(id="interface:mouth", name="R1 mouth",
            bounded_boundary_id="boundary:front:mouth", unbounded_boundary_id="boundary:exterior:mouth_interface",
            coordinate_tolerance_m=1e-8)]
        for i in range(1,5):
            name = f"mid_{i}"
            system["components"].append(dict(id="component:"+name, name=name,
                kind="ideal_velocity_source", boundary_ids=["boundary:front:"+name],
                parameters={"motion_profile":"uniform"}))
            system["excitation_ports"].append(dict(id="excitation:"+name, name=name+" unit normal velocity",
                component_id="component:"+name, kind="normal_velocity"))
        project = dict(schema_version=9, physical_system=system, symmetry="off",
            stitch_exterior_meshes=False, imported_meshes=[], observation_planes=[],
            component_channel_by_id={c["id"]:c["name"] for c in system["components"]},
            project_preferences=dict(freq_min_hz=240, freq_max_hz=3000, freq_count=17,
                polar_angle_step_deg=15., polar_observation_distance_m=2., spherical_sampling_enabled=False))
        _write_json(output / "project.blab.json", project)
        report.update(status="complete", project_sha256=sha256(output / "project.blab.json"),
            exterior_surface=integrity, input_sha256={str(p):sha256(p) for p in (
                front_directory/"mesh.json", exterior_directory/"exterior.json", exterior_directory/"conformance.json")},
            limitations=["Unit normal velocity basis; not voltage-driven commercial drivers",
                "Rigid throat; no tweeter output", "No actual cone or rear acoustic coupling",
                "Single mesh; no radiation convergence or physical validation"],
            source_mesh_areas_m2={v["name"]:v["mesh_area_m2"] for v in front["source_area_checks"] if v["name"].startswith("mid_")})
    except BaseException as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output / "compilation.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("front_directory", type=Path)
    parser.add_argument("exterior_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(compile_project(args.front_directory, args.exterior_directory, args.output), indent=2))
