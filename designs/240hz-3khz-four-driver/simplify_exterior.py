"""Reduce exterior wall triangles, preserving the mouth and checking sampled error."""
import argparse,hashlib,json
from pathlib import Path
import meshio,numpy as np,vtk
from vtk.util.numpy_support import numpy_to_vtk,vtk_to_numpy
from meh_studio.radiation_geometry import surface_integrity


def poly(points,triangles):
 p=vtk.vtkPolyData();v=vtk.vtkPoints();v.SetData(numpy_to_vtk(points));p.SetPoints(v)
 cells=vtk.vtkCellArray()
 for tri in triangles:
  cells.InsertNextCell(3)
  for i in tri:cells.InsertCellPoint(int(i))
 p.SetPolys(cells);return p


def run(source,output):
 output.mkdir(parents=True,exist_ok=False)
 report={'status':'running','qualified':False,'maximum_sampled_distance_m':.001,'maximum_relative_volume_change':.02}
 try:
  m=meshio.read(source);t=np.concatenate([c.data for c in m.cells if c.type=='triangle'])
  tags=np.concatenate([a for c,a in zip(m.cells,m.cell_data['gmsh:physical']) if c.type=='triangle'])
  if set(m.field_data)!= {'mouth_interface','rigid_exterior'} or set(tags)!={10,99}:raise ValueError('unexpected exterior boundary groups')
  wall=poly(m.points,t[tags==99]);dec=vtk.vtkDecimatePro();dec.SetInputData(wall);dec.SetTargetReduction(.75);dec.SetFeatureAngle(60);dec.SetOutputPointsPrecision(vtk.vtkAlgorithm.DOUBLE_PRECISION)
  dec.PreserveTopologyOn();dec.BoundaryVertexDeletionOff();dec.SplittingOff();dec.Update()
  reduced=dec.GetOutput();p=vtk_to_numpy(reduced.GetPoints().GetData());cells=vtk_to_numpy(reduced.GetPolys().GetData()).reshape(-1,4)[:,1:]
  # Weld only the shared mouth rim; coincident but distinct wall vertices
  # must retain their topology (global coordinate deduplication can pinch edges).
  mouthfaces=t[tags==10]; lookup={tuple(m.points[i]):int(i) for i in np.unique(mouthfaces)}
  indices=np.array([lookup.get(tuple(x),len(m.points)+i) for i,x in enumerate(p)])
  points=np.vstack((m.points,p));faces=np.vstack((mouthfaces,indices[cells]))
  normals=vtk.vtkPolyDataNormals();normals.SetInputData(poly(points,faces));normals.ConsistencyOn();normals.AutoOrientNormalsOn();normals.SplittingOff();normals.Update()
  oriented=normals.GetOutput();newfaces=vtk_to_numpy(oriented.GetPolys().GetData()).reshape(-1,4)[:,1:]
  if not np.array_equal(np.sort(newfaces,axis=1),np.sort(faces,axis=1)):raise ValueError('normal orientation changed triangle membership')
  faces=newfaces
  groups=np.r_[np.full(sum(tags==10),10),np.full(len(cells),99)]
  path=output/'exterior.msh';meshio.write(path,meshio.Mesh(points,[('triangle',faces)],field_data=m.field_data,
    cell_data={'gmsh:physical':[groups],'gmsh:geometrical':[groups]}),file_format='gmsh22',binary=False)
  integrity=surface_integrity(path)
  original_volume=float(np.einsum('ij,ij->i',m.points[t[:,0]],np.cross(m.points[t[:,1]],m.points[t[:,2]])).sum()/6)
  volume_error=abs(integrity['enclosed_volume_m3']/original_volume-1)
  # Bidirectional vertex-to-triangle samples, not a continuous Hausdorff bound.
  distance=vtk.vtkDistancePolyDataFilter();distance.SetInputData(0,poly(m.points,t));distance.SetInputData(1,poly(points,faces));distance.SignedDistanceOff();distance.Update()
  maximum=max(float(np.max(np.abs(vtk_to_numpy(distance.GetOutput(i).GetPointData().GetScalars())))) for i in (0,1))
  report.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),surface=integrity,
    original_triangles=len(t),sampled_distance_m=maximum,relative_volume_change=volume_error,
    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  if maximum>.001 or volume_error>.02:raise ValueError('simplification exceeds declared geometric error limits')
  report.update(status='complete',limitations=['Bidirectional vertex samples do not bound all surface points',
    'No acoustic mesh convergence claim','Original mouth triangles retained; FEM conformance remains to perform'])
 except BaseException as exc:
  report.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
 finally:(output/'simplification.json').write_text(json.dumps(report,indent=2))
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(run(a.source,a.output),indent=2))
