"""Re-evaluate a frozen search winner at denser frequencies and three FEM sizes."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import BoundaryLabRuntime, _read_json, _write_json, _contained, sha256, _termination_guard
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from meh_studio.export_validation import validate_export
from meh_studio.radiation_geometry import step_geometry_sha256
from meh_studio.optimisation import SearchBrief, candidates, candidate_record, evaluate_candidate, verified_assessment


def pressure(project, evaluation, gain, drive_settings=None):
    evidence=verified_assessment(project,evaluation)
    root=evaluation/'upstream'
    manifest=_read_json(root/'manifest.json')
    system=_read_json(project)['physical_system']
    ports={p['id']:p['component_id'] for p in system['excitation_ports']}
    weights=np.array([1. if ports[p]=='component:throat' else gain for p in manifest['excitation_port_ids']])
    if drive_settings is not None:
        from meh_studio.acoustic_objectives import drive_weights
        weights=drive_weights([row['freq_hz'] for row in manifest['results']],
            [ports[p] for p in manifest['excitation_port_ids']],drive_settings)
    domain=next(d for d in _read_json(_contained(root,manifest['domains_metadata_file']))['domains'] if d['id']=='observation:horizontal-polar')
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as archive:
        indices=np.flatnonzero(archive[domain['coordinates']['angle_deg']]==0)
    if len(indices)!=1: raise ValueError('missing unique on-axis observation')
    values=[]
    for index,result in enumerate(manifest['results']):
        meta=_read_json(_contained(root,result['metadata_file']))
        q=next(q for q in meta['quantities'] if q['id']=='acoustic:pressure:horizontal-polar')
        with np.load(_contained(root,result['arrays_file']),allow_pickle=False) as archive:
            values.append((weights[index] if drive_settings is not None else weights)@archive[q['key']][:,int(indices[0])])
    if verified_assessment(project,evaluation)!=evidence: raise ValueError('changed finalist evidence')
    return np.asarray(values)


def mesh_identity(root):
    record=_read_json(root/'system/compilation.json')
    digest=step_geometry_sha256(root/'system/exterior/envelope.step')
    if digest!=record['exterior_identity']['cad_geometry_sha256']:
        raise ValueError('finalist CAD identity differs from compilation')
    return {'cad_geometry_sha256':digest,'exterior_surface':record['exterior_surface'],
            'exterior_mesh_size_m':record['exterior_mesh_size_m'],'compiler_runtime':record['compiler_runtime']}


def validation_frequencies(search_frequencies):
    """Require a distinct native-label-safe held-out sample in every interval."""
    midpoints=[]
    for low,high in zip(search_frequencies,search_frequencies[1:]):
        midpoint=float(round(math.sqrt(low*high)))
        if not low<midpoint<high:
            raise ValueError('rounded validation midpoint must lie strictly inside each search interval')
        midpoints.append(midpoint)
    if not midpoints:
        raise ValueError('validation requires held-out frequencies')
    return tuple(sorted((*search_frequencies,*midpoints)))


def load_search(search):
    from meh_studio.search_results import load_completed_search
    control_hashes,result,brief,base,winner,gain=load_completed_search(search)
    frequencies=validation_frequencies(brief.frequencies_hz)
    from meh_studio.acoustic_objectives import freeze_brief
    frozen=freeze_brief(brief,gain,result['winner'].get('drive_settings'))
    from meh_studio.spherical_metrics import denser_validation_brief
    frozen=denser_validation_brief(frozen)
    sizes=(base.mesh_size_m,base.mesh_size_m*.75,base.mesh_size_m*.5)
    if min(sizes)<.0005: raise ValueError('refinement exceeds generator mesh limits')
    return control_hashes,result,brief,base,winner,gain,frequencies,frozen,sizes


def validate(search, output, runtime, *, timeout_s=7200):
    report={'status':'running'}
    with _termination_guard(report) as activate:
        return _validate(search,output,runtime,timeout_s,report,activate)


def _validate(search, output, runtime, timeout_s, report, activate):
    if not math.isfinite(timeout_s) or not 0<timeout_s<=7200: raise ValueError('finalist timeout must be within (0, 7200] seconds')
    search=search.absolute();output=output.absolute()
    control_hashes,result,brief,base,winner,gain,frequencies,frozen,sizes=load_search(search)
    original_hash=control_hashes['search.json']
    runtime_identity=runtime.verify()
    output.mkdir(parents=True,exist_ok=False)
    report.update({'schema_version':1,'status':'running','search_sha256':original_hash,
        'input_sha256':control_hashes,'winner_index':result['winner_index'],'fixed_side_gain':gain,'frequencies_hz':frequencies,
        'runtime':runtime_identity,'per_level_solve_timeout_s':timeout_s,'mesh_sizes_m':sizes,'magnitude_change_limit_db':.5,'phase_change_limit_deg':5.,
        'qualified':False,'physical_validation':False,'levels':[],'successive_changes':[],
        'limitations':['FEM and conforming mouth interface refined; rigid-exterior target size fixed, not an independent full exterior convergence test','Pointwise pressure comparison, no gain/phase fitting',
                      'Additional geometric-midpoint frequencies rounded to whole hertz for native label precision','Finite frequency samples do not establish full-band convergence','Synthetic sources; no print or physical validation']})
    responses=[]
    if brief.acoustic_objectives is not None and brief.acoustic_objectives.sphere is not None:
        report['sphere_sampling']={
            'search_angle_precision_deg':brief.acoustic_objectives.sphere.angle_precision_deg,
            'validation_angle_precision_deg':frozen.acoustic_objectives.sphere.angle_precision_deg,
            'validation_point_count':round(41253/frozen.acoustic_objectives.sphere.angle_precision_deg**2),
            'angular_convergence_validated':False}
        report['limitations'].append('A denser whole-sphere grid checks additional directions; this is not an angular quadrature convergence proof')
    try:
        activate()
        _write_json(output/'validation.json',report)
        for i,size in enumerate(sizes):
            print(f'Finalist refinement {i+1}/3: {size:g} m',flush=True)
            if runtime.verify()!=runtime_identity: raise ValueError('finalist runtime changed between levels')
            root=output/f'level-{i}'
            score=evaluate_candidate(winner,root,runtime,frozen,mesh_size=size,timeout_s=timeout_s,frequencies=frequencies)
            identity=mesh_identity(root)
            if report['levels']:
                prior=report['levels'][0]['mesh_identity']
                if any(identity[k]!=prior[k] for k in ('cad_geometry_sha256','exterior_mesh_size_m','compiler_runtime')):
                    raise ValueError('finalist CAD or exterior target changed between levels')
            values=pressure(root/'system/project.blab.json',root/'evaluation',gain,result['winner'].get('drive_settings'))
            comparison=values
            if brief.acoustic_objectives is not None:
                from meh_studio.acoustic_objectives import convergence_polars
                comparison,coordinates=convergence_polars(root/'system/project.blab.json',root/'evaluation',
                    result['winner']['drive_settings'],frozen.acoustic_objectives)
                if report.get('comparison_coordinates',coordinates)!=coordinates:
                    raise ValueError('finalist polar observation coordinates changed')
                report['comparison_coordinates']=coordinates
                report['fixed_drive_settings']=result['winner']['drive_settings']
            if not np.isfinite(comparison).all() or np.any(abs(comparison)==0): raise ValueError('undefined finalist pressure comparison')
            responses.append(comparison)
            report['levels'].append({'mesh_size_m':size,'score':score,
                'mesh_identity':identity,'export_checks':validate_export(root/'geometry'),
                'pressure_real':values.real.tolist(),'pressure_imag':values.imag.tolist(),
                'comparison_pressure_real':comparison.real.tolist(),'comparison_pressure_imag':comparison.imag.tolist()})
            if len(responses)>1:
                before,after=responses[-2:]
                change={'maximum_magnitude_change_db':float(np.max(abs(20*np.log10(abs(after)/abs(before))))),
                    'maximum_phase_change_deg':float(np.max(abs(np.angle(after*before.conj(),deg=True))))}
                report['successive_changes'].append(change)
                if change['maximum_magnitude_change_db']>.5 or change['maximum_phase_change_deg']>5:
                    raise ValueError('finalist mesh stability limits exceeded; remaining levels not run')
            _write_json(output/'validation.json',report)
        if runtime.verify()!=runtime_identity:raise ValueError('finalist runtime changed before completion')
        comparisons=report['successive_changes']
        report.update(status='complete',successive_changes=comparisons,
            refinement_passed=all(c['maximum_magnitude_change_db']<=.5 and c['maximum_phase_change_deg']<=5 for c in comparisons),
            electrical_consistency_passed=all(level['score']['electrical_validation']['passed'] for level in report['levels']))
        if any(sha256(search/name)!=digest for name,digest in control_hashes.items()):
            raise ValueError('source search controls changed during validation')
        if load_search(search)[0]!=control_hashes:
            raise ValueError('source search evidence changed during validation')
    except BaseException as exc:
        report.update(status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',
                      refinement_passed=False,electrical_consistency_passed=False,error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _write_json(output/'validation.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('search',type=Path);parser.add_argument('output',type=Path)
    for name in ('checkout','python','julia'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--solve-timeout-s',type=float,default=7200)
    parser.add_argument('--julia-threads',type=int,default=1)
    args=parser.parse_args()
    report=validate(args.search,args.output,BoundaryLabRuntime(args.checkout,args.python,args.julia,julia_threads=args.julia_threads),timeout_s=args.solve_timeout_s)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
