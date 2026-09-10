"""Linear single-tone operating predictions from verified voltage transfer bases.

Dividing pressure, velocity and current by the same native basis voltage removes
the RMS/peak convention. Applying explicitly RMS terminal voltages then produces
RMS responses. This is source-normalised prediction, not physical calibration.
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from .metrics import sum_voltage_basis, electrical_power_rms, pressure_levels_rms


def operating_quantities(frequencies, ids, voltage_rms, pressure_per_volt,
                         current_per_volt, velocity_per_volt, resistance_ohm):
    """All receiving drivers, including induced motion, remain in the basis."""
    f=np.asarray(frequencies,dtype=float);r=np.asarray(resistance_ohm,dtype=float)
    if f.ndim!=1 or not len(f) or not np.isfinite(f).all() or np.any(f<=0) or np.any(np.diff(f)<=0):
        raise ValueError('positive increasing operating frequencies required')
    if r.shape!=(len(ids),) or not np.isfinite(r).all() or np.any(r<=0):
        raise ValueError('one positive coil resistance per component required')
    voltage=np.asarray(voltage_rms,dtype=complex)
    pressure=sum_voltage_basis(pressure_per_volt,ids,voltage,ids)
    current=sum_voltage_basis(current_per_volt,ids,voltage,ids)
    velocity=sum_voltage_basis(velocity_per_volt,ids,voltage,ids)
    if current.shape!=voltage.shape or velocity.shape!=voltage.shape or len(current)!=len(f):
        raise ValueError('operating bases must retain every component and frequency')
    power,total=electrical_power_rms(voltage,current)
    peak_excursion=np.sqrt(2)*abs(velocity)/(2*np.pi*f[:,None])
    coil_loss=abs(current)**2*r
    if not np.isfinite(peak_excursion).all() or not np.isfinite(coil_loss).all():
        raise ValueError('operating calculation exceeded finite numerical range')
    return {'pressure':pressure,'current':current,'velocity':velocity,
            'power':power,'total_power':total,'peak_excursion':peak_excursion,'coil_loss':coil_loss}


def search_operating_report(search: Path, input_rms_v: float):
    """Frozen winning DSP at an explicit RMS reference before its filters/gains."""
    from .search_results import load_completed_search
    from .boundary_lab import _read_json,_contained
    from .optimisation import verified_assessment
    from .acoustic_objectives import drive_weights
    if not math.isfinite(input_rms_v) or input_rms_v<=0:
        raise ValueError('positive finite input RMS voltage required')
    search=search.absolute()
    hashes,result,brief,base,winner,gain=load_completed_search(search)
    settings=result['winner'].get('drive_settings')
    if settings is None:raise ValueError('operating report requires a winner with frozen acoustic DSP')
    trial=search/f"trial-{result['winner_index']:03d}"
    project=trial/'system/project.blab.json';evaluation=trial/'evaluation'
    evidence=verified_assessment(project,evaluation)
    system=_read_json(project)['physical_system'];root=evaluation/'upstream'
    manifest=_read_json(root/'manifest.json')
    if manifest.get('phasor_convention')!='exp(-i omega t)':raise ValueError('unsupported native phasor convention')
    port_components={p['id']:p['component_id'] for p in system['excitation_ports']}
    ids=tuple(port_components[p] for p in manifest['excitation_port_ids'])
    components={c['id']:c for c in system['components']}
    resistance=[components[c]['parameters']['re_ohm'] for c in ids]
    domains=_read_json(_contained(root,manifest['domains_metadata_file']))['domains']
    domain=next(d for d in domains if d['id']=='observation:horizontal-polar')
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as arrays:
        angles=arrays[domain['coordinates']['angle_deg']]
        axial=np.flatnonzero(angles==0)
        if len(axial)!=1:raise ValueError('one explicit on-axis observation required')
        # Preserve every coordinate: no far-field or distance rescaling is inferred.
        coordinates={k:np.asarray(arrays[v])[int(axial[0])].tolist() for k,v in domain['coordinates'].items()}
    frequencies=[];pressures=[];currents=[];velocities=[]
    for row in manifest['results']:
        meta=_read_json(_contained(root,row['metadata_file']))
        reference=meta.get('diagnostics',{}).get('transducer_reference_voltage_v')
        if reference!=2.83:raise ValueError('explicit native 2.83 V reference required')
        frequencies.append(row['freq_hz']);quantities={q['id']:q for q in meta['quantities']}
        with np.load(_contained(root,row['arrays_file']),allow_pickle=False) as arrays:
            p=quantities['acoustic:pressure:horizontal-polar']
            if p['unit']!='Pa':raise ValueError('pressure unit must be Pa')
            pressures.append(arrays[p['key']][:,axial].copy()/reference)
            for key,unit,destination in (('electrical:voice-coil-current','A',currents),
                                        ('mechanical:diaphragm-velocity','m/s',velocities)):
                q=quantities[key];order=q['metadata']['component_ids']
                if q['unit']!=unit or len(order)!=len(ids) or set(order)!=set(ids):
                    raise ValueError('complete component identities and physical units required')
                if q['metadata'].get('physical_driver_orbit_counts')!=[1]*len(ids):
                    raise ValueError('operating report requires individually represented physical drivers')
                destination.append(arrays[q['key']][:,[order.index(c) for c in ids]].copy()/reference)
    voltage=input_rms_v*drive_weights(frequencies,list(ids),settings)
    values=operating_quantities(frequencies,ids,voltage,pressures,currents,velocities,resistance)
    hf=ids.index('component:throat');mids=[i for i in range(len(ids)) if i!=hf]
    channel_current=np.column_stack((values['current'][:,mids].sum(axis=1),values['current'][:,hf]))
    channel_voltage=voltage[:,[mids[0],hf]]
    channel_power,net_power=electrical_power_rms(channel_voltage,channel_current)
    def complex_values(v):return {'real':v.real.tolist(),'imag':v.imag.tolist()}
    report={'schema_version':1,'kind':'linear_single_tone_operating_prediction',
        'input_sha256':hashes,'winner_index':result['winner_index'],'frequencies_hz':frequencies,
        'input_rms_v':input_rms_v,'input_definition':'RMS reference voltage before the frozen DSP gains and filters',
        'normalisation':'Native response divided by its explicit 2.83 V basis; transfer ratios applied to RMS voltage',
        'drive_settings':settings,'observation_coordinates':coordinates,'component_ids':ids,
        'pressure_rms_pa':complex_values(values['pressure'][:,0]),
        'predicted_pressure_level_db_re_20upa':[v.model_dump(mode='json') for v in pressure_levels_rms(values['pressure'][:,0])],
        'component_voltage_rms_v':complex_values(voltage),'component_current_rms_a':complex_values(values['current']),
        'component_velocity_rms_m_s':complex_values(values['velocity']),
        'component_peak_excursion_m':values['peak_excursion'].tolist(),
        'component_coil_joule_loss_w':values['coil_loss'].tolist(),
        'amplifier_channel_ids':['parallel_mid_bank','hf'],
        'amplifier_voltage_rms_v':complex_values(channel_voltage),'amplifier_current_rms_a':complex_values(channel_current),
        'amplifier_signed_real_power_w':channel_power.tolist(),'net_real_input_power_w':net_power.tolist(),
        'electrical_validation':evidence['checks'],'physical_validation':False,'maximum_spl_qualified':False,
        'limitations':['Linear independent sinusoidal samples, not simultaneous broadband programme power',
            'No thermal, excursion, amplifier clipping or distortion limits inferred; no safe drive recommendation',
            'Includes all modelled mutual coupling; ideal rigid diaphragms and supplied source models remain approximations',
            'Reported pressure levels are numerical predictions at saved coordinates, not measured or far-field-qualified SPL']}
    if verified_assessment(project,evaluation)!=evidence or load_completed_search(search)[0]!=hashes:
        raise ValueError('search evidence changed during operating report')
    return report
