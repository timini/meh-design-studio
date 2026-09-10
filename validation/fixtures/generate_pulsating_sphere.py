"""Uniformly pulsating sphere: independent exterior acoustic reference, no horn."""
from pathlib import Path
import json,hashlib,argparse
import gmsh
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--sphere-angle-deg',type=float)
args=parser.parse_args()
if args.sphere_angle_deg is not None and not 2.5<=args.sphere_angle_deg<=15:parser.error('sphere angle must be 2.5–15 degrees')
root=args.output;root.mkdir(parents=True,exist_ok=False)
a=.02;h=.003
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gmsh.initialize()
try:
 gmsh.option.setNumber('General.Terminal',0)
 sphere=gmsh.model.occ.addSphere(0,0,0,a);gmsh.model.occ.synchronize()
 faces=[tag for dim,tag in gmsh.model.getBoundary([(3,sphere)],oriented=False)]
 gmsh.model.addPhysicalGroup(2,faces,10,name='sphere_motion')
 gmsh.option.setNumber('Mesh.MeshSizeMin',h);gmsh.option.setNumber('Mesh.MeshSizeMax',h)
 gmsh.option.setNumber('Mesh.ElementOrder',1);gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
 gmsh.model.mesh.generate(2);gmsh.write(str(root/'sphere.msh'))
finally:gmsh.finalize()
reference={'kind':'analytic_pulsating_sphere','radius_m':a,'mesh_size_m':h,'velocity_coefficient_m_per_s':1.,'density_kg_m3':1.21,'sound_speed_m_s':343.,'phasor_convention':'exp(-i omega t)','frequencies_hz':[350.,2000.,5000.,7500.],'maximum_relative_complex_error':.02,'formula':'p(r) = rho*c*(-i*k*a)/(1-i*k*a)*(a/r)*exp(i*k*(r-a))*v','rms_interpretation':False,'generator_sha256':sha(Path(__file__))}
if args.sphere_angle_deg is not None:reference['sphere_angle_deg']=args.sphere_angle_deg
(root/'reference.json').write_text(json.dumps(reference,indent=2)+'\n')
system={'id':'system:sphere-reference','name':'Uniformly pulsating sphere','model_version':1,'metadata':{'generated_mesh_sha256':{'mesh:sphere':sha(root/'sphere.msh')},'analytic_reference_sha256':sha(root/'reference.json')},'interfaces':[],
 'meshes':[{'id':'mesh:sphere','name':'sphere','file':'sphere.msh','purpose':'bem_surface','scale_to_m':1.,'translation_m':[0,0,0]}],
 'regions':[{'id':'region:exterior','name':'Exterior','kind':'unbounded_air','mesh_ids':['mesh:sphere'],'density_kg_per_m3':1.21,'sound_speed_m_per_s':343.}],
 'boundaries':[{'id':'boundary:sphere','name':'sphere_motion','kind':'moving','region_id':'region:exterior','parameters':{},'group':{'mesh_id':'mesh:sphere','dimension':2,'name':'sphere_motion','tag':10}}],
 'components':[{'id':'component:sphere','name':'Uniform outward radial motion','kind':'ideal_velocity_source','boundary_ids':['boundary:sphere'],'parameters':{'motion_profile':'uniform'}}],
 'excitation_ports':[{'id':'excitation:sphere','name':'Unit normal velocity','kind':'normal_velocity','component_id':'component:sphere'}]}
project={'schema_version':9,'physical_system':system,'symmetry':'off','stitch_exterior_meshes':False,'imported_meshes':[],'observation_planes':[],'component_channel_by_id':{'component:sphere':'main'},'project_preferences':{'freq_min_hz':350,'freq_max_hz':7500,'freq_count':4,'polar_angle_step_deg':5.,'polar_observation_distance_m':1.,'spherical_sampling_enabled':False}}
if args.sphere_angle_deg is not None:
 project['project_preferences'].update(spherical_sampling_enabled=True,balloon_angle_precision_deg=args.sphere_angle_deg)
(root/'project.blab.json').write_text(json.dumps(project,indent=2)+'\n')
print(root)
