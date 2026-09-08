"""Generate an independent uniform-tube benchmark, not a horn design.

The exact mechanical load for a uniform piston in a perfectly terminated tube
is rho*c*area. A square cross section avoids curved-surface area approximation.
"""
import argparse
from pathlib import Path
import json
import hashlib

import gmsh

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--mesh-size-m", type=float, default=.01)
args = parser.parse_args()
if not .002 <= args.mesh_size_m <= .02:
    parser.error("mesh size must be between 2 and 20 mm")
args.output.mkdir(parents=True, exist_ok=False)
gmsh.initialize()
try:
    gmsh.option.setNumber("General.Terminal", 0)
    volume = gmsh.model.occ.addBox(-.02, -.02, 0, .04, .04, .2)
    gmsh.model.occ.synchronize()
    walls = []
    for dim, tag in gmsh.model.getBoundary([(3, volume)], oriented=False):
        z = gmsh.model.occ.getCenterOfMass(dim, tag)[2]
        if abs(z) < 1e-10: gmsh.model.addPhysicalGroup(2, [tag], 10, name="piston")
        elif abs(z-.2) < 1e-10: gmsh.model.addPhysicalGroup(2, [tag], 11, name="termination")
        else: walls.append(tag)
    gmsh.model.addPhysicalGroup(2, walls, 99, name="walls")
    gmsh.model.addPhysicalGroup(3, [volume], 1, name="air")
    gmsh.option.setNumber("Mesh.MeshSizeMin", args.mesh_size_m)
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.mesh_size_m)
    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
    gmsh.option.setNumber("Mesh.Binary", 0)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(args.output / "tube.msh"))
finally:
    gmsh.finalize()
parameters = {"re_ohm": 6.0, "le_h": .0001, "bl_n_per_a": 4.0, "mmd_kg": .005,
              "cms_m_per_n": .0005, "rms_n_s_per_m": 1.0,
              "motion_axis": [0, 0, 1], "motion_profile": "rigid_translation"}
mesh_id, region_id = "mesh:tube", "region:tube"
system = {"id": "system:analytic-tube", "name": "Independent uniform tube reference", "model_version": 1,
    "metadata": {"generated_mesh_sha256": {mesh_id: hashlib.sha256((args.output/"tube.msh").read_bytes()).hexdigest()}}, "interfaces": [],
    "meshes": [{"id": mesh_id, "name": "tube", "file": "tube.msh", "purpose": "fem_volume",
                "scale_to_m": 1.0, "translation_m": [0, 0, 0]}],
    "regions": [{"id": region_id, "name": "tube", "kind": "bounded_air", "mesh_ids": [mesh_id],
                 "density_kg_per_m3": 1.21, "sound_speed_m_per_s": 343.0,
                 "volume_groups": [{"mesh_id": mesh_id, "dimension": 3, "name": "air", "tag": 1}],
                 "loss_model": {"bulk_loss_factor": 0.0}}],
    "components": [{"id": "driver", "name": "synthetic piston", "kind": "electrodynamic_transducer",
                    "boundary_ids": ["piston"], "parameters": parameters}],
    "excitation_ports": [{"id": "voltage", "name": "Native 2.83 V", "kind": "voltage", "component_id": "driver"}],
    "boundaries": [{"id": name, "name": name, "kind": kind, "region_id": region_id, "parameters": {},
                    "group": {"mesh_id": mesh_id, "dimension": 2, "name": name, "tag": tag}}
                   for name, tag, kind in (("piston",10,"moving"),("termination",11,"plane_wave_tube_termination"),("walls",99,"rigid"))]}
project = {"schema_version": 9, "physical_system": system, "symmetry": "off", "stitch_exterior_meshes": False,
           "imported_meshes": [], "observation_planes": [], "component_channel_by_id": {"driver": "main"},
           "project_preferences": {"freq_min_hz": 500, "freq_max_hz": 2000, "freq_count": 3,
                                   "polar_angle_step_deg": 5.0, "polar_observation_distance_m": 1.0,
                                   "spherical_sampling_enabled": False}}
(args.output / "reference.json").write_text(json.dumps({"kind": "analytic_uniform_tube", "area_m2": .0016,
    "density_kg_m3": 1.21, "sound_speed_m_s": 343.0, "mechanical_load_ns_m": 1.21*343*.0016,
    "mesh_size_m": args.mesh_size_m, "source_parameters": parameters}, indent=2), encoding="utf-8")

project["physical_system"]["metadata"]["analytic_reference_sha256"] = hashlib.sha256((args.output/"reference.json").read_bytes()).hexdigest()
(args.output / "project.blab.json").write_text(json.dumps(project, indent=2), encoding="utf-8")
