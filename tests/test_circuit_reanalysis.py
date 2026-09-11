import numpy as np
import pytest
import json
from meh_studio.domain import SourceModel
from meh_studio.references import solve_driver_circuit
from meh_studio.circuit_reanalysis import recompute_circuits


def reference_bases(sources, frequencies, acoustic_load):
    n=np.array([s.outlet_velocity_ratio for s in sources])
    physical_load=acoustic_load*n[None,:,None]*n[None,None,:]
    velocity=[]; current=[]
    for drive in range(len(sources)):
        volts=np.zeros((len(frequencies),len(sources)));volts[:,drive]=2.83
        solved=solve_driver_circuit(sources,frequencies,volts,physical_load)
        velocity.append(solved.velocity_m_s*n); current.append(solved.current_a)
    return np.stack(velocity,axis=1),np.stack(current,axis=1)


def test_changed_circuits_recover_full_mutual_loading_and_every_pressure_basis(source):
    f=[350.,1000.,3000.,7500.]
    load=np.tile([[2.-3j,.5-1j],[.5-1j,3.-2j]],(4,1,1))
    changed=SourceModel.model_validate(source.model_dump()|{'sd_m2':2*source.sd_m2,
        'ideal_outlet_area_m2':source.sd_m2,'mmd_kg':.004,'cms_m_n':.0012,'bl_n_a':3.6})
    old=(source,source);new=(changed,source)
    old_v,old_i=reference_bases(old,f,load);new_v,new_i=reference_bases(new,f,load)
    result=recompute_circuits(f,old,new,old_v,old_i)
    np.testing.assert_allclose(result['acoustic_load'],load,rtol=1e-11,atol=1e-12)
    np.testing.assert_allclose(result['velocity'],new_v,rtol=1e-11,atol=1e-13)
    np.testing.assert_allclose(result['current'],new_i,rtol=1e-11,atol=1e-13)
    transfer=np.array([[1.+2j,3.-1j],[.5-2j,-1.+.5j],[2.+0j,0.-3j]])
    pressure_old=old_v@transfer.T
    pressure_recombined=np.einsum('feo,fen->fon',result['weights'],pressure_old)
    np.testing.assert_allclose(pressure_recombined,new_v@transfer.T,rtol=1e-11,atol=1e-13)
    # The old current basis cannot simply be mixed after changing the circuit.
    assert not np.allclose(np.einsum('feo,fed->fod',result['weights'],old_i),new_i)
    assert np.all(abs(new_i[:,0,1])>0)


def test_identity_reanalysis_preserves_voltage_and_all_induced_motion(source):
    f=[350.,1000.,3000.];load=np.tile([[2.-3j,.5-1j],[.5-1j,3.-2j]],(3,1,1))
    sources=(source,source);v,i=reference_bases(sources,f,load)
    result=recompute_circuits(f,sources,sources,v,i)
    np.testing.assert_allclose(result['weights'],np.tile(np.eye(2),(3,1,1)),atol=1e-12)
    np.testing.assert_allclose(result['velocity'],v,rtol=1e-12)
    np.testing.assert_allclose(result['current'],i,rtol=1e-12)


@pytest.mark.parametrize('fault',['area','singular','circuit','shape','nan'])
def test_incompatible_or_unreliable_basis_is_rejected(source,fault):
    f=[350.,1000.,3000.];load=np.tile([[2.-3j,.5-1j],[.5-1j,3.-2j]],(3,1,1))
    sources=(source,source);new=sources;v,i=reference_bases(sources,f,load)
    if fault=='area':new=(SourceModel.model_validate(source.model_dump()|{'sd_m2':.006}),source)
    if fault=='singular':v[:,1,:]=v[:,0,:]
    if fault=='circuit':i*=1.1
    if fault=='shape':v=v[:,:1,:]
    if fault=='nan':v[0,0,0]=np.nan
    with pytest.raises(ValueError):recompute_circuits(f,sources,new,v,i)


