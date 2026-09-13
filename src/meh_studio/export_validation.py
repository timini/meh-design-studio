"""Independent triangle checks for generated STL files; not print qualification."""
from pathlib import Path
import contextlib
import io
import numpy as np
import meshio
from .boundary_lab import _read_json, _contained, sha256


def validate_export(root: Path):
    root=Path(root)
    state=_read_json(root/'geometry.json')
    return _validate_export_state(root, state)


def _validate_export_state(root: Path, state):
    """Also check freshly generated meshes before their manifest is published."""
    if state.get('status')!='complete' or state.get('units',{}).get('cad_and_stl')!='mm':
        raise ValueError('complete millimetre geometry export required')
    rows=[]
    for entry in state['files']:
        path=_contained(root,entry['path'])
        if sha256(path)!=entry['sha256']: raise ValueError('export file integrity mismatch')
        if not entry['path'].startswith('parts/') or path.suffix!='.stl': continue
        with contextlib.redirect_stdout(io.StringIO()): mesh=meshio.read(path)
        if not mesh.cells or any(c.type!='triangle' for c in mesh.cells): raise ValueError('STL must contain triangles')
        # STL repeats vertices; exact float-coordinate welding preserves cracks.
        points,inverse=np.unique(mesh.points,axis=0,return_inverse=True)
        faces=inverse[np.vstack([cell.data for cell in mesh.cells])]
        if not np.isfinite(points).all(): raise ValueError('nonfinite STL coordinates')
        a,b,c=(points[faces[:,i]] for i in range(3))
        if np.any(np.linalg.norm(np.cross(b-a,c-a),axis=1)<=1e-12): raise ValueError('degenerate STL triangles')
        edges=np.vstack((faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]))
        _,edge_inverse,counts=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True)
        signs=np.where(edges[:,0]<edges[:,1],1,-1)
        if np.any(counts!=2) or np.any(np.bincount(edge_inverse,weights=signs)!=0):
            raise ValueError('STL has open/nonmanifold/inconsistently oriented edges')
        volume=float(np.einsum('ij,ij->i',a,np.cross(b,c)).sum()/6/1e9)
        expected=state['material_volume_m3'][path.stem]
        error=abs(volume/expected-1)
        if volume<=0 or error>.01: raise ValueError('STL volume differs from CAD by more than one percent')
        if sha256(path)!=entry['sha256']: raise ValueError('STL changed during validation')
        rows.append({'file':entry['path'],'sha256':entry['sha256'],'triangles':len(faces),
            'closed_oriented_edges':True,'volume_m3':volume,'relative_cad_volume_error':error,
            'bounds_mm':[points.min(axis=0).tolist(),points.max(axis=0).tolist()]})
    if not rows: raise ValueError('no material STL files in export')
    return {'schema_version':1,'mesh_checks_passed':True,'print_qualified':False,'parts':rows,
            'limitations':['No slicer, printer, supports, fit, sealing, hardware or physical strength qualification']}
