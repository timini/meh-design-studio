import sys, json, math, argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import transfer_fem as f
import gmsh,meshio
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
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
gmsh.model.mesh.generate(3);gmsh.write(str(out/'tube.msh'));gmsh.finalize()
ops=f.assemble(meshio.read(out/'tube.msh'));rows=[]
for hz in (240,1000,3000):
 means,res=f.response(ops,hz,{'source':.0001})
 exact=1.21*343*.0001/.0004*complex(math.cos(-2*math.pi*hz*.1/343),math.sin(-2*math.pi*hz*.1/343))
 error=abs(means['mouth']/exact-1);assert error<.02,(hz,error,means['mouth'],exact)
 rows.append({'frequency_hz':hz,'relative_complex_error':error,'relative_residual':res})
(out/'validation.json').write_text(json.dumps(rows,indent=2));print(rows)
