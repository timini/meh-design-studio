import numpy as np
import pytest
from meh_studio.acoustic_objectives import AcousticObjectives,lr4,drive_weights,polar_error,parallel_bank,freeze_brief


def test_lr4_crossover_complement_has_unity_magnitude_and_minus_six_db_at_crossover():
    frequencies=np.geomspace(100,10000,121)
    low=lr4(frequencies,1000,'lowpass');high=lr4(frequencies,1000,'highpass')
    np.testing.assert_allclose(abs(low+high),1,rtol=1e-13)
    assert abs(lr4([1000],1000,'lowpass')[0])==pytest.approx(.5)
    assert abs(lr4([1000],1000,'highpass')[0])==pytest.approx(.5)


def test_parallel_mids_share_voltage_and_delay_uses_native_phasor():
    ids=['component:mid_b','component:throat','component:mid_a']
    settings={'side_gain':.4,'mid_highpass_hz':350.,'upper_crossover_hz':5000.,'mid_polarity':-1,'hf_delay_s':.0001}
    weights=drive_weights([1000.,5000.],ids,settings)
    np.testing.assert_array_equal(weights[:,0],weights[:,2])
    no_delay=drive_weights([1000.,5000.],ids,settings|{'hf_delay_s':0.})
    np.testing.assert_allclose(weights[:,1]/no_delay[:,1],np.exp(2j*np.pi*np.array([1000.,5000.])*.0001))


def test_parallel_input_includes_mutual_current_and_holds_hf_at_zero_voltage():
    # Symmetric passive admittance. Two 8-ohm self admittances plus 0.025 S mutual.
    y=np.array([[.2,.01,.01],[.01,.125,.025],[.01,.025,.125]],complex)
    basis=np.array([2.83*y.T])
    bank=parallel_bank(basis,['component:throat','component:mid_a','component:mid_b'])
    assert bank['minimum_impedance_magnitude_ohm']==pytest.approx(1/.3)
    assert bank['maximum_current_per_volt_a']==pytest.approx(.3)
    assert bank['amplifier_channels_for_mids']==1


def test_reduced_bank_matches_four_physical_mids_and_enforces_two_ohm_limit():
    from meh_studio.acoustic_objectives import _score_acoustic_basis
    full_ids=['component:throat','x+','x-','y+','y-']
    reduced_ids=['component:throat','x','y']
    y=np.full((5,5),.01);np.fill_diagonal(y,.125);y[0,0]=.2
    assert np.linalg.eigvalsh(y).min()>0  # Independent passive five-port network.
    full_current=2.83*y.T
    groups=[[0],[1,2],[3,4]]
    reduced_current=np.stack([full_current[g].sum(axis=0)[[0,1,3]] for g in groups])
    full=parallel_bank([full_current],full_ids)
    reduced=parallel_bank([reduced_current],reduced_ids,physical_driver_orbit_counts=[1,2,2])
    assert reduced==full
    assert reduced['mid_count']==4 and reduced['minimum_impedance_magnitude_ohm']<2.
    assert parallel_bank([reduced_current],reduced_ids)['minimum_impedance_magnitude_ohm']>2.
    angles={p:np.array([-45.,0.,45.]) for p in ('horizontal','vertical')}
    pressure=np.array([1.,.25,.25,.25,.25])[:,None]*np.array([.5,1.,.5])
    reduced_pressure=np.stack([pressure[g].sum(axis=0) for g in groups])
    targets=AcousticObjectives(upper_crossovers_hz=(2000.,),mid_polarities=(1,),hf_delays_s=(0.,),minimum_bank_impedance_ohm=2.)
    for ids,current,p,counts in [(full_ids,full_current,pressure,None),
                                  (reduced_ids,reduced_current,reduced_pressure,[1,2,2])]:
        with pytest.raises(ValueError,match='violates 2 ohm'):
            _score_acoustic_basis([1000.],ids,angles,{plane:[p] for plane in angles},[current],(1.,),targets,
                                   physical_driver_orbit_counts=counts)
    unrestricted=targets.model_copy(update={'minimum_bank_impedance_ohm':None})
    scores=[_score_acoustic_basis([1000.],ids,angles,{plane:[p] for plane in angles},[current],(1.,),unrestricted,
                                   physical_driver_orbit_counts=counts)
            for ids,current,p,counts in [(full_ids,full_current,pressure,None),
                                         (reduced_ids,reduced_current,reduced_pressure,[1,2,2])]]
    assert scores[0]['drive_settings']==scores[1]['drive_settings']
    for key in ['mid_bank_real_a','mid_bank_imag_a','hf_real_a','hf_imag_a']:
        np.testing.assert_allclose(scores[0]['parallel_mid_bank']['selected_drive_currents'][key],
                                   scores[1]['parallel_mid_bank']['selected_drive_currents'][key],rtol=1e-13)


