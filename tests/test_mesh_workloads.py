from pathlib import Path
import pytest
from meh_studio.geometry import HornGeometry


def test_explicit_mesh_workload_limits_preserve_legacy_defaults():
    base=HornGeometry.model_validate_json((Path(__file__).parents[1]/'examples/freeform-ring-geometry.json').read_text())
    legacy=base.model_dump(mode='json')
    assert 'maximum_tetrahedra' not in legacy and 'maximum_exterior_triangles' not in legacy
    enlarged=HornGeometry.model_validate(legacy|{'maximum_tetrahedra':3_000_000,'maximum_exterior_triangles':16000})
    assert enlarged.model_dump()['maximum_tetrahedra']==3_000_000
    assert enlarged.model_dump()['maximum_exterior_triangles']==16000
    assert enlarged.content_hash!=base.content_hash
    assert enlarged.mesh_size_m==base.mesh_size_m
    for setting,value in [('maximum_tetrahedra',True),('maximum_tetrahedra',10_000_001),('maximum_exterior_triangles',0),('maximum_exterior_triangles',32001)]:
        with pytest.raises(ValueError):HornGeometry.model_validate(legacy|{setting:value})
