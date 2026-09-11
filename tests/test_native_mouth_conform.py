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
