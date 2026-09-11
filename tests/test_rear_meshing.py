import json
import math
from pathlib import Path

import numpy as np
import pytest

from meh_studio.geometry import HornGeometry, export_geometry, mesh_geometry


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def data():
    return json.loads((EXAMPLES / 'three-driver-geometry.json').read_text())


def test_axial_refinement_preserves_default_identity_and_validates_spacing():
    original = HornGeometry.model_validate(data())
    explicit = HornGeometry.model_validate(data() | {'rear_axial_mesh_size_m': None})
    assert original.model_dump_json() == explicit.model_dump_json()
    assert 'rear_axial_mesh_size_m' not in explicit.model_dump()
    refined = HornGeometry.model_validate(data() | {'rear_axial_mesh_size_m': .0005})
    assert refined.content_hash != original.content_hash
    assert HornGeometry.model_validate_json(refined.model_dump_json()) == refined
    for value in (True, '0.001', 0., .00001, .009, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            HornGeometry.model_validate(data() | {'rear_axial_mesh_size_m': value})


@pytest.mark.cad
@pytest.mark.parametrize('symmetry,tilt', [('off',0.), ('xy',20.)])
def test_layered_mesh_preserves_front_mesh_and_compiles_all_driver_groups(tmp_path,symmetry,tilt):
    pytest.importorskip('cadquery'); pytest.importorskip('gmsh')
    import meshio
    from meh_studio.boundary_lab import sha256
    from meh_studio.generated_system import HornSources, compile_interior_system
    base = HornGeometry.model_validate(data() | {'solver_symmetry': symmetry,
        'entry_layout': 'four_driver_ring', 'driver_tilt_deg': tilt})
    refined = HornGeometry.model_validate(base.model_dump() | {'rear_axial_mesh_size_m': .001})
    roots = [tmp_path/'base',tmp_path/'refined']; reports = []
    for design,root in zip((base,refined),roots):
        export_geometry(design,root)
        reports.append(mesh_geometry(root))
    assert sha256(roots[0]/'analysis/front.msh') == sha256(roots[1]/'analysis/front.msh')
    original = {r['id']:r for r in reports[0]['regions']}
    sources = json.loads((roots[1]/'geometry.json').read_text())['sources']
    for region in reports[1]['regions']:
        assert region['volume_m3'] == pytest.approx(original[region['id']]['volume_m3'],rel=1e-6)
        if region['id']=='front':
            assert 'layered_rear_mesh' not in region
            continue
        report = region['layered_rear_mesh']
        assert report['actual_axial_spacing_m'] <= refined.rear_axial_mesh_size_m
        assert region['tetrahedra'] == report['predicted_tetrahedra']
        mesh = meshio.read(roots[1]/region['path'])
        source = next(s for s in sources if region['id']=='rear_'+s['id'])
        axial = (mesh.points-np.array(source['rear_center_m'])) @ np.array(source['motion_axis'])
        layer = np.rint(axial/report['actual_axial_spacing_m']).astype(int)
        np.testing.assert_allclose(axial,layer*report['actual_axial_spacing_m'],atol=1e-9,rtol=0)
        assert len(np.unique(layer)) == report['layers']+1
        for cell in mesh.cells:
            if cell.type=='tetra': assert np.max(np.ptp(layer[cell.data],axis=1))==1
    physical = HornSources.model_validate_json((EXAMPLES/'synthetic-horn-sources.json').read_text())
    compiled = compile_interior_system(roots[1],physical,tmp_path/'system')
    assert compiled['driver_count']==5
    if symmetry=='xy':
        assert sum(v['physical_driver_orbit_count'] for v in compiled['driver_symmetry'].values())==5


@pytest.mark.cad
def test_layered_mesh_rejects_changed_volume_and_guards_layer_count():
    gmsh = pytest.importorskip('gmsh')
    from meh_studio.rear_meshing import layered_rear_volume, check_layered_workload
    for wrong_direction in (True,False):
        gmsh.initialize()
        try:
            gmsh.option.setNumber('General.Terminal',0)
            tag = gmsh.model.occ.addCylinder(0,0,0,0,0,.07,.016)
            gmsh.model.occ.synchronize()
            face = next(t for d,t in gmsh.model.getBoundary([(3,tag)],oriented=False)
                        if gmsh.model.getType(d,t)=='Plane' and abs(gmsh.model.occ.getCenterOfMass(d,t)[2])<1e-9)
            if wrong_direction:
                with pytest.raises(ValueError,match='differs from the exported air CAD'):
                    layered_rear_volume(gmsh,[(3,tag)],face,[0,0,-1],.07,.0005)
            else:
                _,_,_,report = layered_rear_volume(gmsh,[(3,tag)],face,[0,0,1],.07,.0005)
                gmsh.option.setNumber('Mesh.MeshSizeMax',.008)
                with pytest.raises(ValueError,match='workload exceeds'):
                    check_layered_workload(gmsh,report,1)
                assert report['predicted_tetrahedra']>1
                assert len(gmsh.model.mesh.getElements(3)[0])==0
        finally: gmsh.finalize()


@pytest.mark.cad
def test_layered_rear_p1_impedance_matches_lossless_closed_cylinder(tmp_path):
    """Independent FEM equations check the longitudinal resonances, not just CAD."""
    gmsh=pytest.importorskip('gmsh');pytest.importorskip('scipy')
    import meshio
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    from meh_studio.rear_meshing import layered_rear_volume,check_layered_workload
    length=.07;radius=.016;spacing=.0005
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        tag=gmsh.model.occ.addCylinder(0,0,0,0,0,length,radius)
        gmsh.model.occ.synchronize()
        face=next(t for d,t in gmsh.model.getBoundary([(3,tag)],oriented=False)
                  if gmsh.model.getType(d,t)=='Plane' and abs(gmsh.model.occ.getCenterOfMass(d,t)[2])<1e-9)
        volumes,source,walls,report=layered_rear_volume(gmsh,[(3,tag)],face,[0,0,1],length,spacing)
        gmsh.model.addPhysicalGroup(3,[volumes[0][1]],1,name='air')
        gmsh.model.addPhysicalGroup(2,source,10,name='piston')
        gmsh.model.addPhysicalGroup(2,walls,99,name='rigid')
        gmsh.option.setNumber('Mesh.MeshSizeMax',.004)
        gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',48)
        gmsh.option.setNumber('Mesh.ElementOrder',1)
        check_layered_workload(gmsh,report,200000)
        gmsh.model.mesh.generate(3)
        path=tmp_path/'cylinder.msh';gmsh.write(str(path))
    finally: gmsh.finalize()
    mesh=meshio.read(path);tet=np.vstack([b.data for b in mesh.cells if b.type=='tetra'])
    assert len(tet)==report['predicted_tetrahedra']
    points=mesh.points[tet]
    affine=np.concatenate((np.ones((*points.shape[:2],1)),points),axis=2)
    volume=np.abs(np.linalg.det(affine))/6
    gradient=np.linalg.inv(affine)[:,1:,:].transpose(0,2,1)
    stiffness=volume[:,None,None]*np.einsum('tik,tjk->tij',gradient,gradient)
    mass=volume[:,None,None]*(np.ones((4,4))+np.eye(4))/20
    ii=np.repeat(tet,4,axis=1).ravel();jj=np.tile(tet,(1,4)).ravel();shape=(len(mesh.points),)*2
    K=coo_matrix((stiffness.ravel(),(ii,jj)),shape=shape).tocsc()
    M=coo_matrix((mass.ravel(),(ii,jj)),shape=shape).tocsc()
    triangles=np.vstack([b.data[np.asarray(tags)==10] for b,tags in zip(mesh.cells,mesh.cell_data['gmsh:physical']) if b.type=='triangle'])
    points=mesh.points[triangles]
    areas=np.linalg.norm(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]),axis=1)/2
    piston=np.zeros(len(mesh.points));np.add.at(piston,triangles.ravel(),np.repeat(areas/3,3))
    rho=1.21;c=343.
    for frequency in (350.,2000.,5000.,7500.):
        omega=2*math.pi*frequency;matrix=K-(omega/c)**2*M
        # exp(-i omega t), unit inward piston velocity: outward dp/dn=-i omega rho.
        rhs=-1j*omega*rho*piston
        pressure=spsolve(matrix.astype(complex),rhs)
        assert np.linalg.norm(matrix@pressure-rhs)/np.linalg.norm(rhs)<1e-8
        load=np.dot(piston,pressure)
        exact=1j*rho*c*math.pi*radius**2/math.tan(omega*length/c)
        assert abs(load-exact)/abs(exact)<.02
