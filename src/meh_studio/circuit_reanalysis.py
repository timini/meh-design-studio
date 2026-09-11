"""Recompute driver circuits on a fixed, complete native acoustic velocity basis.

These are derived fields, not another native solve or a qualified source model.
Native arrays use (excitation, receiving component/observation); circuit algebra
uses receiving components as rows. The exp(-i omega t) convention is explicit.
"""
from pathlib import Path
import json
import math
import numpy as np
from .domain import Positive, Record


class ReanalysisLimits(Record):
    maximum_velocity_condition: Positive = 1e6
    maximum_circuit_condition: Positive = 1e6
    maximum_input_voltage_residual: Positive = 1e-5
    maximum_algebra_residual: Positive = 1e-10


def _circuit(sources, frequency):
    parameters = [s.outlet_piston_parameters() for s in sources]
    values = lambda key: np.array([p[key] for p in parameters])
    w = 2 * np.pi * frequency
    return (values('re_ohm') - 1j*w*values('le_h'), values('bl_n_per_a'),
            values('rms_n_s_per_m') - 1j*(w*values('mmd_kg') - 1/(w*values('cms_m_per_n'))))


def _relative(error, reference):
    denominator = float(np.linalg.norm(reference))
    return float(np.linalg.norm(error)/denominator) if denominator else (0. if not np.any(error) else math.inf)


def recompute_circuits(frequencies, old_sources, new_sources, velocity, current,
                       *, reference_voltage_v=2.83, limits=None):
    """Return new voltage bases and weights on the original excitation columns.

    Source circuits are physical records; both old and new circuits are converted
    to their native outlet coordinates. All moving-boundary areas must match.
    The 1e-5 input screen permits exploratory complex64 input; it does not replace
    or pass the separate native electrical qualification gate at 1e-8.
    """
    limits = ReanalysisLimits() if limits is None else limits
    f = np.asarray(frequencies, dtype=float)
    v = np.asarray(velocity, dtype=complex); i = np.asarray(current, dtype=complex)
    d = len(old_sources)
    if (not d or len(new_sources) != d or f.ndim != 1 or not len(f)
            or not np.isfinite(f).all() or np.any(f <= 0) or np.any(np.diff(f) <= 0)
            or v.shape != (len(f), d, d) or i.shape != v.shape
            or not np.isfinite(v).all() or not np.isfinite(i).all()
            or not math.isfinite(reference_voltage_v) or reference_voltage_v <= 0):
        raise ValueError('complete finite square voltage/velocity bases and increasing positive frequencies required')
    if any(not math.isclose(a.outlet_area_m2, b.outlet_area_m2, rel_tol=1e-12)
           for a, b in zip(old_sources, new_sources)):
        raise ValueError('changing moving-boundary area requires a new acoustic geometry and solve')
    new_v=[]; new_i=[]; weights=[]; loads=[]; diagnostics=[]
    voltage = reference_voltage_v * np.eye(d)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            for n, frequency in enumerate(f):
                old_v = v[n].T; old_i = i[n].T
                condition = float(np.linalg.cond(old_v))
                if not math.isfinite(condition) or condition > limits.maximum_velocity_condition:
                    raise ValueError('native velocity basis is singular or exceeds the declared condition limit')
                ze, bl, zm = _circuit(old_sources, frequency)
                input_error = _relative(ze[:,None]*old_i + bl[:,None]*old_v - voltage, voltage)
                if input_error > limits.maximum_input_voltage_residual:
                    raise ValueError('native source circuit does not reproduce the declared voltage basis')
                force = bl[:,None]*old_i - zm[:,None]*old_v
                load = np.linalg.solve(old_v.T, force.T).T
                ze, bl, zm = _circuit(new_sources, frequency)
                matrix = load + np.diag(zm + bl**2/ze)
                circuit_condition = float(np.linalg.cond(matrix))
                if not math.isfinite(circuit_condition) or circuit_condition > limits.maximum_circuit_condition:
                    raise ValueError('replacement circuit exceeds the declared condition limit')
                out_v = np.linalg.solve(matrix, (bl/ze)[:,None]*voltage)
                out_i = (voltage - bl[:,None]*out_v)/ze[:,None]
                mixing = np.linalg.solve(old_v, out_v)
                residual = max(_relative(old_v@mixing-out_v, out_v),
                    _relative((load + np.diag(zm))@out_v - bl[:,None]*out_i, bl[:,None]*out_i))
                if residual > limits.maximum_algebra_residual:
                    raise ValueError('derived circuit or velocity reconstruction exceeds the declared algebra limit')
                if not all(np.isfinite(a).all() for a in (out_v, out_i, mixing, load)):
                    raise ValueError('nonfinite derived circuit basis')
                new_v.append(out_v.T); new_i.append(out_i.T); weights.append(mixing); loads.append(load)
                diagnostics.append({'frequency_hz':float(frequency), 'velocity_condition':condition,
                    'replacement_circuit_condition':circuit_condition,
                    'input_voltage_relative_residual':input_error, 'algebra_relative_residual':residual,
                    'acoustic_load_reciprocity_relative_residual':_relative(load-load.T, load),
                    'minimum_acoustic_load_hermitian_eigenvalue':float(np.linalg.eigvalsh((load+load.conj().T)/2).min())})
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise ValueError('circuit reanalysis could not form a finite nonsingular basis') from exc
    return {'velocity':np.asarray(new_v), 'current':np.asarray(new_i), 'weights':np.asarray(weights),
            'acoustic_load':np.asarray(loads), 'diagnostics':diagnostics}


