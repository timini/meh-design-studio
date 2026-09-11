"""Common-voltage mid-bank DSP and polar metrics for full coupled voltage bases.

Impedance ratios are independent of RMS/peak convention. Absolute SPL, efficiency
and amplifier headroom still require an explicitly calibrated source convention.
"""
from __future__ import annotations
from typing import Annotated
import math
import numpy as np
from pydantic import Field, model_validator, model_serializer
from .domain import Positive, Record
from .spherical_metrics import SphericalObjectives, sphere_error


class AcousticObjectives(Record):
    mid_highpass_hz: Positive = 350.
    upper_crossovers_hz: tuple[Positive,...] = (3000.,4000.,5000.)
    mid_polarities: tuple[Annotated[int,Field(strict=True)],...] = (1,-1)
    hf_delays_s: tuple[Annotated[float,Field(strict=True,ge=0,le=.005)],...] = (0.,)
    horizontal_coverage_deg: Annotated[float,Field(strict=True,ge=20,le=180)] = 90.
    vertical_coverage_deg: Annotated[float,Field(strict=True,ge=20,le=180)] = 90.
    directivity_weight: Annotated[float,Field(strict=True,ge=0)] = .5
    minimum_bank_impedance_ohm: Positive | None = 2.
    sphere: SphericalObjectives | None = None
    acoustic_handover_hz: tuple[Positive,Positive] | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy_objectives(self,handler):
        result=handler(self)
        if self.sphere is None:result.pop('sphere',None)
        if self.acoustic_handover_hz is None:result.pop('acoustic_handover_hz',None)
        return result

    @model_validator(mode='after')
    def bounded(self):
        for values in (self.upper_crossovers_hz,self.mid_polarities,self.hf_delays_s):
            if not values or len(values)>20 or len(set(values))!=len(values):
                raise ValueError('DSP choices must be unique, nonempty and bounded')
        if any(type(p) is not int or p not in (-1,1) for p in self.mid_polarities):
            raise ValueError('mid polarity must be +1 or -1')
        if min(self.upper_crossovers_hz)<=self.mid_highpass_hz:
            raise ValueError('upper crossover must exceed mid high-pass')
        if self.acoustic_handover_hz is not None:
            low,high=self.acoustic_handover_hz
            if not self.mid_highpass_hz<low<high:
                raise ValueError('acoustic handover bounds must increase above the mid high-pass')
        return self


def lr4(frequencies_hz,crossover_hz,kind):
    """Analogue LR4 transfer in the solver's exp(-i omega t) convention."""
    f=np.asarray(frequencies_hz,dtype=float)
    if f.ndim!=1 or not len(f) or not np.isfinite(f).all() or np.any(f<=0):
        raise ValueError('finite positive frequency vector required')
    if not math.isfinite(crossover_hz) or crossover_hz<=0 or kind not in ('lowpass','highpass'):
        raise ValueError('positive crossover and lowpass/highpass filter kind required')
    s=-1j*f/crossover_hz
    denominator=(s*s+math.sqrt(2)*s+1)**2
    return (np.ones_like(s) if kind=='lowpass' else s**4)/denominator


def drive_weights(frequencies_hz,component_ids,settings):
    """Multipliers of each native basis; all parallel mids share one voltage."""
    if component_ids.count('component:throat')!=1 or len(component_ids)<2 or len(set(component_ids))!=len(component_ids):
        raise ValueError('unique throat and side component IDs required')
    f=np.asarray(frequencies_hz,dtype=float)
    mid=settings['side_gain']*settings.get('mid_polarity',1)*lr4(f,settings['mid_highpass_hz'],'highpass')*lr4(f,settings['upper_crossover_hz'],'lowpass')
    hf=lr4(f,settings['upper_crossover_hz'],'highpass')*np.exp(2j*np.pi*f*settings.get('hf_delay_s',0.))
    weights=np.repeat(mid[:,None],len(component_ids),axis=1)
    weights[:,component_ids.index('component:throat')]=hf
    return weights


