"""Prepare R1's filled outer envelope for radiation meshing, not printing."""
import argparse,hashlib,json,math
from pathlib import Path
import cadquery as cq
from generate import build,rounded_plate,cylinder,FACE,LENGTH,MOUTH
from meh_studio.radiation_geometry import surface_integrity


def export(source,output):
 output.mkdir(parents=True,exist_ok=False)
 report={'status':'running','qualified':False,'units':{'cad':'mm','mesh':'m'}}
 try:
  domain=json.loads((source/'front-domain.json').read_text());path=source/'front-air.step'
  expected=next(x['sha256'] for x in domain['files'] if x['path']==path.name)
  if domain['status']!='complete' or domain['units']!='mm' or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('invalid front air identity')
  body,_,mounts=build(exterior_blank=True);air=cq.importers.importStep(str(path)).val()
  # Fill sealed rear cavities and ideal driver packages. This changes no mouth geometry.
  cap=rounded_plate(108,6,radius=28).fuse(rounded_plate(96,124,radius=10))
  fills=[cap.translate((0,0,FACE)).moved(m['plane'].location) for m in mounts]
  envelope=body.fuse(air,*fills).clean()
  if not envelope.isValid() or len(envelope.Solids())!=1:raise ValueError('outer envelope must be one connected solid')
  if len(envelope.Shells())!=1:raise ValueError('outer envelope retains enclosed cavities')
  path=output/'envelope.step';cq.exporters.export(envelope,str(path))
  import gmsh
  if gmsh.isInitialized():raise ValueError('requires isolated Gmsh runtime')
  gmsh.initialize()
  try:
   gmsh.option.setNumber('General.Terminal',0);gmsh.option.setString('Geometry.OCCTargetUnit','M')
   imported=gmsh.model.occ.importShapes(str(path.resolve()))
   disk=gmsh.model.occ.addDisk(0,0,LENGTH/1000,MOUTH/1000,MOUTH/1000)
   gmsh.model.occ.fragment(imported,[(2,disk)]);gmsh.model.occ.synchronize()
   volumes=gmsh.model.getEntities(3)
   if len(volumes)!=1:raise ValueError('envelope import disconnected')
   mouth=[];walls=[]
   for dim,tag in gmsh.model.getBoundary(volumes,oriented=False):
    center=gmsh.model.occ.getCenterOfMass(dim,tag);area=gmsh.model.occ.getMass(dim,tag)
    if gmsh.model.getType(dim,tag)=='Plane' and math.dist(center,[0,0,LENGTH/1000])<1e-7 and math.isclose(area,math.pi*(MOUTH/1000)**2,rel_tol=1e-6):mouth.append(tag)
    else:walls.append(tag)
   if len(mouth)!=1:raise ValueError('mouth interface not unique')
   gmsh.model.addPhysicalGroup(2,mouth,10,name='mouth_interface');gmsh.model.addPhysicalGroup(2,walls,99,name='rigid_exterior')
   gmsh.option.setNumber('Mesh.MeshSizeMin',.025);gmsh.option.setNumber('Mesh.MeshSizeMax',.04)
   gmsh.option.setNumber('Mesh.ElementOrder',1);gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
   gmsh.model.mesh.generate(2);gmsh.write(str(output/'exterior.msh'))
  finally:gmsh.finalize()
  integrity=surface_integrity(output/'exterior.msh')
  if not math.isclose(integrity['enclosed_volume_m3'],envelope.Volume()/1e9,rel_tol=.02):raise ValueError('surface volume error exceeds 2%')
  report.update(status='complete',surface=integrity,cad_volume_m3=envelope.Volume()/1e9,
    source_front_air_sha256=expected,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Rigid filled rear packages and fastener holes; no measured driver casing geometry','Interface not yet conformed to FEM triangles','No acoustic solve or convergence claim'])
 except BaseException as exc:
  report.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
 finally:(output/'exterior.json').write_text(json.dumps(report,indent=2))
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.source,a.output),indent=2))
