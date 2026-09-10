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


def test_latest_selected_revision_and_unrelated_history():
    brief,base,drivers=inputs()
    unrelated=drivers[1].model_copy(update={'id':'unselected'})
    revised=drivers[1].model_copy(update={'revision':2})
    pool=candidates(brief,base,drivers+[unrelated,unrelated.model_copy(update={'revision':2}),revised])
    assert all(c['drivers'][1].revision==2 for c in pool if c['drivers'][1].id==revised.id)


def test_relative_score_is_invariant_under_uniform_pressure_scaling():
    import numpy as np
    from meh_studio.optimisation import relative_response
    values=np.array([1+1j,2-1j,3+2j])
    assert np.allclose(relative_response(values),relative_response(values*1e-100),atol=1e-11)
    with pytest.raises(ValueError,match='exact pressure null'):relative_response([1,0,2])


def test_interrupted_search_and_active_trial_are_cancelled(tmp_path,monkeypatch):
    import meh_studio.optimisation as search
    from meh_studio.catalogue import Catalogue
    brief,base,drivers=inputs()
    database=tmp_path/'drivers.sqlite'
    with Catalogue.create(database) as cat:
        for d in drivers:cat.add(d)
    class Runtime:
        def verify(self):return {}
    def interrupt(*args,**kwargs):raise KeyboardInterrupt('cancelled test')
    monkeypatch.setattr(search,'evaluate_candidate',interrupt)
    output=tmp_path/'search'
    with pytest.raises(KeyboardInterrupt):search.optimise(brief,base,database,Runtime(),output)
    report=json.loads((output/'search.json').read_text())
    assert report['status']==report['trials'][0]['status']=='cancelled'


def test_scoring_follows_verified_domain_manifest_paths(tmp_path,monkeypatch):
    import numpy as np
    import meh_studio.optimisation as search
    project=tmp_path/'project.json'
    project.write_text(json.dumps({'physical_system':{'excitation_ports':[
        {'id':'t','component_id':'component:throat'},{'id':'s','component_id':'component:entry'}]}}))
    root=tmp_path/'evaluation/upstream';root.mkdir(parents=True)
    manifest={'domains_metadata_file':'renamed-domain.json','domains_file':'renamed-domain.npz',
              'excitation_port_ids':['t','s'],'results':[]}
    (root/'renamed-domain.json').write_text(json.dumps({'domains':[
        {'id':'observation:horizontal-polar','coordinates':{'angle_deg':'angles'}}]}))
    np.savez(root/'renamed-domain.npz',angles=np.array([-5,0,5]))
    for i in range(3):
        name=f'row-{i}'
        (root/f'{name}.json').write_text(json.dumps({'quantities':[{'id':'acoustic:pressure:horizontal-polar','key':'p'}]}))
        np.savez(root/f'{name}.npz',p=np.ones((2,3),dtype=complex)*(i+1)*1e-100)
        manifest['results'].append({'metadata_file':f'{name}.json','arrays_file':f'{name}.npz'})
    (root/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(search,'verified_assessment',lambda *args:{'checks':{'passed':True}})
    result=search.response_score(project,root.parent,(.5,1.))
    assert result['ripple_db']==pytest.approx(20*np.log10(3))


def test_runtime_change_aborts_after_completed_trial(tmp_path, monkeypatch):
    import meh_studio.optimisation as search
    from meh_studio.catalogue import Catalogue
    brief,base,drivers=inputs();database=tmp_path/'drivers.sqlite'
    with Catalogue.create(database) as catalogue:
        for driver in drivers:catalogue.add(driver)
    class Runtime:
        calls=0
        def verify(self):
            self.calls+=1
            return {'revision':'first' if self.calls<=2 else 'changed'}
    def complete(candidate,root,*args,**kwargs):
        root.mkdir();(root/'candidate.json').write_text('{}');(root/'geometry').mkdir()
        return {'objective':1.,'electrical_validation':{'passed':True}}
    monkeypatch.setattr(search,'evaluate_candidate',complete)
    output=tmp_path/'search'
    with pytest.raises(ValueError,match='runtime changed'):
        search.optimise(brief,base,database,Runtime(),output)
    report=json.loads((output/'search.json').read_text())
    assert report['status']=='failed' and 'winner' not in report
    assert report['trials'][0]['status']=='complete'


@pytest.mark.parametrize('changed',[False,True])
def test_candidate_score_binds_pre_solve_geometry(tmp_path,monkeypatch,changed):
    import meh_studio.optimisation as search
    brief,base,drivers=inputs();candidate=search.candidates(brief,base,drivers)[0]
    def geometry(design,root):
        root.mkdir();(root/'geometry.json').write_text('{"generated":"original"}')
    monkeypatch.setattr(search,'export_geometry',geometry)
    monkeypatch.setattr(search,'mesh_geometry',lambda *args:None)
    monkeypatch.setattr(search,'compile_radiating_system',lambda *args,**kwargs:None)
    monkeypatch.setattr(search,'response_score',lambda *args:{'ripple_db':1.})
    root=tmp_path/'candidate'
    class Runtime:
        def solve(self,project,request,output,**kwargs):
            output.mkdir();(output/'evaluation.json').write_text('{}')
            if changed:(root/'geometry/geometry.json').write_text('{"generated":"changed"}')
    if changed:
        with pytest.raises(ValueError,match='geometry manifest changed'):
            search.evaluate_candidate(candidate,root,Runtime(),brief)
        assert not (root/'score.json').exists()
    else:
        score=search.evaluate_candidate(candidate,root,Runtime(),brief)
        assert score['geometry_manifest_sha256']==search.sha256(root/'geometry/geometry.json')