def polar_error(pressure,angles_deg,coverage_deg):
    """RMS error from a smooth -6 dB coverage target in each forward polar plane."""
    pressure=np.asarray(pressure,dtype=complex);angles=np.asarray(angles_deg,dtype=float)
    if pressure.ndim!=2 or pressure.shape[1]!=len(angles) or not np.isfinite(pressure).all():
        raise ValueError('finite frequency-by-angle pressure required')
    axial=np.flatnonzero(angles==0)
    if len(axial)!=1 or not np.isfinite(angles).all() or len(set(angles))!=len(angles):
        raise ValueError('one explicit axis and unique finite polar angles required')
    selected=np.flatnonzero(np.abs(angles)<=90)
    half=coverage_deg/2
    if not np.any(angles<=-half) or not np.any(angles>=half):
        raise ValueError('polar observations do not cover target angles')
    reference=np.abs(pressure[:,axial[0]])
    if np.any(reference==0):raise ValueError('on-axis null prevents directivity scoring')
    relative=20*np.log10(np.maximum(np.abs(pressure[:,selected])/reference[:,None],1e-6))
    target=-6*(angles[selected]/half)**2
    # Include both forward wings so narrow/lobed solutions cannot hide outside coverage.
    error=float(np.sqrt(np.mean((relative-target[None,:])**2)))
    return {'rms_target_error_db':error,'angles_deg':angles[selected].tolist(),
            'relative_db':relative.tolist(),'target_db':target.tolist()}


def parallel_bank(current_basis,component_ids,reference_voltage_v=2.83):
    """Mid-bank input impedance with HF amplifier held at zero volts.

    current_basis axes: frequency, excitation, receiving component, ordered alike.
    Off-diagonal induced currents are included, not just self impedances.
    """
    current=np.asarray(current_basis,dtype=complex)
    count=len(component_ids)
    if current.ndim!=3 or current.shape[1:]!=(count,count) or not np.isfinite(current).all():
        raise ValueError('finite complete current basis required')
    if component_ids.count('component:throat')!=1 or len(set(component_ids))!=count or count<2:
        raise ValueError('one throat and unique mid component identities required')
    if not math.isfinite(reference_voltage_v) or reference_voltage_v<=0:raise ValueError('positive basis voltage required')
    mids=[i for i,c in enumerate(component_ids) if c!='component:throat']
    # Sum receiving mid currents from every simultaneously driven mid excitation.
    current_per_volt=current[:,mids,:][:,:,mids].sum(axis=(1,2))/reference_voltage_v
    if np.any(abs(current_per_volt)==0):raise ValueError('zero mid-bank admittance')
    impedance=1/current_per_volt
    return {'wiring':'parallel','amplifier_channels_for_mids':1,
            'hf_termination':'zero-voltage ideal amplifier','mid_count':len(mids),
            'impedance_real_ohm':impedance.real.tolist(),'impedance_imag_ohm':impedance.imag.tolist(),
            'minimum_impedance_magnitude_ohm':float(abs(impedance).min()),
            'maximum_current_per_volt_a':float(abs(current_per_volt).max())}


