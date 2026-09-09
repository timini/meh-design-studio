"""Re-evaluate a frozen search winner at denser frequencies and three FEM sizes."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import BoundaryLabRuntime, _read_json, _write_json, _contained, sha256
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from meh_studio.export_validation import validate_export
from meh_studio.optimisation import SearchBrief, candidates, evaluate_candidate, verified_assessment


def pressure(project, evaluation, gain):
    evidence=verified_assessment(project,evaluation)
    root=evaluation/'upstream'
    manifest=_read_json(root/'manifest.json')
    system=_read_json(project)['physical_system']
    ports={p['id']:p['component_id'] for p in system['excitation_ports']}
    weights=np.array([1. if ports[p]=='component:throat' else gain for p in manifest['excitation_port_ids']])
    domain=next(d for d in _read_json(_contained(root,manifest['domains_metadata_file']))['domains'] if d['id']=='observation:horizontal-polar')
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as archive:
        indices=np.flatnonzero(archive[domain['coordinates']['angle_deg']]==0)
    if len(indices)!=1: raise ValueError('missing unique on-axis observation')
    values=[]
    for result in manifest['results']:
        meta=_read_json(_contained(root,result['metadata_file']))
        q=next(q for q in meta['quantities'] if q['id']=='acoustic:pressure:horizontal-polar')
        with np.load(_contained(root,result['arrays_file']),allow_pickle=False) as archive:
            values.append(weights@archive[q['key']][:,int(indices[0])])
    if verified_assessment(project,evaluation)!=evidence: raise ValueError('changed finalist evidence')
    return np.asarray(values)


def validate(search, output, runtime):
    search=search.absolute();output=output.absolute()
    original_hash=sha256(search/'search.json')
    result=_read_json(search/'search.json')
    if result['status']!='complete': raise ValueError('search must complete before finalist validation')
    brief=SearchBrief.model_validate_json((search/'brief.json').read_text())
    base=HornGeometry.model_validate_json((search/'base-geometry.json').read_text())
    drivers=[DriverRevision.model_validate(d) for d in json.loads((search/'catalogue-snapshot.json').read_text())]
    winner=candidates(brief,base,drivers)[result['winner_index']]
    gain=result['winner']['side_gain']
    frequencies=tuple(sorted(set(brief.frequencies_hz)|{float(round(math.sqrt(a*b))) for a,b in zip(brief.frequencies_hz,brief.frequencies_hz[1:])}))
    frozen=SearchBrief.model_validate(brief.model_dump()|{'frequencies_hz':frequencies,'side_gains':(gain,)})
    sizes=(base.mesh_size_m,base.mesh_size_m*.75,base.mesh_size_m*.5)
    if min(sizes)<.0005: raise ValueError('refinement exceeds generator mesh limits')
    output.mkdir(parents=True,exist_ok=False)
    report={'schema_version':1,'status':'running','search_sha256':original_hash,
        'winner_index':result['winner_index'],'fixed_side_gain':gain,'frequencies_hz':frequencies,
        'mesh_sizes_m':sizes,'magnitude_change_limit_db':.5,'phase_change_limit_deg':5.,
        'qualified':False,'physical_validation':False,'levels':[],
        'limitations':['Exterior mesh fixed; FEM refinement only','Pointwise pressure comparison, no gain/phase fitting',
                      'Additional geometric-midpoint frequencies rounded to whole hertz for native label precision','Finite frequency samples do not establish full-band convergence','Synthetic sources; no print or physical validation']}
    responses=[]
    try:
        for i,size in enumerate(sizes):
            print(f'Finalist refinement {i+1}/3: {size:g} m',flush=True)
            root=output/f'level-{i}'
            score=evaluate_candidate(winner,root,runtime,frozen,mesh_size=size)
            values=pressure(root/'system/project.blab.json',root/'evaluation',gain)
            if not np.isfinite(values).all() or np.any(abs(values)==0): raise ValueError('undefined finalist pressure comparison')
            responses.append(values)
            report['levels'].append({'mesh_size_m':size,'score':score,
                'export_checks':validate_export(root/'geometry'),
                'pressure_real':values.real.tolist(),'pressure_imag':values.imag.tolist()})
            _write_json(output/'validation.json',report)
        comparisons=[]
        for before,after in zip(responses,responses[1:]):
            comparisons.append({'maximum_magnitude_change_db':float(np.max(abs(20*np.log10(abs(after)/abs(before))))),
                'maximum_phase_change_deg':float(np.max(abs(np.angle(after*before.conj(),deg=True))))})
        report.update(status='complete',successive_changes=comparisons,
            refinement_passed=all(c['maximum_magnitude_change_db']<=.5 and c['maximum_phase_change_deg']<=5 for c in comparisons),
            electrical_consistency_passed=all(level['score']['electrical_validation']['passed'] for level in report['levels']))
        if sha256(search/'search.json')!=original_hash: raise ValueError('source search changed during validation')
    except BaseException as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _write_json(output/'validation.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('search',type=Path);parser.add_argument('output',type=Path)
    for name in ('checkout','python','julia'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    report=validate(args.search,args.output,BoundaryLabRuntime(args.checkout,args.python,args.julia))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