@pytest.mark.parametrize('counts',[[1,True],[1.,2.],[1,0],[1,-2],[1,5],[1],[1,'2']])
def test_bank_rejects_invalid_physical_multiplicity(counts):
    with pytest.raises(ValueError,match='orbit count'):
        parallel_bank([np.eye(2)],['component:throat','mid'],physical_driver_orbit_counts=counts)


def test_polar_target_rewards_coverage_and_rejects_a_narrow_beam():
    angles=np.arange(-90,91,5.)
    desired=10**((-6*(angles/45)**2)/20)
    smooth=polar_error(np.array([desired,desired]),angles,90.)
    narrow=polar_error(np.array([desired**3,desired**3]),angles,90.)
    assert smooth['rms_target_error_db']<1e-12
    assert narrow['rms_target_error_db']>10


def test_targets_reject_missing_crossover_coverage():
    from test_optimisation import inputs
    from meh_studio.optimisation import SearchBrief
    brief,_,_=inputs()
    with pytest.raises(ValueError,match='grid must cover'):
        SearchBrief.model_validate(brief.model_dump()|{'acoustic_objectives':{}})


def test_frozen_brief_keeps_single_crossover_polarity_delay():
    from test_optimisation import inputs
    from meh_studio.optimisation import SearchBrief
    brief,_,_=inputs()
    brief=SearchBrief.model_validate(brief.model_dump()|{'frequencies_hz':[350.,1000.,8000.],'acoustic_objectives':{}})
    settings={'side_gain':.5,'mid_highpass_hz':350.,'upper_crossover_hz':4000.,'mid_polarity':-1,'hf_delay_s':0.}
    frozen=freeze_brief(brief,.5,settings)
    assert frozen.acoustic_objectives.upper_crossovers_hz==(4000.,)
    assert frozen.acoustic_objectives.mid_polarities==(-1,)
    assert frozen.side_gains==(.5,)


@pytest.mark.parametrize('value',[0.,-1.,float('nan'),float('inf'),True,'20'])
def test_invalid_observation_distance_rejected(value):
    with pytest.raises(ValueError):AcousticObjectives(observation_distance_m=value)


def test_observation_distance_is_preserved_by_frozen_and_denser_finalist_controls():
    from test_optimisation import inputs
    from meh_studio.optimisation import SearchBrief
    from meh_studio.spherical_metrics import denser_validation_brief
    brief,_,_=inputs()
    legacy=AcousticObjectives()
    assert 'observation_distance_m' not in legacy.model_dump(mode='json')
    targets=AcousticObjectives(observation_distance_m=20.,sphere={})
    assert targets.content_hash!=legacy.content_hash
    assert AcousticObjectives.model_validate_json(targets.canonical_json())==targets
    brief=SearchBrief.model_validate(brief.model_dump()|{'frequencies_hz':[350.,1000.,8000.],
        'acoustic_objectives':targets.model_dump(mode='json')})
    settings={'side_gain':.5,'mid_highpass_hz':350.,'upper_crossover_hz':4000.,'mid_polarity':1,'hf_delay_s':0.}
    frozen=denser_validation_brief(freeze_brief(brief,.5,settings))
    assert frozen.acoustic_objectives.observation_distance_m==20.


def test_scoring_and_convergence_reject_a_different_observation_distance(tmp_path,monkeypatch):
    import json
    import meh_studio.optimisation as search
    from meh_studio.acoustic_objectives import score_acoustics,convergence_polars
    monkeypatch.setattr(search,'verified_assessment',lambda *args:{})
    project=tmp_path/'project.json'
    project.write_text(json.dumps({'project_preferences':{'polar_observation_distance_m':1.}}))
    objectives=AcousticObjectives(observation_distance_m=20.)
    with pytest.raises(ValueError,match='observation distance differs'):
        score_acoustics(project,tmp_path,(1.,),objectives)
    with pytest.raises(ValueError,match='observation distance differs'):
        convergence_polars(project,tmp_path,{},objectives)
