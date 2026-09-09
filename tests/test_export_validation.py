import json
import meshio
import numpy as np
import pytest
from meh_studio.boundary_lab import sha256
from meh_studio.export_validation import validate_export


@pytest.mark.parametrize('fault',[None,'open','orientation','scale'])
def test_export_checks_real_stl_topology_and_millimetre_volume(tmp_path,fault):
    points=np.array([[0.,0,0],[1.,0,0],[0,1.,0],[0,0,1.]])
    faces=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    if fault=='open': faces=faces[:-1]
    if fault=='orientation':faces[0]=faces[0][::-1]
    if fault=='scale':points*=1000
    (tmp_path/'parts').mkdir()
    path=tmp_path/'parts/tetra.stl'
    meshio.write(path,meshio.Mesh(points,[('triangle',faces)]),binary=True)
    state={'status':'complete','units':{'cad_and_stl':'mm'},
           'files':[{'path':'parts/tetra.stl','sha256':sha256(path)}],
           'material_volume_m3':{'tetra':1/6/1e9}}
    (tmp_path/'geometry.json').write_text(json.dumps(state))
    if fault:
        with pytest.raises(ValueError):validate_export(tmp_path)
    else:
        result=validate_export(tmp_path)
        assert result['mesh_checks_passed'] and not result['print_qualified']
