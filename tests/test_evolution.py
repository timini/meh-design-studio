import json
from pathlib import Path
import pytest
from meh_studio.optimisation import SearchBrief,candidates,candidate_record
from meh_studio.geometry import HornGeometry
from meh_studio.domain import DriverRevision
from meh_studio.evolution import propose,replay


def inputs():
    root=Path(__file__).resolve().parents[1]/'examples'
    brief=json.loads((root/'synthetic-compact-search-brief.json').read_text())
    brief.update(trial_budget=6,evolution={'elite_size':1,'explore_every':4,
        'geometry_bounds':{'length_m':[.12,.14],'entry_fraction_0':[.36,.5]}})
    return (SearchBrief.model_validate(brief),
            HornGeometry.model_validate_json((root/'freeform-ring-geometry.json').read_text()),
            [DriverRevision.model_validate(v) for v in json.loads((root/'synthetic-search-drivers.json').read_text())])


def test_fitness_changes_parentage_and_shape_with_reproducible_replay():
    brief,base,drivers=inputs();seeds=candidates(brief,base,drivers)
    history=[];previous=[];proposals=[]
    for i in range(brief.trial_budget):
        candidate,proposal=propose(brief,seeds,history,previous)
        previous.append(candidate);proposals.append(proposal)
        history.append({'status':'complete','objective':float(10-i)})
    again,again_proposals=replay(brief,base,drivers,history)
    assert [candidate_record(c) for c in previous]==[candidate_record(c) for c in again]
    assert proposals==again_proposals
    assert proposals[2]['parent_index']==1
    assert proposals[4]['method']=='random_exploration'
    assert len({c['design'].content_hash for c in previous})==len(previous)
    assert all(c['cost']==brief.prices[c['drivers'][0].id]+4*brief.prices[c['drivers'][1].id] for c in previous)
    changed=history[:2];changed[0]=dict(changed[0],objective=-100.)
    _,p=propose(brief,seeds,changed,previous[:2])
    assert p['parent_index']==0


def test_failed_simulation_is_not_an_elite_and_does_not_stop_search():
    brief,base,drivers=inputs();seeds=candidates(brief,base,drivers)
    c0,_=propose(brief,seeds,[],[])
    c1,p=propose(brief,seeds,[{'status':'failed'}],[c0])
    assert p['method']=='random_exploration' and p['parent_index'] is None
    assert c1['design']!=c0['design']


def test_evolution_contract_rejects_invalid_bounds():
    brief,_,_=inputs()
    with pytest.raises(ValueError):SearchBrief.model_validate(brief.model_dump()|{'evolution':{'geometry_bounds':{'entry_fraction_0':[.5,1.]}}})