def reanalyse_circuits(project: Path, evaluation: Path, new_sources, output: Path, *, limits=None):
    """Write a separate derived dataset from verified complete native evidence."""
    from .boundary_lab import _read_json, _write_json, _contained, sha256
    from .generated_system import HornSources
    from .optimisation import verified_assessment
    from .geometry_worker import geometry_runtime
    project=Path(project).resolve(); evaluation=Path(evaluation).resolve(); output=Path(output).resolve()
    limits=ReanalysisLimits() if limits is None else limits
    application_runtime=json.loads(json.dumps(geometry_runtime()))
    new_sources=HornSources.model_validate(new_sources)
    evidence=verified_assessment(project,evaluation)
    source_path=project.parent/'sources.json'; old_sources=HornSources.model_validate_json(source_path.read_text())
    compilation=_read_json(project.parent/'compilation.json')
    if (compilation.get('status')!='complete' or compilation.get('sources_hash')!=old_sources.content_hash
            or compilation.get('project_sha256')!=sha256(project)):
        raise ValueError('compiled project and physical source identities do not match')
    if (old_sources.density_kg_m3!=new_sources.density_kg_m3
            or old_sources.sound_speed_m_s!=new_sources.sound_speed_m_s):
        raise ValueError('changing the acoustic medium requires a new native solve')
    system=_read_json(project)['physical_system']; raw=evaluation/'upstream'; manifest=_read_json(raw/'manifest.json')
    if manifest.get('phasor_convention')!='exp(-i omega t)':
        raise ValueError('unsupported native phasor convention')
    port_ids={p['id']:p['component_id'] for p in system['excitation_ports']}
    ids=[port_ids[p] for p in manifest['excitation_port_ids']]
    components={c['id']:c for c in system['components']}
    if len(ids)!=len(set(ids)) or set(ids)!=set(components) or ids.count('component:throat')!=1:
        raise ValueError('one independent voltage excitation for every component is required')
    old=[old_sources.throat if c=='component:throat' else old_sources.side for c in ids]
    new=[new_sources.throat if c=='component:throat' else new_sources.side for c in ids]
    for id,source in zip(ids,old):
        if (components[id]['kind']!='electrodynamic_transducer'
                or components[id]['parameters'].get('motion_profile')!='rigid_translation'):
            raise ValueError('fixed rigid-translation transducer boundaries are required')
        if any(components[id]['parameters'].get(k)!=value for k,value in source.outlet_piston_parameters().items()):
            raise ValueError('native circuit differs from the physical source record')
    velocities=[]; currents=[]; precisions=set()
    for row in manifest['results']:
        meta=_read_json(_contained(raw,row['metadata_file'])); quantities={q['id']:q for q in meta['quantities']}
        if meta['diagnostics'].get('transducer_reference_voltage_v')!=2.83:
            raise ValueError('explicit native 2.83 V basis required')
        with np.load(_contained(raw,row['arrays_file']),allow_pickle=False) as arrays:
            for name,destination,unit in (('mechanical:diaphragm-velocity',velocities,'m/s'),
                                           ('electrical:voice-coil-current',currents,'A')):
                q=quantities[name]; order=q['metadata']['component_ids']
                if (set(order)!=set(ids) or len(order)!=len(ids) or q['unit']!=unit
                        or q['metadata'].get('physical_driver_orbit_counts')!=[1]*len(ids)):
                    raise ValueError('individually represented components with matching units are required')
                values=arrays[q['key']]; precisions.add(str(values.dtype))
                destination.append(values[:,[order.index(c) for c in ids]].copy())
    result=recompute_circuits(manifest['frequencies_hz'],old,new,velocities,currents,limits=limits)
    output.mkdir(parents=True,exist_ok=False)
    report={'status':'running','kind':'derived_fixed_geometry_circuit_reanalysis','qualified':False,'physical_validation':False,
        'application_runtime':application_runtime,
        'native_evidence':evidence,'project_path':str(project),'evaluation_path':str(evaluation),
        'project_sha256':sha256(project),'old_sources_sha256':sha256(source_path),
        'new_sources':new_sources.model_dump(mode='json'),'new_sources_hash':new_sources.content_hash,
        'limits':limits.model_dump(mode='json'),'component_ids':ids,'frequencies_hz':manifest['frequencies_hz'],
        'native_reference_voltage_v':2.83,'native_storage_dtypes':sorted(precisions),'calculation_dtype':'complex128',
        'diagnostics':result['diagnostics'],'rows':[],
        'limitations':['Derived from the original acoustic discretisation; no new field solve or geometry change',
            'Complex128 algebra does not recover precision lost in complex64 input',
            'The 1e-5 input screen does not replace or pass the separate 1e-8 native electrical gate',
            'Source qualifications and omitted phase-plug, breakup, nonlinear and physical behaviour remain unresolved']}
    try:
        np.savez_compressed(output/'circuit-basis.npz',**{k:result[k] for k in ('velocity','current','weights','acoustic_load')})
        report['circuit_basis_sha256']=sha256(output/'circuit-basis.npz')
        for index,row in enumerate(manifest['results']):
            meta=_read_json(_contained(raw,row['metadata_file'])); values={}
            with np.load(_contained(raw,row['arrays_file']),allow_pickle=False) as arrays:
                for q in meta['quantities']:
                    name=q['id']
                    if name in ('mechanical:diaphragm-velocity','electrical:voice-coil-current'):
                        order=q['metadata']['component_ids']; key='velocity' if name.startswith('mechanical:') else 'current'
                        values[q['key']]=result[key][index][:,[ids.index(c) for c in order]]
                    elif name.startswith(('acoustic:pressure:','acoustic:normal-derivative:')):
                        original=arrays[q['key']]
                        if (not np.iscomplexobj(original) or q['axes'][0]!='excitation'
                                or original.shape[0]!=len(ids)):
                            raise ValueError('linear complex acoustic excitation fields are required')
                        values[q['key']]=(result['weights'][index].T @ original.reshape(len(ids),-1)).reshape(original.shape)
                    else:
                        raise ValueError('unsupported native quantity for circuit reanalysis')
                    if not np.isfinite(values[q['key']]).all():
                        raise ValueError('nonfinite recombined acoustic field')
            path=output/f'frequency-{index:06d}.npz'; np.savez_compressed(path,**values)
            report['rows'].append({'frequency_hz':row['freq_hz'],'arrays_file':path.name,'arrays_sha256':sha256(path),
                'original_metadata_file':str(_contained(raw,row['metadata_file'])),
                'original_metadata_sha256':sha256(_contained(raw,row['metadata_file']))})
        if (verified_assessment(project,evaluation)!=evidence or sha256(source_path)!=report['old_sources_sha256']
                or json.loads(json.dumps(geometry_runtime()))!=application_runtime):
            raise ValueError('native evidence changed during circuit reanalysis')
        report['status']='complete'
    except BaseException as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _write_json(output/'derived.json',report)
    return report
