import numpy as np
import pytest
from meh_studio.operating import operating_quantities


def test_rms_scaling_mutual_currents_peak_excursion_and_signed_power():
    # Two-port passive resistor network, independently known I = Y V.
    # Receiving-port order differs from voltage basis excitation orientation.
    ids=('a','b');f=[1000.]
    y=np.array([[.2,-.1],[-.1,.1]])
    voltage=np.array([[1.,3.]])
    velocity=np.array([[[.01,.004],[.002,.02]]])
    p=np.array([[[2.],[1j]]])
    report=operating_quantities(f,ids,voltage,p,[y.T],velocity,[4.,8.])
    np.testing.assert_allclose(report['current'],[[-.1,.2]])
    np.testing.assert_allclose(report['power'],[[-.1,.6]])
    np.testing.assert_allclose(report['total_power'],[.5])
    np.testing.assert_allclose(report['coil_loss'],[[.04,.32]])
    np.testing.assert_allclose(report['pressure'],[[2+3j]])
    np.testing.assert_allclose(report['peak_excursion'],np.sqrt(2)*np.array([[.016,.064]])/(2*np.pi*1000))
    doubled=operating_quantities(f,ids,2*voltage,p,[y.T],velocity,[4.,8.])
    np.testing.assert_allclose(doubled['pressure'],2*report['pressure'])
    np.testing.assert_allclose(doubled['peak_excursion'],2*report['peak_excursion'])
    np.testing.assert_allclose(doubled['coil_loss'],4*report['coil_loss'])


def test_native_reference_convention_cancels_in_transfer_ratios():
    ids=('a',);voltage=[[3.]]
    # The same linear transfer represented with two arbitrary native amplitudes.
    reports=[]
    for native in (2.83,2.83*np.sqrt(2)):
        reports.append(operating_quantities([1000.],ids,voltage,
            np.array([[[4*native]]])/native,np.array([[[.2*native]]])/native,
            np.array([[[.001*native]]])/native,[5.]))
    for key in reports[0]:np.testing.assert_allclose(reports[0][key],reports[1][key])


def test_operating_rejects_missing_receiving_driver():
    with pytest.raises(ValueError,match='every component'):
        operating_quantities([1000.],('a','b'),[[1.,1.]],[[[1.],[1.]]],
                             [[[1.],[1.]]],[[[1.],[1.]]],[4.,4.])


@pytest.mark.parametrize('transformed', [False, True])
def test_report_uses_manifest_coordinates_and_reorders_component_columns(tmp_path,monkeypatch,source,transformed):
    import json
    import meh_studio.search_results as search_results
    import meh_studio.optimisation as optimisation
    from meh_studio.operating import search_operating_report
    from meh_studio.acoustic_objectives import drive_weights
    root=tmp_path/'trial-000/evaluation/upstream';root.mkdir(parents=True)
    system_path=tmp_path/'trial-000/system';system_path.mkdir()
    ids=['component:mid','component:throat']
    settings={'side_gain':.5,'mid_highpass_hz':350.,'upper_crossover_hz':3000.,'mid_polarity':1,'hf_delay_s':0.}
    saved=({'search.json':'original'}, {'winner_index':0,'winner':{'drive_settings':settings}},None,None,None,.5)
    monkeypatch.setattr(search_results,'load_completed_search',lambda p:saved)
    monkeypatch.setattr(optimisation,'verified_assessment',lambda *a:{'checks':{'passed':False}})
    system = {
        'excitation_ports':[{'id':str(i),'component_id':c} for i,c in enumerate(ids)],
        'components':[{'id':c,'parameters':{'re_ohm':4.}} for c in ids]}
    if transformed:
        from meh_studio.domain import SourceModel
        from meh_studio.generated_system import HornSources
        physical = SourceModel.model_validate(source.model_dump() | {'ideal_outlet_area_m2': source.sd_m2/3})
        (system_path/'sources.json').write_text(HornSources(throat=physical,side=source).model_dump_json())
        system['components'][1]['parameters'] = physical.outlet_piston_parameters()
        system['metadata'] = {'ideal_outlet_transforms': {'component:throat': {
            'source_sha256':physical.content_hash, 'diaphragm_area_m2':physical.sd_m2,
            'outlet_area_m2':physical.outlet_area_m2, 'outlet_velocity_per_diaphragm_velocity':3.,
            'model':'lossless_zero_length_area_transformer'}}}
    (system_path/'project.blab.json').write_text(json.dumps({'physical_system':system}))
    (root/'relocated-domains.json').write_text(json.dumps({'domains':[{
        'id':'observation:horizontal-polar','coordinates':{'angle_deg':'angles','points_m':'points'}}]}))
    np.savez(root/'relocated-domains.npz',angles=[0.],points=[[0.,0.,2.]])
    quantities=[{'id':'acoustic:pressure:horizontal-polar','key':'p','unit':'Pa'}]
    for id,key,unit in [('electrical:voice-coil-current','i','A'),('mechanical:diaphragm-velocity','v','m/s')]:
        quantities.append({'id':id,'key':key,'unit':unit,'metadata':{'component_ids':ids[::-1],'physical_driver_orbit_counts':[1,1]}})
    (root/'row.json').write_text(json.dumps({'quantities':quantities,'diagnostics':{'transducer_reference_voltage_v':2.83}}))
    # Native output receiving columns are [HF, mid], excitation rows [mid, HF].
    np.savez(root/'row.npz',p=2.83*np.array([[1.],[2.]]),i=2.83*np.array([[.05,.25],[.5,.05]]),v=2.83*np.array([[.001,.002],[.003,.004]]))
    (root/'manifest.json').write_text(json.dumps({'phasor_convention':'exp(-i omega t)',
        'excitation_port_ids':['0','1'],'domains_metadata_file':'relocated-domains.json','domains_file':'relocated-domains.npz',
        'results':[{'freq_hz':1000.,'metadata_file':'row.json','arrays_file':'row.npz'}]}))
    report=search_operating_report(tmp_path,2.)
    weights=2*drive_weights([1000.],ids,settings)
    current=weights@np.array([[.25,.05],[.05,.5]])
    np.testing.assert_allclose(report['component_current_rms_a']['real'],current.real)
    raw_velocity = weights @ np.array([[.002,.001],[.004,.003]])
    physical_velocity = raw_velocity / np.array([1.,3. if transformed else 1.])
    np.testing.assert_allclose(report['component_velocity_rms_m_s']['real'],physical_velocity.real)
    np.testing.assert_allclose(report['component_peak_excursion_m'],np.sqrt(2)*abs(physical_velocity)/(2*np.pi*1000))
    if transformed:
        np.testing.assert_allclose(report['component_outlet_velocity_rms_m_s']['real'],raw_velocity.real)
    else:
        assert 'component_outlet_velocity_rms_m_s' not in report
    assert report['observation_coordinates']['points_m']==[0.,0.,2.]
    assert report['physical_validation'] is False
    assert report['electrical_validation']['passed'] is False
    calls=0
    def change_on_second_read(p):
        nonlocal calls
        calls+=1
        return saved if calls==1 else ({'search.json':'changed'},*saved[1:])
    monkeypatch.setattr(search_results,'load_completed_search',change_on_second_read)
    with pytest.raises(ValueError,match='evidence changed'):search_operating_report(tmp_path,2.)
