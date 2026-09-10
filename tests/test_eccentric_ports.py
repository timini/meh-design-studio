"""Independent port/driver placement through geometry and evolutionary proposals."""
import json
from pathlib import Path
import pytest
from meh_studio.geometry import HornGeometry,build_geometry,export_geometry,mesh_geometry


def example():
    return json.loads((Path(__file__).resolve().parents[1]/'examples/freeform-ring-geometry.json').read_text())


def test_port_can_move_toward_throat_while_driver_clears_it():
    data=example()|{'entry_positions_m':[.02],'driver_axial_offset_m':.01}
    design=HornGeometry.model_validate(data)
    assert design.entry_positions_m[0]<design.front_radius_m+design.wall_m
    assert design.entry_positions_m[0]+design.driver_axial_offset_m>design.front_radius_m+design.wall_m
    with pytest.raises(ValueError,match='chambers must clear'):
        HornGeometry.model_validate(data|{'driver_axial_offset_m':0.})


@pytest.mark.parametrize('change',[
    {'driver_axial_offset_m':.015}, # Port would protrude beyond chamber face.
    {'driver_axial_offset_m':-.015},
    {'entry_positions_m':[.008],'driver_axial_offset_m':.01},
    {'driver_axial_offset_m':float('nan')},
])
def test_eccentric_port_keeps_aperture_and_envelope_constraints(change):
    with pytest.raises(ValueError):HornGeometry.model_validate(example()|change)


def test_zero_offset_preserves_historical_geometry_identity():
    before=HornGeometry.model_validate(example());explicit=HornGeometry.model_validate(example()|{'driver_axial_offset_m':0.})
    assert before.content_hash==explicit.content_hash
    assert 'driver_axial_offset_m' not in explicit.model_dump(mode='json')


def test_evolution_mutates_and_replays_signed_offset():
    from test_evolution import inputs
    from meh_studio.optimisation import SearchBrief,candidates,candidate_record
    from meh_studio.evolution import propose,replay
    brief,base,drivers=inputs()
    evolution=brief.evolution.model_dump(mode='json')
    evolution['geometry_bounds']['driver_axial_offset_m']=[-.003,.003]
    brief=SearchBrief.model_validate(brief.model_dump(mode='json')|{'evolution':evolution})
    seeds=candidates(brief,base,drivers);history=[];previous=[];reports=[]
    for _ in range(brief.trial_budget):
        candidate,report=propose(brief,seeds,history,previous)
        previous.append(candidate);reports.append(report);history.append({'status':'complete','objective':float(len(history))})
    recovered,recovered_reports=replay(brief,base,drivers,history)
    assert [candidate_record(c) for c in previous]==[candidate_record(c) for c in recovered]
    assert reports==recovered_reports
    assert any(abs(c['design'].driver_axial_offset_m)>0 for c in previous)
    with pytest.raises(ValueError,match='must be positive'):
        SearchBrief.model_validate(brief.model_dump(mode='json')|{'evolution':{'geometry_bounds':{'port_length_m':[-.01,.01]}}})


@pytest.mark.cad
def test_offset_changes_real_aperture_without_relocating_driver():
    from meh_studio.cad_runtime import load_cadquery
    cq=load_cadquery()
    baseline=HornGeometry.model_validate(example())
    design=HornGeometry.model_validate(example()|{'entry_positions_m':[baseline.entry_positions_m[0]-.01],
                                                 'driver_axial_offset_m':.01})
    air,parts,sources=build_geometry(design)
    _,_,original_sources=build_geometry(baseline)
    assert sources==original_sources
    source=next(s for s in sources if s['id']=='entry_0_positive')
    x=source['front_center_m'][0]-design.front_depth_m-design.wall_m/2
    def point(z):return cq.Vector(x*1000,0,z*1000)
    assert air['front'].isInside(point(design.entry_positions_m[0]),1e-6)
    assert not air['front'].isInside(point(source['front_center_m'][2]),1e-6)
    assert parts['horn'].isInside(point(source['front_center_m'][2]),1e-6)
    for a in air.values():
        for p in parts.values():assert a.intersect(p).Volume()<1e-3


@pytest.mark.cad
def test_near_throat_eccentric_port_exports_and_meshes(tmp_path):
    design=HornGeometry.model_validate(example()|{'entry_positions_m':[.02],'driver_axial_offset_m':.01})
    root=tmp_path/'geometry';report=export_geometry(design,root)
    assert all(s['front_center_m'][2]==pytest.approx(.03) for s in report['sources'])
    result=mesh_geometry(root)
    assert result['status']=='complete'
    assert all(check['relative_area_error']<=.01 for r in result['regions'] for check in r['source_area_checks'])
