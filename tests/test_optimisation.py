import json
from pathlib import Path
import pytest
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from meh_studio.optimisation import SearchBrief, candidates


def inputs():
    root=Path(__file__).resolve().parents[1]/'examples'
    return (SearchBrief.model_validate_json((root/'synthetic-search-brief.json').read_text()),
            HornGeometry.model_validate_json((root/'three-driver-geometry.json').read_text()),
            [DriverRevision.model_validate(d) for d in json.loads((root/'synthetic-search-drivers.json').read_text())])


def test_candidate_search_is_bounded_deterministic_and_varies_models_geometry():
    brief,base,drivers=inputs()
    a=candidates(brief,base,drivers);b=candidates(brief,base,drivers)
    assert a==b and len(a)==brief.trial_budget
    assert len({c['design'].content_hash for c in a})>1
    assert all(c['cost']<=brief.max_driver_cost and c['design'].driver_count<=brief.max_drivers for c in a)
    assert all(c['sources'].throat.provenance.kind=='synthetic' for c in a)


def test_cost_and_driver_limits_prune_before_solving():
    brief,base,drivers=inputs()
    brief=SearchBrief.model_validate(brief.model_dump()|{'max_drivers':3,'max_driver_cost':14})
    result=candidates(brief,base,drivers)
    assert all(c['design'].driver_count==3 and c['drivers'][1].id=='synthetic-side' for c in result)
    with pytest.raises(ValueError,match='no feasible'):
        candidates(SearchBrief.model_validate(brief.model_dump()|{'max_driver_cost':1}),base,drivers)


@pytest.mark.parametrize('change',[{'prices':{}},{'entry_fractions':[(1.,)]},{'frequencies_hz':[1000,500,2000]},{'trial_budget':0}])
def test_invalid_search_contract_fails(change):
    brief,_,_=inputs()
    with pytest.raises(ValueError): SearchBrief.model_validate(brief.model_dump()|change)