@pytest.fixture
def derived_case(source,tmp_path,monkeypatch):
    from meh_studio.boundary_lab import sha256
    from meh_studio.generated_system import HornSources
    from meh_studio.circuit_reanalysis import reanalyse_circuits
    from meh_studio import optimisation
    old=HornSources(throat=source,side=source)
    changed=SourceModel.model_validate(source.model_dump()|{'bl_n_a':3.6,'mmd_kg':.004})
    new=HornSources(throat=changed,side=source)
    system=tmp_path/'system';system.mkdir();raw=tmp_path/'evaluation/upstream';raw.mkdir(parents=True)
    project=system/'project.blab.json'
    ids=['component:throat','component:side-0'];ports=['voltage:throat','voltage:side-0']
    project.write_text(json.dumps({'physical_system':{
        'components':[{'id':id,'kind':'electrodynamic_transducer',
            'parameters':source.outlet_piston_parameters()|{'motion_profile':'rigid_translation'}} for id in ids],
        'excitation_ports':[{'id':p,'component_id':c} for p,c in zip(ports,ids)]}}))
    (system/'sources.json').write_text(old.model_dump_json())
    (system/'compilation.json').write_text(json.dumps({'status':'complete',
        'sources_hash':old.content_hash,'project_sha256':sha256(project)}))
    f=[350.,1000.,3000.];load=np.tile([[2.-3j,.5-1j],[.5-1j,3.-2j]],(3,1,1))
    v,i=reference_bases((source,source),f,load)
    new_v,new_i=reference_bases((changed,source),f,load)
    transfer=np.array([[1.+2j,3.-1j],[.5-2j,-1.+.5j],[2.+0j,0.-3j]])
    quantities=[{'id':name,'key':key,'unit':unit,'axes':['excitation','component'],
        'metadata':{'component_ids':ids[::-1],'physical_driver_orbit_counts':[1,1]}}
        for name,key,unit in [('mechanical:diaphragm-velocity','v','m/s'),
                              ('electrical:voice-coil-current','i','A')]]
    quantities.append({'id':'acoustic:pressure:observation','key':'p','unit':'Pa','axes':['excitation','observation']})
    for plane in ('horizontal','vertical'):
        quantities.append({'id':f'acoustic:pressure:{plane}-polar','key':plane,'unit':'Pa','axes':['excitation','observation']})
    rows=[]
    for n,freq in enumerate(f):
        (raw/f'{n}.json').write_text(json.dumps({'diagnostics':{'transducer_reference_voltage_v':2.83},'quantities':quantities}))
        pressure=v[n]@transfer.T
        np.savez(raw/f'{n}.npz',v=v[n,:,::-1],i=i[n,:,::-1],p=pressure,horizontal=pressure,vertical=pressure)
        rows.append({'freq_hz':freq,'metadata_file':f'{n}.json','arrays_file':f'{n}.npz'})
    np.savez(raw/'domains.npz',angles=np.array([-45.,0.,45.]))
    (raw/'domains.json').write_text(json.dumps({'domains':[{'id':f'observation:{p}-polar',
        'coordinates':{'angle_deg':'angles'}} for p in ('horizontal','vertical')]}))
    (raw/'manifest.json').write_text(json.dumps({'phasor_convention':'exp(-i omega t)',
        'excitation_port_ids':ports,'frequencies_hz':f,'results':rows,
        'domains_metadata_file':'domains.json','domains_file':'domains.npz'}))
    evidence={'checks':{'passed':False},'test_fixture':True}
    monkeypatch.setattr(optimisation,'verified_assessment',lambda *args:evidence)
    original={p:sha256(p) for directory in (system,raw) for p in directory.iterdir()}
    return project,raw,new,evidence,original,new_v,new_i,transfer


def test_derived_dataset_preserves_native_evidence_and_receiving_order(derived_case,tmp_path):
    from meh_studio.boundary_lab import sha256
    from meh_studio.circuit_reanalysis import reanalyse_circuits
    project,raw,new,evidence,original,new_v,new_i,transfer=derived_case
    output=tmp_path/'derived'
    report=reanalyse_circuits(project,raw.parent,new,output)
    assert report['status']=='complete' and not report['qualified']
    assert report['native_evidence']==evidence and report['new_sources_hash']==new.content_hash
    with np.load(output/report['rows'][0]['arrays_file']) as arrays:
        np.testing.assert_allclose(arrays['v'],new_v[0,:,::-1],rtol=1e-11,atol=1e-13)
        np.testing.assert_allclose(arrays['i'],new_i[0,:,::-1],rtol=1e-11,atol=1e-13)
        np.testing.assert_allclose(arrays['p'],new_v[0]@transfer.T,rtol=1e-11,atol=1e-13)
    assert all(sha256(p)==value for p,value in original.items())
    with pytest.raises(FileExistsError):reanalyse_circuits(project,raw.parent,new,output)


@pytest.mark.parametrize('scenario',['score','impedance','handover','grid','distance'])
def test_acoustic_scoring_uses_new_currents_and_preserves_failed_fields(derived_case,tmp_path,scenario):
    from meh_studio.boundary_lab import sha256
    from meh_studio.circuit_reanalysis import reanalyse_circuits
    from meh_studio.acoustic_objectives import parallel_bank
    from meh_studio.optimisation import SearchBrief
    from test_optimisation import inputs
    project,raw,new,evidence,original,new_v,new_i,transfer=derived_case
    brief=SearchBrief.model_validate(inputs()[0].model_dump()|{'frequencies_hz':[350.,1000.,3000.],
        'acoustic_objectives':{'upper_crossovers_hz':[2000.],
            'minimum_bank_impedance_ohm':100. if scenario=='impedance' else 2.,
            'observation_distance_m':20. if scenario=='distance' else 1.}})
    if scenario=='grid':brief=SearchBrief.model_validate(brief.model_dump()|{'frequencies_hz':[350.,1500.,3000.]})
    if scenario=='handover':
        data=brief.model_dump();data['side_gains']=[1e-9]
        data['acoustic_objectives']['acoustic_handover_hz']=[1000.,3000.]
        brief=SearchBrief.model_validate(data)
    output=tmp_path/'scored'
    if scenario=='score':
        report=reanalyse_circuits(project,raw.parent,new,output,brief=brief)
        scoring=report['acoustic_scoring'];assert scoring['status']=='complete'
        assert scoring['brief_hash']==brief.content_hash and not scoring['qualified']
        score=scoring['score'];bank=parallel_bank(new_i,['component:throat','component:side-0'])
        assert score['parallel_mid_bank']['minimum_impedance_magnitude_ohm']==pytest.approx(bank['minimum_impedance_magnitude_ohm'])
        assert 'electrical_validation' not in score
        assert report['native_evidence']==evidence
    else:
        with pytest.raises(ValueError):reanalyse_circuits(project,raw.parent,new,output,brief=brief)
        if scenario in ('impedance','handover'):
            report=json.loads((output/'derived.json').read_text())
            assert report['status']=='failed' and report['acoustic_scoring']['status']=='failed'
            assert 'score' not in report['acoustic_scoring']
            assert len(report['rows'])==3
            assert all(sha256(output/r['arrays_file'])==r['arrays_sha256'] for r in report['rows'])
        else:assert not output.exists()
    assert all(sha256(p)==value for p,value in original.items())
