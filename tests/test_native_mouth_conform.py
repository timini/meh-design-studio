import numpy as np
import pytest
from meh_studio.native_mouth_conform import protect_curved_walls,oriented_facets


def meshes():
    from types import SimpleNamespace as S
    # The curved triangle is very close to the rim, but is not in its plane.
    points=np.array([[0.,0.,.3],[1.,0.,.3],[0.,1.,.3],[1.,1.,.3],[1.,1.,.299]])
    fem=S(points=points,cells=[S(type='triangle',data=np.array([[0,1,2]]))],
        cell_data={'gmsh:physical':[np.array([11])]},field_data={'mouth_interface':np.array([11,2])})
    bem=S(points=points.copy(),cells=[S(type='triangle',data=np.array([[0,1,2],[1,3,2],[1,4,3]]))],
        cell_data={'gmsh:physical':[np.array([10,99,99])]},
        field_data={'mouth_interface':np.array([10,2]),'rigid_exterior':np.array([99,2])})
    return fem,bem


def test_only_exact_planar_rim_is_available_to_annulus_remesher():
    fem,bem=meshes();coordinates=bem.points.copy()
    name,tag,rigid,before,report=protect_curved_walls(fem,bem,.3)
    np.testing.assert_array_equal(bem.cell_data['gmsh:physical'][0],[10,99,tag])
    np.testing.assert_array_equal(bem.points,coordinates)
    assert tuple(bem.field_data[name])==(tag,2) and rigid==99
    assert report['planar_rim_triangles']==report['protected_curved_triangles']==1
    assert report['plane_classification_tolerance_m']==1e-8
    face=coordinates[np.array([[1,4,3]])]
    assert oriented_facets(face)==before
    assert oriented_facets(face[:,[1,2,0]])==before
    assert oriented_facets(face[:,::-1])!=before
    face[0,0,0]+=1e-12
    assert oriented_facets(face)!=before


@pytest.mark.parametrize('fault',['fem_plane','bem_plane','missing_rim','tags','nonfinite'])
def test_foreign_or_nonplanar_mouths_are_rejected(fault):
    fem,bem=meshes()
    if fault=='fem_plane':fem.points=fem.points.copy();fem.points[0,2]+=.001
    if fault=='bem_plane':bem.points[0,2]+=.001
    if fault=='missing_rim':bem.points[3,2]=.298
    if fault=='tags':bem.cell_data['gmsh:physical'][0][-1]=42
    if fault=='nonfinite':bem.points[0,0]=np.nan
    with pytest.raises(ValueError):protect_curved_walls(fem,bem,.3)


@pytest.mark.parametrize('width', [.003, .00003, .03])
def test_quarter_rim_tolerance_excludes_cut_connectors_without_relaxing_default(width):
    import meshio
    from meh_studio.native_mouth_conform import quarter_rim_tolerance
    radius = .22
    angles = np.array([0., np.pi/4, np.pi/2])
    inner = np.column_stack([radius*np.cos(angles), radius*np.sin(angles), np.full(3,.3)])
    outer = inner.copy(); outer[:,:2] *= (radius+width)/radius
    points = np.vstack([[0.,0.,.3], inner, outer])
    mouth = np.array([[0,1,2],[0,2,3]])
    rim = np.array([[1,4,5],[1,5,2],[2,5,6],[2,6,3]])
    bem = meshio.Mesh(points, [('triangle', np.vstack([mouth,rim]))],
        cell_data={'gmsh:physical':[np.array([10,10,99,99,99,99])]},
        field_data={'mouth_interface':np.array([10,2])})
    fem = meshio.Mesh(points, [('triangle',mouth)],
        cell_data={'gmsh:physical':[np.array([10,10])]},field_data={'mouth_interface':np.array([10,2])})
    before = bem.points.copy()
    report = quarter_rim_tolerance(fem,bem,99)
    assert report['shared_opening_edges'] == 2
    assert report['minimum_nonopening_midpoint_distance_m'] == pytest.approx(width/2)
    assert report['geometry_tolerance_m'] == pytest.approx(min(radius*np.sqrt(2)*.005,width/4))
    assert report['geometry_tolerance_m'] <= report['upstream_default_geometry_tolerance_m']
    np.testing.assert_array_equal(bem.points,before)
    # Unshared duplicate vertices describe an invalid disconnected opening.
    broken = bem.copy()
    broken.points = np.vstack([points,points[1:4]])
    broken.cells[0].data[:2] = [[0,7,8],[0,8,9]]
    with pytest.raises(ValueError,match='shared opening'):
        quarter_rim_tolerance(fem,broken,99)
