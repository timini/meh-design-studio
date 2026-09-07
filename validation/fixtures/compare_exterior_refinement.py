"""Compare declared exterior refinements without gain/phase fitting or RMS inference."""
import argparse
import json
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import _contained, _read_json, sha256
from meh_studio.validation import validate_electrical_basis


def load(project, evaluation):
    checks = validate_electrical_basis(project,evaluation)
    manifest = _read_json(evaluation/'upstream/manifest.json')
    rows = []
    for result in manifest['results']:
        metadata = _read_json(_contained(evaluation/'upstream',result['metadata_file']))
        with np.load(_contained(evaluation/'upstream',result['arrays_file']),allow_pickle=False) as archive:
            rows.append({q['id']:archive[q['key']] for q in metadata['quantities']
                         if q['quantity'] in {'exterior_pressure','diaphragm_velocity','voice_coil_current'}})
    return {'evaluation':str(evaluation.resolve()),'evaluation_sha256':sha256(evaluation/'evaluation.json'),
            'project_sha256':sha256(project),'mesh_inventory':manifest['meshes'],
            'electrical_checks':checks},manifest,rows


def compare(reference,candidate,relative_null_floor=.001):
    if reference.shape != candidate.shape:
        raise ValueError('comparison shapes differ')
    reference_norm=float(np.linalg.norm(reference))
    if not reference_norm:
        raise ValueError('reference norm is zero')
    # Each independently excited source has its own reference peak, preserving
    # weak source outputs rather than hiding them behind a louder source.
    threshold=relative_null_floor*np.max(abs(reference),axis=1,keepdims=True)
    mask=(abs(reference)>threshold)&(abs(candidate)>threshold)
    count=int(mask.sum())
    amplitude=20*np.log10(abs(candidate[mask])/abs(reference[mask]))
    phase=np.rad2deg(np.angle(candidate[mask]*reference[mask].conj()))
    return {'relative_matrix_norm_change':float(np.linalg.norm(candidate-reference)/reference_norm),
            'compared_samples':count,'excluded_null_samples':int(mask.size-count),
            'maximum_absolute_magnitude_change_db':float(np.max(abs(amplitude))) if count else None,
            'maximum_absolute_phase_change_deg':float(np.max(abs(phase))) if count else None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',nargs=2,type=Path,action='append',required=True,metavar=('PROJECT','EVALUATION'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if len(args.run)<3: raise ValueError('at least three declared refinement runs required')
    loaded=[load(*run) for run in args.run]
    frequencies=loaded[0][1]['frequencies_hz']
    ports=loaded[0][1]['excitation_port_ids']
    fem_inputs={m['id']:m['sha256'] for m in loaded[0][1]['meshes'] if m['purpose']=='fem_volume'}
    for record,manifest,_ in loaded[1:]:
        if record['project_sha256'] != loaded[0][0]['project_sha256']:
            raise ValueError('project definitions must match exactly for exterior-only refinement')
        if {m['id']:m['sha256'] for m in manifest['meshes'] if m['purpose']=='fem_volume'} != fem_inputs:
            raise ValueError('FEM meshes changed in exterior-only refinement')
        if any(manifest[k] != loaded[0][1][k] for k in ('backend_id','phasor_convention')):
            raise ValueError('backend or phase convention changed')
        if manifest['frequencies_hz'] != frequencies or manifest['excitation_port_ids'] != ports:
            raise ValueError('frequency or excitation identity mismatch')
    pairs=[]
    for (a,_,x),(b,_,y) in zip(loaded,loaded[1:]):
        rows=[]
        for frequency,old,new in zip(frequencies,x,y):
            if old.keys()!=new.keys(): raise ValueError('output identities differ')
            rows.append({'frequency_hz':frequency,'quantities':{k:compare(old[k],new[k]) for k in old}})
        pairs.append({'from':a['evaluation'],'to':b['evaluation'],'rows':rows})
    report={'schema_version':1,'evidence':'exterior_mesh_sensitivity_only','qualified':False,
        'null_policy':'Exclude reference or candidate amplitude <= 0.001 times each source reference peak; report excluded count. No fitted gain/phase.',
        'limitations':['Only exterior mesh refined; FEM discretisation fixed','Three frequencies and fixed polar cuts only',
                      'No independent acoustic solver or physical measurement','No absolute RMS/SPL normalisation',
                      'Strict circuit/reciprocity failures remain failures'],
        'runs':[r for r,_,_ in loaded],'successive_comparisons':pairs}
    # Refuse overwrite of previous evidence.
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(args.output)


if __name__=='__main__': main()
