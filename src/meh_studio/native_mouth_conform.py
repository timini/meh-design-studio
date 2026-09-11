"""Standalone adapter executed by the pinned Boundary Lab Python environment.

The generated mouth is planar. Protect curved rigid walls from the upstream
annulus selector, whose geometry tolerance can otherwise include nearby walls.
No upstream geometry, merging or final interface tolerances are increased.
"""
from pathlib import Path
from collections import Counter
import argparse
import dataclasses
import hashlib
import json
import math
import shutil
import tempfile
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def triangles(mesh):
    if not mesh.cells or any(c.type!='triangle' for c in mesh.cells):
        raise ValueError('generated exterior must contain only linear triangles')
    tags=mesh.cell_data['gmsh:physical']
    if len(tags)!=len(mesh.cells) or any(len(c.data)!=len(t) for c,t in zip(mesh.cells,tags)):
        raise ValueError('physical tags must cover every exterior triangle')
    return np.concatenate([c.data for c in mesh.cells]),np.concatenate(tags)


def oriented_facets(points):
    """Coordinate multiset invariant under cyclic rotation, but not reversal."""
    def key(face):
        v=tuple(tuple(float(x) for x in p) for p in face)
        return min(v,v[1:]+v[:1],v[2:]+v[:2])
    return Counter(key(face) for face in points)


def protect_curved_walls(fem,bem,mouth_z):
    if not math.isfinite(mouth_z) or not np.isfinite(fem.points).all() or not np.isfinite(bem.points).all():
        raise ValueError('finite generated mouth and mesh coordinates required')
    mouth=int(bem.field_data['mouth_interface'][0]);rigid=int(bem.field_data['rigid_exterior'][0])
    rows,tags=triangles(bem)
    if mouth==rigid or set(np.unique(tags))!={mouth,rigid}:
        raise ValueError('generated exterior requires distinct mouth and rigid physical groups')
    if any(int(bem.field_data[name][1])!=2 for name in ('mouth_interface','rigid_exterior')):
        raise ValueError('generated exterior groups must be surfaces')
    fem_tag=int(fem.field_data['mouth_interface'][0])
    fem_mouth=np.concatenate([c.data[np.asarray(t)==fem_tag] for c,t in zip(fem.cells,fem.cell_data['gmsh:physical']) if c.type=='triangle'])
    if not len(fem_mouth):raise ValueError('FEM mouth facets required')
    tolerance=1e-8
    if (np.max(abs(fem.points[fem_mouth,2]-mouth_z))>tolerance
            or np.max(abs(bem.points[rows[tags==mouth],2]-mouth_z))>tolerance):
        raise ValueError('both mouth interfaces must lie in the declared generated plane')
    planar=(tags==rigid)&(np.max(abs(bem.points[rows,2]-mouth_z),axis=1)<=tolerance)
    protected=(tags==rigid)&~planar
    if not planar.any() or not protected.any():
        raise ValueError('generated mouth requires a planar rigid rim and nonplanar enclosure')
    before=oriented_facets(bem.points[rows[protected]])
    protected_tag=max(int(v[0]) for v in bem.field_data.values())+1
    name='meh_protected_curved_rigid'
    if name in bem.field_data:raise ValueError('reserved temporary group already exists')
    offset=0
    for cell,physical in zip(bem.cells,bem.cell_data['gmsh:physical']):
        count=len(cell.data);physical[protected[offset:offset+count]]=protected_tag;offset+=count
    bem.field_data[name]=np.array([protected_tag,2])
    return name,protected_tag,rigid,before,{'mouth_plane_z_m':mouth_z,'plane_classification_tolerance_m':tolerance,
        'planar_rim_triangles':int(planar.sum()),'protected_curved_triangles':int(protected.sum())}


def conform(front,exterior,output,report_path,mouth_z):
    import meshio
    from blab.interface_conform import conform_bem_interface_to_fem
    inputs={'front':digest(front),'exterior':digest(exterior)}
    report={'status':'running','helper_sha256':digest(__file__),'input_sha256':inputs}
    try:
        if output.exists() or report_path.exists():raise FileExistsError('conformer outputs must be new')
        fem=meshio.read(front);bem=meshio.read(exterior)
        name,protected_tag,rigid,before,classification=protect_curved_walls(fem,bem,mouth_z)
        result,identity=conform_bem_interface_to_fem(fem,bem,
            fem_interface_name='mouth_interface',bem_interface_name='mouth_interface',
            protected_bem_interface_names=(name,))
        rows,tags=triangles(result)
        if oriented_facets(result.points[rows[tags==protected_tag]])!=before:
            raise ValueError('conforming changed protected curved-wall coordinates, facets or orientation')
        for tags in result.cell_data['gmsh:physical']:tags[tags==protected_tag]=rigid
        del result.field_data[name]
        if inputs!={'front':digest(front),'exterior':digest(exterior)} or digest(__file__)!=report['helper_sha256']:
            raise ValueError('native conformer inputs or helper changed')
        with tempfile.TemporaryDirectory(prefix='meh-conform-',dir=output.parent) as temporary:
            staged=Path(temporary)/'surface.msh'
            meshio.write(staged,result,file_format='gmsh22',binary=False,float_fmt='.17e')
            with staged.open('rb') as source,output.open('xb') as target:shutil.copyfileobj(source,target)
        report.update(status='complete',classification=classification,conforming_result=dataclasses.asdict(identity),
            protected_facets_unchanged=True,output_sha256=digest(output))
    except BaseException as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        # Compilation owns a new directory; never overwrite prior evidence.
        with report_path.open('x') as stream:stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    for name in ('front','exterior','output','report'):parser.add_argument(name,type=Path)
    parser.add_argument('--mouth-z',type=float,required=True)
    args=parser.parse_args()
    conform(args.front,args.exterior,args.output,args.report,args.mouth_z)


if __name__=='__main__':main()
