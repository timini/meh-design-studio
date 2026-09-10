import numpy as np
import pytest
from meh_studio.spherical_metrics import SphericalObjectives, fibonacci_directions, sphere_geometry, sphere_error
from meh_studio.acoustic_objectives import AcousticObjectives


def test_isotropic_pressure_has_zero_axis_to_sphere_difference():
    points=fibonacci_directions(413)
    result=sphere_error(np.full((2,413),2+3j),[2+3j,2+3j],[1000.,2000.],points,SphericalObjectives(),90,90)
    np.testing.assert_allclose(result['on_axis_to_sphere_mean_db'],0.,atol=1e-12)
    assert result['solid_angle_weight_sr']*413==pytest.approx(4*np.pi)
    assert result['radiated_power_or_efficiency_qualified'] is False


def test_sphere_detects_lobes_that_leave_both_principal_cuts_unchanged():
    points=fibonacci_directions(413)
    isotropic=np.ones((1,413),complex)
    # The perturbation vanishes identically in both x=0 and y=0 polar planes.
    diagonal_lobes=1+100*(points[:,0]*points[:,1])**2
    settings=SphericalObjectives()
    base=sphere_error(isotropic,[1.],[2000.],points,settings,90,90)
    lobed=sphere_error(diagonal_lobes[None,:],[1.],[2000.],points,settings,90,90)
    assert lobed['rms_target_error_db']>base['rms_target_error_db']+5
    assert lobed['sphere_mean_square_pressure_relative_to_axis'][0]>10


def test_declared_spherical_target_is_exact_and_partial_grid_is_rejected():
    points=2*fibonacci_directions(413)
    target,radius,weight=sphere_geometry(points,90,60,30)
    pressure=10**(target/20)
    result=sphere_error(pressure[None,:],[1.],[2000.],points,SphericalObjectives(),90,60)
    assert result['rms_target_error_db']<1e-12 and radius==pytest.approx(2.)
    with pytest.raises(ValueError,match='complete pinned'):
        sphere_geometry(points[:-1],90,60,30)


def test_legacy_objective_serialisation_does_not_gain_a_sphere_field():
    assert 'sphere' not in AcousticObjectives().model_dump(mode='json')
    assert AcousticObjectives(sphere=SphericalObjectives()).model_dump(mode='json')['sphere']['angle_precision_deg']==10.


def test_declared_precision_must_match_the_saved_grid():
    with pytest.raises(ValueError,match='declared angular precision'):
        sphere_error(np.ones((1,413)),[1.],[2000.],fibonacci_directions(413),
                     SphericalObjectives(angle_precision_deg=5.),90,90)


def test_finalist_adds_directions_without_changing_frozen_dsp():
    from test_optimisation import inputs
    from meh_studio.optimisation import SearchBrief
    from meh_studio.spherical_metrics import denser_validation_brief
    original,_,_=inputs()
    brief=SearchBrief.model_validate(original.model_dump()|{'frequencies_hz':[350.,1000.,8000.],
        'side_gains':[.4],'acoustic_objectives':{'sphere':{},'upper_crossovers_hz':[3000.],
        'mid_polarities':[-1],'hf_delays_s':[.0003]}})
    denser=denser_validation_brief(brief)
    assert denser.acoustic_objectives.sphere.angle_precision_deg==5.
    data=denser.model_dump(mode='json')
    data['acoustic_objectives']['sphere']['angle_precision_deg']=10.
    assert data==brief.model_dump(mode='json')
    assert denser_validation_brief(original) is original
    with pytest.raises(ValueError,match='2.5 degree minimum'):
        denser_validation_brief(denser_validation_brief(denser))


def test_whole_sphere_score_reads_native_basis_and_preserves_failed_validation(tmp_path,monkeypatch):
    import json
    import meh_studio.optimisation as optimisation
    from meh_studio.acoustic_objectives import score_acoustics,convergence_polars
    # Contract fixture, not native acoustic evidence. The verifier is isolated here.
    monkeypatch.setattr(optimisation,'verified_assessment',lambda *args:{'checks':{'passed':False}})
    project=tmp_path/'project.json'
    ids=['component:throat','component:mid']
    project.write_text(json.dumps({'physical_system':{'excitation_ports':[
        {'id':str(i),'component_id':c} for i,c in enumerate(ids)]}}))
    root=tmp_path/'evaluation/upstream';root.mkdir(parents=True)
    domains=[{'id':f'observation:{p}-polar','coordinates':{'angle_deg':'angles'}} for p in ('horizontal','vertical')]
    domains.append({'id':'observation:sphere','coordinates':{'points_m':'points'}})
    (root/'domains.json').write_text(json.dumps({'domains':domains}))
    points=fibonacci_directions(413)
    np.savez(root/'domains.npz',angles=[-45.,0.,45.],points=points)
    quantities=[{'id':f'acoustic:pressure:{p}-polar','key':'polar'} for p in ('horizontal','vertical')]
    quantities+=[{'id':'acoustic:pressure:sphere','key':'sphere'},
        {'id':'electrical:voice-coil-current','key':'current','metadata':{'component_ids':ids}}]
    (root/'row.json').write_text(json.dumps({'quantities':quantities,
        'diagnostics':{'transducer_reference_voltage_v':2.83}}))
    manifest={'phasor_convention':'exp(-i omega t)','excitation_port_ids':['0','1'],
        'domains_metadata_file':'domains.json','domains_file':'domains.npz',
        'results':[{'freq_hz':2000.,'metadata_file':'row.json','arrays_file':'row.npz'}]}
    (root/'manifest.json').write_text(json.dumps(manifest))
    settings=AcousticObjectives(sphere=SphericalObjectives(),upper_crossovers_hz=(3000.,),
        mid_polarities=(1,),hf_delays_s=(0.,))
    scores=[]
    for shape in (np.ones(413),1+100*(points[:,0]*points[:,1])**2):
        np.savez(root/'row.npz',polar=np.ones((2,3),complex),sphere=np.tile(shape,(2,1)),
                 current=2.83*np.eye(2)/8)
        scores.append(score_acoustics(project,root.parent,(1.,),settings))
    assert scores[1]['acoustic_objective']>scores[0]['acoustic_objective']
    assert scores[1]['polars']==scores[0]['polars']
    assert scores[1]['electrical_validation']['passed'] is False
    pressure,coordinates=convergence_polars(project,root.parent,scores[1]['drive_settings'],settings)
    assert pressure.shape==(1,419) and len(coordinates)==419
    assert sum(c['plane']=='sphere' for c in coordinates)==413
    (root/'domains.json').write_text(json.dumps({'domains':domains[:-1]}))
    with pytest.raises(ValueError,match='complete native sphere'):
        score_acoustics(project,root.parent,(1.,),settings)