def score_acoustics(project,evaluation,gains,objectives):
    """Score preserved polar/current bases with common-bank crossover choices."""
    from .boundary_lab import _read_json,_contained
    from .optimisation import verified_assessment,relative_response
    evidence=verified_assessment(project,evaluation)
    root=evaluation/'upstream';manifest=_read_json(root/'manifest.json')
    if manifest.get('phasor_convention')!='exp(-i omega t)':
        raise ValueError('crossover scoring requires explicit exp(-i omega t) convention')
    ports={p['id']:p['component_id'] for p in _read_json(project)['physical_system']['excitation_ports']}
    ids=[ports[p] for p in manifest['excitation_port_ids']]
    domains=_read_json(_contained(root,manifest['domains_metadata_file']))['domains']
    angles={};bases={'horizontal':[],'vertical':[]};currents=[];frequencies=[];sphere_basis=[];sphere_points=None
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as data:
        for plane in bases:
            domain=next(d for d in domains if d['id']==f'observation:{plane}-polar')
            angles[plane]=data[domain['coordinates']['angle_deg']].copy()
        if objectives.sphere is not None:
            domain=next((d for d in domains if d['id']=='observation:sphere'),None)
            if domain is None:raise ValueError('spherical objective requires a complete native sphere observation')
            sphere_points=data[domain['coordinates']['points_m']].copy()
    for row in manifest['results']:
        frequencies.append(row['freq_hz'])
        metadata=_read_json(_contained(root,row['metadata_file']))
        if metadata.get('diagnostics',{}).get('transducer_reference_voltage_v')!=2.83:
            raise ValueError('native 2.83 V reference must be explicit')
        quantities={q['id']:q for q in metadata['quantities']}
        with np.load(_contained(root,row['arrays_file']),allow_pickle=False) as data:
            for plane in bases:
                q=quantities[f'acoustic:pressure:{plane}-polar'];basis=data[q['key']]
                if basis.shape!=(len(ids),len(angles[plane])):raise ValueError('invalid polar basis shape')
                bases[plane].append(basis.copy())
            q=quantities['electrical:voice-coil-current'];ordered=q['metadata']['component_ids']
            if len(ordered)!=len(ids) or set(ordered)!=set(ids):raise ValueError('current basis component identities differ')
            currents.append(data[q['key']][:,[ordered.index(c) for c in ids]].copy())
            if objectives.sphere is not None:
                q=quantities['acoustic:pressure:sphere'];basis=data[q['key']]
                if basis.shape!=(len(ids),len(sphere_points)):raise ValueError('invalid whole-sphere basis shape')
                sphere_basis.append(basis.copy())
    frequencies=np.asarray(frequencies)
    bank=parallel_bank(currents,ids)
    if objectives.minimum_bank_impedance_ohm is not None and bank['minimum_impedance_magnitude_ohm']<objectives.minimum_bank_impedance_ohm:
        raise ValueError(f"parallel mid bank minimum {bank['minimum_impedance_magnitude_ohm']:.6g} ohm violates {objectives.minimum_bank_impedance_ohm:g} ohm constraint")
    bases={name:np.asarray(value) for name,value in bases.items()}
    sphere_basis=np.asarray(sphere_basis)
    winner=None
    winner_key=None
    handover_rejections=0
    for gain in gains:
        for crossover in objectives.upper_crossovers_hz:
            for polarity in objectives.mid_polarities:
                for delay in objectives.hf_delays_s:
                    settings={'side_gain':gain,'mid_highpass_hz':objectives.mid_highpass_hz,
                              'upper_crossover_hz':crossover,'mid_polarity':polarity,'hf_delay_s':delay,
                              'filter':'analogue_lr4','phasor_convention':'exp(-i omega t)'}
                    weights=drive_weights(frequencies,ids,settings)
                    pressure={plane:np.einsum('fea,fe->fa',basis,weights) for plane,basis in bases.items()}
                    axis=np.flatnonzero(angles['horizontal']==0)
                    if len(axis)!=1:raise ValueError('unique horizontal on-axis sample required')
                    axial=pressure['horizontal'][:,axis[0]]
                    handover=None
                    if objectives.acoustic_handover_hz is not None:
                        from .acoustic_handover import acoustic_handover
                        terms=bases['horizontal'][:,:,axis[0]]*weights
                        hf=ids.index('component:throat')
                        mids=[i for i in range(len(ids)) if i!=hf]
                        handover=acoustic_handover(frequencies,terms[:,mids].sum(axis=1),terms[:,hf],
                            objectives.mid_highpass_hz,objectives.acoustic_handover_hz)
                        if not handover['passed']:
                            handover_rejections+=1
                            continue
                    try:
                        relative=relative_response(axial)
                        # Target the declared low crossover roll-off, rather than boosting it away.
                        residual=relative-20*np.log10(abs(lr4(frequencies,objectives.mid_highpass_hz,'highpass')))
                        polars={plane:polar_error(pressure[plane],angles[plane],getattr(objectives,plane+'_coverage_deg')) for plane in bases}
                        spherical=None
                        if objectives.sphere is not None:
                            spherical=sphere_error(np.einsum('fea,fe->fa',sphere_basis,weights),axial,
                                frequencies,sphere_points,objectives.sphere,
                                objectives.horizontal_coverage_deg,objectives.vertical_coverage_deg)
                    except ValueError:continue
                    errors=[p['rms_target_error_db'] for p in polars.values()]
                    if spherical is not None:errors.append(spherical['rms_target_error_db'])
                    directivity=sum(errors)/len(errors)
                    ripple=float(np.ptp(residual))
                    option={'ripple_db':ripple,'side_gain':gain,'relative_response_db':relative.tolist(),
                        'acoustic_objective':ripple+objectives.directivity_weight*directivity,
                        'directivity_error_db':directivity,'polars':polars,'drive_settings':settings}
                    if spherical is not None:option['sphere']=spherical
                    if handover is not None:option['acoustic_handover']=handover
                    key=(option['acoustic_objective'],gain,crossover)
                    if winner_key is None or key<winner_key:
                        winner,winner_key=option,key
    if winner is None:
        if handover_rejections:
            raise ValueError(f'no defined acoustic DSP response satisfies the declared mid/HF handover window ({handover_rejections} handover rejections)')
        raise ValueError('all acoustic DSP options contain undefined responses')
    weights=drive_weights(frequencies,ids,winner['drive_settings'])
    operating=np.einsum('fet,fe->ft',np.asarray(currents),weights)
    mids=[i for i,c in enumerate(ids) if c!='component:throat']
    bank_current=operating[:,mids].sum(axis=1)
    hf_current=operating[:,ids.index('component:throat')]
    bank['selected_drive_currents']={'normalisation':'original native 2.83 V basis, no RMS calibration claim',
        'mid_bank_real_a':bank_current.real.tolist(),'mid_bank_imag_a':bank_current.imag.tolist(),
        'hf_real_a':hf_current.real.tolist(),'hf_imag_a':hf_current.imag.tolist()}
    if verified_assessment(project,evaluation)!=evidence:raise ValueError('acoustic evidence changed while scoring')
    return winner|{'electrical_validation':evidence['checks'],'parallel_mid_bank':bank,
                   'absolute_spl_calibrated':False,'physical_validation':False}