@pytest.mark.parametrize('preserve_error',[False,True])
def test_adaptive_resume_preserves_failed_parent_history(tmp_path,monkeypatch,preserve_error):
    import meh_studio.optimisation as search
    import meh_studio.search_resume as recovery
    import meh_studio.export_validation as exports
    from meh_studio.catalogue import Catalogue
    from test_search_resume import fake_evaluate,fake_score,Runtime
    brief,base,drivers=inputs()
    brief=SearchBrief.model_validate(brief.model_dump()|{'trial_budget':4})
    database=tmp_path/'catalogue.sqlite'
    with Catalogue.create(database) as catalogue:
        for driver in drivers:catalogue.add(driver)
    def interrupted(candidate,root,*args,**kwargs):
        if root.name=='trial-001':
            root.mkdir();(root/'failed-native.txt').write_text('retained failed experiment')
            raise ValueError('native solver failure fixture')
        if root.name=='trial-002':raise KeyboardInterrupt('stop')
        return fake_evaluate(candidate,root,*args,**kwargs)
    monkeypatch.setattr(search,'evaluate_candidate',interrupted)
    original=tmp_path/'original'
    with pytest.raises(KeyboardInterrupt):search.optimise(brief,base,database,Runtime(),original)
    before=recovery._inventory(original)
    monkeypatch.setattr(recovery,'response_score',fake_score)
    monkeypatch.setattr(recovery,'verify_candidate_project',lambda *args:None)
    monkeypatch.setattr(exports,'validate_export',lambda *args:None)
    calls=[]
    def evaluate(candidate,root,*args,**kwargs):
        calls.append(root.name)
        return fake_evaluate(candidate,root,*args,**kwargs)
    monkeypatch.setattr(search,'evaluate_candidate',evaluate)
    continued=tmp_path/'continued'
    if preserve_error:
        def reject(*args):raise ValueError('failed evidence mismatch fixture')
        monkeypatch.setattr(recovery.Recovery,'preserve_failed',reject)
        with pytest.raises(ValueError,match='failed evidence mismatch'):
            recovery.resume_optimise(original,Runtime(),continued)
        assert json.loads((continued/'search.json').read_text())['status']=='failed'
        assert not (continued/'winner-geometry').exists()
        return
    result=recovery.resume_optimise(original,Runtime(),continued)
    assert calls==['trial-002','trial-003']
    assert result['recovery']['preserved_failed_trial_indices']==[1]
    assert (continued/'trial-001/failed-native.txt').read_text()=='retained failed experiment'
    assert recovery._inventory(original)==before
    planned,proposals=replay(brief,base,drivers,result['trials'])
    assert proposals==result['proposals']
    for index in (0,2,3):
        assert candidate_record(planned[index])==json.loads((continued/f'trial-{index:03d}/candidate.json').read_text())


@pytest.mark.parametrize('fault',['score','missing_evaluation'])
def test_export_rejects_corrupt_nonwinning_fitness_evidence(tmp_path,monkeypatch,fault):
    import meh_studio.optimisation as search
    import meh_studio.search_resume as recovery
    import meh_studio.search_results as results
    import meh_studio.export_validation as exports
    from meh_studio.catalogue import Catalogue
    from meh_studio.boundary_lab import sha256
    from test_search_resume import fake_evaluate,fake_score,Runtime
    brief,base,drivers=inputs()
    brief=SearchBrief.model_validate(brief.model_dump()|{'trial_budget':3})
    database=tmp_path/'catalogue.sqlite'
    with Catalogue.create(database) as catalogue:
        for driver in drivers:catalogue.add(driver)
    monkeypatch.setattr(search,'evaluate_candidate',fake_evaluate)
    monkeypatch.setattr(recovery,'response_score',fake_score)
    monkeypatch.setattr(recovery,'verify_candidate_project',lambda *args:None)
    monkeypatch.setattr(exports,'validate_export',lambda *args:None)
    monkeypatch.setattr(results,'verified_assessment',lambda project,evaluation:{'controls':{'evaluation.json':sha256(evaluation/'evaluation.json')}})
    output=tmp_path/'search';report=search.optimise(brief,base,database,Runtime(),output)
    for trial in output.glob('trial-*'):(trial/'evaluation/preflight.json').write_text('{}')
    controls,*_=results.load_completed_search(output)
    other=next(i for i in range(3) if i!=report['winner_index'])
    assert f'trial-{other:03d}/evaluation/evaluation.json' in controls
    if fault=='score':
        path=output/f'trial-{other:03d}/score.json'
        value=json.loads(path.read_text());value['objective']-=.001
        path.write_text(json.dumps(value))
    else:(output/f'trial-{other:03d}/evaluation/evaluation.json').unlink()
    with pytest.raises((ValueError,OSError)):results.load_completed_search(output)


def test_default_symmetry_preserves_existing_seeded_search_identity():
    import hashlib
    brief,base,drivers=inputs();seeds=candidates(brief,base,drivers)
    assert 'profile_symmetry' not in brief.model_dump()['evolution']
    history=[];previous=[];records=[]
    for i in range(6):
        candidate,proposal=propose(brief,seeds,history,previous)
        previous.append(candidate);records.append({'candidate':candidate_record(candidate),'proposal':proposal})
        history.append({'status':'complete','objective':float(10-i)})
    # Captured from the unchanged v1 implementation before adding symmetry controls.
    digest=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert digest=='85ed3a06601ec65269059ee8e15887371575392781b68196947216660f27da80'


