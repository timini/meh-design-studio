import json
import numpy as np
import pytest
from meh_studio.acoustic_handover import acoustic_handover
from meh_studio.acoustic_objectives import AcousticObjectives,drive_weights,freeze_brief,score_acoustics


def test_channel_dominance_checks_all_band_samples_and_retains_exact_nulls():
    f=[350.,2000.,3000.,4000.,5000.,7500.]
    mid=[1.,1.,1.,1.,.5,0.];hf=[0.,.5,1.,2.,1.,1.]
    report=acoustic_handover(f,mid,hf,350.,(3000.,5000.))
    assert report['passed'] and report['hf_channel_null'][0] and report['mid_channel_null'][-1]
    assert report['mid_over_hf_db'][0]==120 and report['mid_over_hf_db'][-1]==-120
    json.dumps(report,allow_nan=False)
    mid[1]=.1
    report=acoustic_handover(f,mid,hf,350.,(3000.,5000.))
    assert not report['passed'] and report['mid_dominance_failed_hz']==[2000.]
    mid[1]=1.;mid[-1]=2.
    report=acoustic_handover(f,mid,hf,350.,(3000.,5000.))
    assert not report['passed'] and report['hf_dominance_failed_hz']==[7500.]
    mid[0]=0.
    assert 350. in acoustic_handover(f,mid,hf,350.,(3000.,5000.))['mid_dominance_failed_hz']


def test_no_interpolation_substitutes_for_handover_boundary_samples():
    with pytest.raises(ValueError,match='explicit'):
        acoustic_handover([350.,2000.,7500.],[1.,1.,.1],[.01,.1,1.],350.,(3000.,5000.))


@pytest.mark.parametrize('window',[(5000.,3000.),(3000.,3000.),(300.,5000.),(3000.,float('nan'))])
def test_invalid_handover_windows_rejected(window):
    with pytest.raises(ValueError):AcousticObjectives(acoustic_handover_hz=window)


def test_opt_in_contract_preserves_legacy_identity_and_survives_frozen_dsp():
    from test_optimisation import inputs
    from meh_studio.optimisation import SearchBrief
    legacy=AcousticObjectives()
    assert 'acoustic_handover_hz' not in legacy.model_dump(mode='json')
    assert legacy.content_hash==AcousticObjectives(acoustic_handover_hz=None).content_hash
    brief,_,_=inputs()
    data=brief.model_dump()|{'frequencies_hz':[300.,350.,2000.,3000.,5000.,7500.],
        'acoustic_objectives':{'acoustic_handover_hz':[3000.,5000.]}}
    brief=SearchBrief.model_validate(data)
    settings={'side_gain':.5,'mid_highpass_hz':350.,'upper_crossover_hz':4000.,'mid_polarity':1,'hf_delay_s':0.}
    frozen=freeze_brief(brief,.5,settings)
    assert frozen.acoustic_objectives.acoustic_handover_hz==(3000.,5000.)
    for missing in (350.,3000.,5000.):
        with pytest.raises(ValueError,match='explicit'):
            SearchBrief.model_validate(data|{'frequencies_hz':[f for f in data['frequencies_hz'] if f!=missing]})


def test_scoring_uses_coherent_mid_bank_and_rejects_filter_only_handover(tmp_path,monkeypatch):
    import meh_studio.optimisation as optimisation
    # A deliberately constructed basis tests selection, not native acoustic accuracy.
    monkeypatch.setattr(optimisation,'verified_assessment',lambda *args:{'checks':{'passed':False}})
    ids=['component:mid_a','component:throat','component:mid_b','component:mid_c','component:mid_d']
    project=tmp_path/'project.json'
    project.write_text(json.dumps({'physical_system':{'components':[{'id':c} for c in ids],'excitation_ports':[
        {'id':str(i),'component_id':c} for i,c in enumerate(ids)]}}))
    root=tmp_path/'evaluation/upstream';root.mkdir(parents=True)
    domains=[{'id':f'observation:{p}-polar','coordinates':{'angle_deg':'angles'}} for p in ('horizontal','vertical')]
    (root/'domains.json').write_text(json.dumps({'domains':domains}))
    np.savez(root/'domains.npz',angles=[-45.,0.,45.])
    quantities=[{'id':f'acoustic:pressure:{p}-polar','key':'polar'} for p in ('horizontal','vertical')]
    quantities.append({'id':'electrical:voice-coil-current','key':'current','metadata':{'component_ids':ids}})
    (root/'row.json').write_text(json.dumps({'quantities':quantities,'diagnostics':{'transducer_reference_voltage_v':2.83}}))
    f=[350.,1000.,2000.,3000.,4000.,5000.,7500.]
    settings={'side_gain':1.,'mid_highpass_hz':350.,'upper_crossover_hz':4000.,'mid_polarity':1,'hf_delay_s':0.}
    weights=drive_weights(f,ids,settings)
    mid=np.array([1.,1.,1.,1.,.6,.2,.05]);hf=np.array([.001,.05,.1,.5,.6,1.,1.])
    def write_basis(cancel_mids=False):
        for i in range(len(f)):
            desired=np.array([mid[i]/4,hf[i],mid[i]/4,mid[i]/4,mid[i]/4],complex)
            if cancel_mids:desired[[3,4]]*=-1
            basis=(desired/weights[i])[:,None]*np.array([.5,1.,.5])[None,:]
            np.savez(root/f'row-{i}.npz',polar=basis,current=2.83*np.eye(5)/16)
    write_basis()
    (root/'manifest.json').write_text(json.dumps({'phasor_convention':'exp(-i omega t)',
        'excitation_port_ids':[str(i) for i in range(5)],'domains_metadata_file':'domains.json',
        'domains_file':'domains.npz','results':[{'freq_hz':v,'metadata_file':'row.json','arrays_file':f'row-{i}.npz'} for i,v in enumerate(f)]}))
    objectives=AcousticObjectives(upper_crossovers_hz=(4000.,),mid_polarities=(1,),hf_delays_s=(0.,),
        acoustic_handover_hz=(3000.,5000.))
    with pytest.raises(ValueError,match='handover window'):
        score_acoustics(project,root.parent,(.25,),objectives)
    score=score_acoustics(project,root.parent,(.25,1.),objectives)
    assert score['side_gain']==1. and score['acoustic_handover']['passed']
    assert score['electrical_validation']['passed'] is False
    assert score['acoustic_handover']['mid_over_hf_db'][3]==pytest.approx(20*np.log10(2.))
    write_basis(cancel_mids=True)
    with pytest.raises(ValueError,match='handover window'):
        score_acoustics(project,root.parent,(1.,),objectives)