def freeze_brief(brief,gain,settings=None):
    data=brief.model_dump(mode='json')|{'side_gains':[gain]}
    if brief.acoustic_objectives is not None:
        if settings is None:raise ValueError('acoustic finalist requires frozen crossover settings')
        data['acoustic_objectives'].update(upper_crossovers_hz=[settings['upper_crossover_hz']],
            mid_polarities=[settings['mid_polarity']],hf_delays_s=[settings['hf_delay_s']])
        if settings['mid_highpass_hz']!=brief.acoustic_objectives.mid_highpass_hz or settings['side_gain']!=gain:
            raise ValueError('frozen drive differs from search controls')
    return type(brief).model_validate(data)


def convergence_polars(project,evaluation,settings,objectives):
    """Raw complex pressures at every saved observation inside both coverage sectors."""
    from .boundary_lab import _read_json,_contained
    from .optimisation import verified_assessment
    evidence=verified_assessment(project,evaluation)
    root=evaluation/'upstream';manifest=_read_json(root/'manifest.json')
    ports={p['id']:p['component_id'] for p in _read_json(project)['physical_system']['excitation_ports']}
    ids=[ports[p] for p in manifest['excitation_port_ids']]
    weights=drive_weights([r['freq_hz'] for r in manifest['results']],ids,settings)
    domains=_read_json(_contained(root,manifest['domains_metadata_file']))['domains']
    selected={};coordinates=[]
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as arrays:
        for plane in ('horizontal','vertical'):
            domain=next(d for d in domains if d['id']==f'observation:{plane}-polar')
            angles=arrays[domain['coordinates']['angle_deg']]
            selected[plane]=np.flatnonzero(abs(angles)<=getattr(objectives,plane+'_coverage_deg')/2)
            if len(selected[plane])<3:raise ValueError('insufficient polar observations for coverage convergence')
            coordinates.extend({'plane':plane,'angle_deg':float(angles[i])} for i in selected[plane])
        if objectives.sphere is not None:
            domain=next((d for d in domains if d['id']=='observation:sphere'),None)
            if domain is None:raise ValueError('finalist requires the complete native sphere')
            points=arrays[domain['coordinates']['points_m']]
            selected['sphere']=np.arange(len(points))
            coordinates.extend({'plane':'sphere','point_m':point.tolist()} for point in points)
    values=[]
    for index,row in enumerate(manifest['results']):
        meta=_read_json(_contained(root,row['metadata_file']))
        with np.load(_contained(root,row['arrays_file']),allow_pickle=False) as arrays:
            combined=[]
            for plane in selected:
                identity='acoustic:pressure:sphere' if plane=='sphere' else f'acoustic:pressure:{plane}-polar'
                q=next(q for q in meta['quantities'] if q['id']==identity)
                combined.extend(weights[index]@arrays[q['key']][:,selected[plane]])
            values.append(combined)
    if verified_assessment(project,evaluation)!=evidence:raise ValueError('polar evidence changed during convergence extraction')
    return np.asarray(values),coordinates
