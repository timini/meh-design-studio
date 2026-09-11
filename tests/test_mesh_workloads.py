from pathlib import Path
import pytest
from meh_studio.geometry import HornGeometry


def test_explicit_mesh_workload_limits_preserve_legacy_defaults():
    base=HornGeometry.model_validate_json((Path(__file__).parents[1]/'examples/freeform-ring-geometry.json').read_text())
    legacy=base.model_dump(mode='json')
    assert 'maximum_tetrahedra' not in legacy and 'maximum_exterior_triangles' not in legacy
    assert 'maximum_raw_exterior_triangles' not in legacy
    assert HornGeometry.model_validate(legacy | {'maximum_raw_exterior_triangles': None}).content_hash == base.content_hash
    enlarged=HornGeometry.model_validate(legacy|{'maximum_tetrahedra':3_000_000,'maximum_exterior_triangles':16000})
    assert enlarged.model_dump()['maximum_tetrahedra']==3_000_000
    assert enlarged.model_dump()['maximum_exterior_triangles']==16000
    assert enlarged.content_hash!=base.content_hash
    assert enlarged.mesh_size_m==base.mesh_size_m
    for setting,value in [('maximum_tetrahedra',True),('maximum_tetrahedra',10_000_001),('maximum_exterior_triangles',0),('maximum_exterior_triangles',32001)]:
        with pytest.raises(ValueError):HornGeometry.model_validate(legacy|{setting:value})


def test_raw_preparation_budget_does_not_increase_final_solver_budget():
    base = HornGeometry.model_validate_json((Path(__file__).parents[1]/'examples/freeform-ring-geometry.json').read_text())
    enlarged = HornGeometry.model_validate(base.model_dump() | {'maximum_raw_exterior_triangles': 64000})
    assert enlarged.maximum_exterior_triangles == base.maximum_exterior_triangles == 8000
    assert enlarged.maximum_raw_exterior_triangles == 64000
    assert enlarged.content_hash != base.content_hash
    assert HornGeometry.model_validate_json(enlarged.model_dump_json()) == enlarged
    for value in (True, 0, 64001, 64000., '64000'):
        with pytest.raises(ValueError):
            HornGeometry.model_validate(base.model_dump() | {'maximum_raw_exterior_triangles': value})


def test_circular_axial_taper_is_not_counted_as_azimuthal_mesh_aspect():
    from meh_studio.geometry import estimated_curved_tetrahedra
    base=HornGeometry.model_validate_json((Path(__file__).parents[1]/'examples/freeform-ring-geometry.json').read_text())
    circular=[{'fraction':f,'radial_scales':[s]*8} for f,s in ((.2,.55),(.4,.6),(.7,.9),(1.,1.5))]
    tapered=HornGeometry.model_validate(base.model_dump()|{'profile_sections':circular})
    round_control=HornGeometry.model_validate(base.model_dump()|{'profile_sections':[dict(s,radial_scales=[1.]*8) for s in circular]})
    volume=.001
    # The radius/volume workload is still included; axial variation must not add
    # an artificial (1.5/.55)^3 penalty to circular cross-sections.
    expected=estimated_curved_tetrahedra(round_control,'front',volume)
    assert estimated_curved_tetrahedra(tapered,'front',volume)==expected
    oval=[dict(s,radial_scales=[s['radial_scales'][0]*(1.2 if i%2 else 1.) for i in range(8)]) for s in circular]
    irregular=HornGeometry.model_validate(base.model_dump()|{'profile_sections':oval})
    assert estimated_curved_tetrahedra(irregular,'front',volume)==pytest.approx(expected*1.2**3)
    assert irregular.maximum_tetrahedra==base.maximum_tetrahedra
