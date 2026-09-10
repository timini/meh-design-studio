"""Geometric identity checks, not acoustic accuracy evidence."""
from pathlib import Path
import numpy as np
import meshio
import pytest
from meh_studio.interface_coordinates import restore_fem_interface_coordinates
from meh_studio.radiation_geometry import verify_exterior_groups
from meh_studio.boundary_lab import sha256


def write(path,points,faces,tags,exterior):
    meshio.write(path,meshio.Mesh(points,[('triangle',np.asarray(faces))],
        cell_data={'gmsh:physical':[np.asarray(tags)],'gmsh:geometrical':[np.ones(len(tags),dtype=int)]},
        field_data={'mouth_interface':[10,2],('rigid_exterior' if exterior else 'rigid_walls'):[99,2]}),
        file_format='gmsh22',binary=False)


@pytest.mark.parametrize('fault',[None,'distance','membership','nonunique','ambiguous'])
def test_restore_preserves_authoritative_interface_without_changing_topology(tmp_path,fault):
    points=np.array([[0.,0,0],[1.,0,0],[0,1.,0],[0,0,1.]])
    faces=[[0,2,1],[0,1,3],[0,3,2],[1,2,3]]
    front,raw,out=(tmp_path/name for name in ('front.msh','raw.msh','out.msh'))
    shifted=points.copy();shifted[0,0]=8e-9
    tags=[10,99,99,99]
    if fault=='distance':shifted[0,0]=2e-8
    if fault=='membership':tags=[99,10,99,99]
    if fault=='nonunique':shifted[1]=shifted[0]
    if fault=='ambiguous':points[1]=[9e-9,0,0]
    write(front,points,faces,[10,99,99,99],False)
    write(raw,shifted,faces,tags,True)
    hashes=[sha256(front),sha256(raw)]
    if fault:
        with pytest.raises(ValueError,match='match|one-to-one|membership'):
            restore_fem_interface_coordinates(raw,front,out)
        assert not out.exists()
    else:
        with pytest.raises(ValueError,match='triangle membership'):verify_exterior_groups(raw,front)
        report=restore_fem_interface_coordinates(raw,front,out)
        assert out.read_text(encoding='utf-8').startswith('$MeshFormat\n2.2 0 8\n')
        assert report['maximum_correction_m']==pytest.approx(8e-9)
        assert report['corrected_vertices']==1
        verify_exterior_groups(out,front)
        result=meshio.read(out)
        np.testing.assert_array_equal(result.points,points)
        np.testing.assert_array_equal(result.cells[0].data,faces)
        with pytest.raises(FileExistsError):restore_fem_interface_coordinates(raw,front,out)
    assert hashes==[sha256(front),sha256(raw)]


def test_same_mouth_vertices_with_different_triangulation_are_rejected(tmp_path):
    points=np.array([[0.,0,0],[1.,0,0],[1.,1.,0],[0,1.,0]])
    front,raw,out=(tmp_path/name for name in ('front.msh','raw.msh','out.msh'))
    write(front,points,[[0,1,2],[0,2,3]],[10,10],False)
    write(raw,points,[[0,1,3],[1,2,3]],[10,10],True)
    with pytest.raises(ValueError,match='triangle membership'):
        restore_fem_interface_coordinates(raw,front,out)
    assert not out.exists()