def symmetric_inputs(symmetry):
    brief,base,drivers=inputs()
    data=base.model_dump(mode='json')
    data['profile_interpolation']='periodic_cubic'
    for section in data['profile_sections']:
        section['radial_scales']=[1.,1.1,1.,1.1,1.,1.1,1.,1.1]
    base=HornGeometry.model_validate(data)
    brief=SearchBrief.model_validate(brief.model_dump()|{'evolution':brief.evolution.model_dump()|{'profile_symmetry':symmetry}})
    return brief,base,drivers


@pytest.mark.parametrize('symmetry',['mirror_xy','quarter_turn'])
def test_linked_profile_mutation_and_random_exploration_preserve_symmetry(symmetry):
    brief,base,drivers=symmetric_inputs(symmetry);seeds=candidates(brief,base,drivers)
    history=[];previous=[];proposals=[]
    for index in range(6):
        candidate,proposal=propose(brief,seeds,history,previous)
        for section in candidate['design'].profile_sections:
            v=section.radial_scales
            assert v[0]==v[4] and v[2]==v[6] and v[1]==v[3]==v[5]==v[7]
            if symmetry=='quarter_turn':assert v[0]==v[2]
        previous.append(candidate);proposals.append(proposal)
        history.append({'status':'complete','objective':float(10-index)})
    assert proposals[4]['method']=='random_exploration'
    assert any(m.get('columns') for p in proposals for m in p.get('mutations',[]))
    again,again_proposals=replay(brief,base,drivers,history)
    assert proposals==again_proposals
    assert [candidate_record(c) for c in previous]==[candidate_record(c) for c in again]
    assert json.loads(json.dumps(proposals))==proposals
    assert len({c['design'].content_hash for c in previous})==6


@pytest.mark.parametrize('symmetry',['mirror_xy','quarter_turn'])
def test_symmetry_rejects_a_seed_with_unequal_linked_controls(symmetry):
    brief,base,drivers=symmetric_inputs(symmetry)
    data=base.model_dump(mode='json');data['profile_sections'][0]['radial_scales'][0]=1.01
    base=HornGeometry.model_validate(data)
    with pytest.raises(ValueError,match='symmetry'):
        propose(brief,candidates(brief,base,drivers),[],[])


@pytest.mark.cad
def test_quarter_turn_offspring_changes_real_cad_and_preserves_ring_rotation():
    pytest.importorskip('cadquery')
    import numpy as np
    from meh_studio.geometry import build_geometry
    from meh_studio.waveguide_profile import cad_volume
    brief,base,drivers=symmetric_inputs('quarter_turn');seeds=candidates(brief,base,drivers)
    first,_=propose(brief,seeds,[],[])
    offspring,_=propose(brief,seeds,[{'status':'complete','objective':10.}],[first])
    design=offspring['design'];assert design!=base
    regions,parts,sources=build_geometry(design)
    # The solved front air and exported horn shell share the quarter-turn shape.
    for shape in (regions['front'],parts['horn']):
        rotated=shape.rotate((0,0,0),(0,0,1),90)
        difference=cad_volume(design,shape.cut(rotated))+cad_volume(design,rotated.cut(shape))
        assert difference<=max(1e-3,1e-7*cad_volume(design,shape))
    centers=np.array([s['front_center_m'] for s in sources])
    rotated=centers[:,[1,0,2]].copy();rotated[:,0]*=-1
    for center in rotated:
        assert np.linalg.norm(centers-center,axis=1).min()<1e-9
    # Offspring are nonconical: their declared sections have nonuniform radial/axial controls.
    assert any(len(set(section.radial_scales))>1 for section in design.profile_sections)


def test_symmetry_search_requires_geometry_to_declare_periodic_interpolation():
    brief,base,drivers=symmetric_inputs('quarter_turn')
    base=HornGeometry.model_validate(base.model_dump()|{'profile_interpolation':'legacy'})
    with pytest.raises(ValueError,match='periodic_cubic'):
        propose(brief,candidates(brief,base,drivers),[],[])
