"""Restore authoritative FEM mouth coordinates after native vertex merging."""
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
import contextlib
import io
import shutil
import tempfile
import numpy as np
from .boundary_lab import sha256


def restore_fem_interface_coordinates(raw: Path, front: Path, output: Path):
    """Copy a conforming BEM mesh, restoring only one-to-one matched mouth nodes.

    The pinned conformer can keep an annulus coordinate when merging a nearby
    FEM node. Its 1e-8 m merge radius is the maximum permitted correction here;
    final exact-facet checks and surface validation still apply afterwards.
    """
    import meshio
    if output.exists():raise FileExistsError(output)
    inputs={'raw_sha256':sha256(raw),'front_sha256':sha256(front)}
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        try:
            bem=meshio.read(raw,file_format='gmsh');fem=meshio.read(front,file_format='gmsh')
        except (meshio.ReadError,SystemExit) as exc:
            raise ValueError('invalid interface coordinate input mesh') from exc
    def facets(mesh):
        group=mesh.field_data.get('mouth_interface')
        if group is None or tuple(map(int,group))[1]!=2:
            raise ValueError('authoritative mouth surface group required')
        physical=mesh.cell_data.get('gmsh:physical',[])
        if len(physical)!=len(mesh.cells):raise ValueError('mouth physical coverage missing')
        rows=[]
        for cell,tags in zip(mesh.cells,physical):
            if len(tags)!=len(cell.data):raise ValueError('mouth physical coverage differs')
            if cell.type=='triangle':rows.extend(cell.data[np.asarray(tags)==int(group[0])])
        if not rows:raise ValueError('mouth must contain linear triangle facets')
        return np.asarray(rows,dtype=int)
    bf,ff=facets(bem),facets(fem)
    bi,fi=np.unique(bf),np.unique(ff)
    if len(bi)!=len(fi) or len(bf)!=len(ff):raise ValueError('mouth topology differs before coordinate restoration')
    if not np.isfinite(bem.points).all() or not np.isfinite(fem.points).all():
        raise ValueError('interface coordinates must be finite')
    tolerance=1e-8
    buckets=defaultdict(list)
    for i in fi:buckets[tuple(np.floor(fem.points[i]/tolerance).astype(np.int64))].append(int(i))
    mapping={};distances=[]
    for i in bi:
        cell=np.floor(bem.points[i]/tolerance).astype(np.int64)
        possible=[]
        for offset in product((-1,0,1),repeat=3):
            for j in buckets.get(tuple(cell+offset),()):
                if np.linalg.norm(bem.points[i]-fem.points[j])<=tolerance:possible.append(j)
        if len(possible)!=1:raise ValueError('mouth coordinate match is missing or ambiguous within native merge radius')
        mapping[int(i)]=possible[0]
        distances.append(float(np.linalg.norm(bem.points[i]-fem.points[possible[0]])))
    if len(set(mapping.values()))!=len(fi):raise ValueError('mouth coordinate mapping is not one-to-one')
    expected=Counter(tuple(sorted(face)) for face in ff)
    mapped=Counter(tuple(sorted(mapping[int(i)] for i in face)) for face in bf)
    if expected!=mapped:raise ValueError('mouth triangle membership differs before coordinate restoration')
    for i,j in mapping.items():bem.points[i]=fem.points[j]
    if inputs!={'raw_sha256':sha256(raw),'front_sha256':sha256(front)}:
        raise ValueError('interface input meshes changed during coordinate restoration')
    # Meshio's Gmsh writer requires a path; copy its completed output exclusively.
    with tempfile.TemporaryDirectory(prefix='meh-interface-',dir=output.parent) as temporary:
        staged=Path(temporary)/'surface.msh'
        # Boundary Lab's physical-group preflight scans the mesh as UTF-8 text.
        meshio.write(staged,bem,file_format='gmsh22',binary=False,float_fmt='.17e')
        with staged.open('rb') as source,output.open('xb') as stream:shutil.copyfileobj(source,stream)
    return inputs|{'output_sha256':sha256(output),'mouth_vertices':len(bi),
        'corrected_vertices':sum(d>0 for d in distances),'maximum_correction_m':max(distances),
        'maximum_allowed_correction_m':tolerance,'method':'restore_unique_authoritative_fem_coordinates'}
