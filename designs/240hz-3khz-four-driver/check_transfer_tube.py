"""Independent tube reference with persistent success/failure evidence."""
import sys, json, math, argparse, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import transfer_fem as f
import gmsh,meshio


def run(out):
 out.mkdir(parents=True,exist_ok=False)
 report={'status':'running','maximum_relative_complex_error':.02,
         'geometry_m':{'length':.1,'width':.02,'height':.02,'mesh_size':.004},
         'density_kg_m3':1.21,'sound_speed_m_s':343.,'inward_flow_m3_s_rms':.0001,
         'frequencies_hz':[240,1000,3000], 'phasor':'exp(+i omega t)',
         'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'solver_sha256':hashlib.sha256(Path(f.__file__).read_bytes()).hexdigest(),
         'samples':[]}
 try:
  if gmsh.isInitialized():raise ValueError('requires isolated Gmsh runtime')
  try:
   gmsh.initialize();gmsh.option.setNumber('General.Terminal',0)
   v=gmsh.model.occ.addBox(0,0,0,.02,.02,.1);gmsh.model.occ.synchronize()
   walls=[]
   for _,t in gmsh.model.getBoundary([(3,v)],oriented=False):
    z=gmsh.model.occ.getCenterOfMass(2,t)[2]
    if abs(z)<1e-9:gmsh.model.addPhysicalGroup(2,[t],10,name='source')
    elif abs(z-.1)<1e-9:gmsh.model.addPhysicalGroup(2,[t],11,name='mouth')
    else:walls.append(t)
   gmsh.model.addPhysicalGroup(2,walls,99,name='rigid_walls');gmsh.model.addPhysicalGroup(3,[v],1,name='air')
   gmsh.option.setNumber('Mesh.MeshSizeMin',.004);gmsh.option.setNumber('Mesh.MeshSizeMax',.004)
   gmsh.model.mesh.generate(3);gmsh.write(str(out/'tube.msh'))
  finally:
   gmsh.finalize()
  report['mesh_sha256']=hashlib.sha256((out/'tube.msh').read_bytes()).hexdigest()
  ops=f.assemble(meshio.read(out/'tube.msh'))
  for hz in report['frequencies_hz']:
   means,res=f.response(ops,hz,{'source':.0001})
   exact=1.21*343*.0001/.0004*complex(math.cos(-2*math.pi*hz*.1/343),math.sin(-2*math.pi*hz*.1/343))
   error=abs(means['mouth']/exact-1)
   report['samples'].append({'frequency_hz':hz,'relative_complex_error':error if math.isfinite(error) else None,
                            'relative_residual':res if math.isfinite(res) else None})
   if not math.isfinite(error) or error>=report['maximum_relative_complex_error']:
    raise ValueError(f'tube complex error exceeds gate at {hz} Hz: {error}')
  report['status']='complete'
 except BaseException as exc:
  report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
  raise
 finally:
  (out/'validation.json').write_text(json.dumps(report,indent=2,allow_nan=False))
 return report


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
 print(json.dumps(run(parser.parse_args().output),indent=2))
