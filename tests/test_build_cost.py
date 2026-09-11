from types import SimpleNamespace
import json
import pytest
from meh_studio.build_cost import BuildBudget,estimate_build_cost,cost_adjusted_score


def budget(limit=300.):
    return BuildBudget(maximum_total_cost=limit,material_density_kg_m3=1250.,
                       material_cost_per_kg=20.,process_allowance_factor=1.2,other_cost_allowance=30.)


def test_actual_cad_material_and_allowances_change_selection_cost():
    # One litre at 1.25 kg/L, 20% allowance, £20/kg = £30 material.
    geometry={'status':'complete','material_volume_m3':{'horn':.0008,'covers':.0002}}
    cost=estimate_build_cost(budget(),geometry,100.)
    assert cost['solid_material_mass_kg']==pytest.approx(1.25)
    assert cost['estimated_total_cost']==pytest.approx(160.)
    brief=SimpleNamespace(build_budget=budget(),max_driver_cost=200.,cost_weight_db=1.)
    first=cost_adjusted_score({'ripple_db':2.},brief,{'cost':100.},geometry)
    second=cost_adjusted_score({'ripple_db':2.},brief,{'cost':100.},
        {'status':'complete','material_volume_m3':{'horn':.002}})
    assert second['objective']>first['objective']
    with pytest.raises(ValueError,match='total build budget'):
        cost_adjusted_score({'ripple_db':2.},SimpleNamespace(**(vars(brief)|{'build_budget':budget(150.)})),{'cost':100.},geometry)


def test_budget_rejection_preserves_estimate_and_never_meshes(tmp_path,monkeypatch):
    from meh_studio import geometry as module
    from meh_studio.candidate_preparation import prepare_in_process
    from meh_studio.geometry import HornGeometry
    from pathlib import Path
    base=HornGeometry.model_validate_json((Path(__file__).parents[1]/'examples/compact-ring-geometry.json').read_text())
    def export(design,output):
        output.mkdir();(output/'geometry.json').write_text(json.dumps({'status':'complete','material_volume_m3':{'horn':.01}}))
    monkeypatch.setattr(module,'export_geometry',export)
    monkeypatch.setattr(module,'mesh_geometry',lambda root:pytest.fail('over-budget candidate reached meshing'))
    (tmp_path/'trial').mkdir()
    with pytest.raises(ValueError,match='total build budget'):
        prepare_in_process({'design':base,'cost':100.},tmp_path/'trial',None,SimpleNamespace(build_budget=budget()))
    evidence=json.loads((tmp_path/'trial/build-cost.json').read_text())
    assert evidence['within_budget'] is False
    assert evidence['estimated_total_cost']==pytest.approx(430.)


@pytest.mark.parametrize('volumes',[{}, {'horn':0.}, {'horn':-1.}, {'horn':float('nan')}])
def test_cost_requires_finite_material_evidence(volumes):
    with pytest.raises(ValueError,match='material volumes'):
        estimate_build_cost(budget(),{'status':'complete','material_volume_m3':volumes},100.)
