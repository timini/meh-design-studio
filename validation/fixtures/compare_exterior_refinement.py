"""Compare declared exterior refinements without gain/phase fitting or RMS inference."""
import argparse
import json
import math
import hashlib
import os
import tempfile
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import _contained, _read_json, sha256
from meh_studio.validation import validate_electrical_basis
from meh_studio.radiation_geometry import step_geometry_sha256


def load(project, evaluation):
    project_payload=project.read_bytes()
    project_digest=hashlib.sha256(project_payload).hexdigest()
    definition_digest=refinement_project_hash_bytes(project_payload)
    evaluation_hash = sha256(evaluation/"evaluation.json")
    checks = validate_electrical_basis(project,evaluation)
    runtime = _read_json(evaluation/"evaluation.json").get("runtime")
    if not isinstance(runtime, dict) or not runtime:
        raise ValueError("missing evaluated runtime identity")
    manifest = _read_json(evaluation/'upstream/manifest.json')
    identity = exterior_identity(project, manifest)
    step_digest = sha256(project.parent/'exterior/envelope.step')
    rows = []
    pressure_ids = None
    for result in manifest['results']:
        metadata = _read_json(_contained(evaluation/'upstream',result['metadata_file']))
        current_ids = {q["id"] for q in metadata["quantities"] if q["quantity"] == "exterior_pressure"}
        if not current_ids or (pressure_ids is not None and current_ids != pressure_ids):
            raise ValueError("consistent exterior-pressure observables are required")
        pressure_ids = current_ids
        with np.load(_contained(evaluation/'upstream',result['arrays_file']),allow_pickle=False) as archive:
            rows.append({q['id']:archive[q['key']] for q in metadata['quantities']
                         if q['quantity'] in {'exterior_pressure','diaphragm_velocity','voice_coil_current'}})
    if not rows:
        raise ValueError('exterior-pressure observations are missing')
    compilation=_read_json(project.parent/'compilation.json')
    target = compilation['exterior_mesh_size_m']
    compiler_runtime=compilation.get('compiler_runtime')
    if not isinstance(compiler_runtime,dict) or not compiler_runtime:
        raise ValueError('missing host meshing runtime identity')
    if validate_electrical_basis(project, evaluation) != checks or sha256(evaluation/'evaluation.json') != evaluation_hash:
        raise ValueError('evaluation artifacts changed while loading comparison arrays')
    if exterior_identity(project, manifest) != identity or sha256(project.parent/'exterior/envelope.step') != step_digest:
        raise ValueError('exterior evidence changed while loading comparison arrays')
    if project.read_bytes()!=project_payload:
        raise ValueError('project changed while loading comparison arrays')
    return {'compiler_runtime':compiler_runtime,'cad_sha256': step_digest, 'runtime': runtime, 'pressure_ids': sorted(pressure_ids or []),
            'project_definition_sha256': definition_digest, 'evaluation':str(evaluation.resolve()),'evaluation_sha256':evaluation_hash,
            'project_sha256':project_digest,'mesh_inventory':manifest['meshes'],
            'exterior_identity':identity,
            'mesh_size_m':target,
            'electrical_checks':checks},manifest,rows


def exterior_identity(project, manifest):
    """Bind a compared surface to the CAD and design recorded at compilation."""
    compilation = _read_json(project.parent / 'compilation.json')
    exterior = _read_json(project.parent / 'exterior/exterior.json')
    cad_hash = sha256(project.parent / 'exterior/envelope.step')
    identity = {'design_hash': exterior.get('design_hash'),
                'cad_geometry_sha256': step_geometry_sha256(project.parent/'exterior/envelope.step')}
    if (compilation.get('status') != 'complete' or exterior.get('status') != 'complete'
            or not identity['design_hash']
            or compilation.get('project_sha256') != sha256(project)
            or compilation.get('geometry_hash') != identity['design_hash']
            or exterior.get('cad_sha256') != cad_hash
            or exterior.get('cad_geometry_sha256') != identity['cad_geometry_sha256']
            or compilation.get('exterior_identity') != identity
            or compilation.get('exterior_report_sha256') != sha256(project.parent/'exterior/exterior.json')
            or compilation.get('exterior_mesh_size_m') != exterior.get('mesh_size_m')
            or not exterior.get('compiler_runtime')
            or compilation.get('compiler_runtime') != exterior.get('compiler_runtime')):
        raise ValueError('missing or changed exterior design/CAD identity')
    surfaces = [mesh for mesh in manifest['meshes'] if mesh['purpose'] == 'bem_surface']
    if (len(surfaces) != 1 or surfaces[0]['id'] != 'mesh:exterior'
            or surfaces[0]['sha256'] != compilation.get('exterior_surface', {}).get('sha256')):
        raise ValueError('evaluated exterior mesh differs from its compilation')
    return identity


def refinement_project_hash(project):
    # Only the BEM mesh digest may vary; all other definitions remain identical.
    return refinement_project_hash_bytes(project.read_bytes())


def refinement_project_hash_bytes(payload):
    data = json.loads(payload)
    hashes = data.get('physical_system', {}).get('metadata', {}).get('generated_mesh_sha256', {})
    hashes.pop('mesh:exterior', None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_refinement_levels(records):
    if len(records) < 3:
        raise ValueError('at least three refinement levels required')
    sizes = [record.get('mesh_size_m') for record in records]
    if any(isinstance(size, bool) or not isinstance(size, (int, float))
           or not math.isfinite(size) or size <= 0 for size in sizes):
        raise ValueError('refinement targets must be positive finite mesh sizes')
    if any(fine >= coarse for coarse, fine in zip(sizes, sizes[1:])):
        raise ValueError('refinement targets must be distinct and strictly decreasing')
    hashes = [tuple(sorted(mesh['sha256'] for mesh in record['mesh_inventory']
                           if mesh['purpose'] == 'bem_surface')) for record in records]
    if any(not identity for identity in hashes) or len(set(hashes)) != len(hashes):
        raise ValueError('refinement requires distinct exterior meshes')


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


def publish_report(path, report):
    payload = json.dumps(report, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.meh-report-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication is atomic and refuses to replace existing evidence.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',nargs=2,type=Path,action='append',required=True,metavar=('PROJECT','EVALUATION'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if len(args.run)<3: raise ValueError('at least three declared refinement runs required')
    runner_digest=sha256(Path(__file__))
    loaded=[load(*run) for run in args.run]
    validate_refinement_levels([record for record, _, _ in loaded])
    frequencies=loaded[0][1]['frequencies_hz']
    ports=loaded[0][1]['excitation_port_ids']
    fem_inputs={m['id']:m['sha256'] for m in loaded[0][1]['meshes'] if m['purpose']=='fem_volume'}
    for record,manifest,_ in loaded[1:]:
        if record['exterior_identity'] != loaded[0][0]['exterior_identity']:
            raise ValueError('exterior design/CAD changed across refinement runs')
        if record['runtime'] != loaded[0][0]['runtime']:
            raise ValueError('runtime changed across refinements')
        if record['compiler_runtime'] != loaded[0][0]['compiler_runtime']:
            raise ValueError('host meshing runtime changed across refinements')
        if record['pressure_ids'] != loaded[0][0]['pressure_ids']:
            raise ValueError('exterior-pressure observable identities differ')
        if record['project_definition_sha256'] != loaded[0][0]['project_definition_sha256']:
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
    report={'schema_version':1,'runner_sha256':runner_digest,'evidence':'exterior_mesh_sensitivity_only','qualified':False,
        'null_policy':'Exclude reference or candidate amplitude <= 0.001 times each source reference peak; report excluded count. No fitted gain/phase.',
        'limitations':['Only exterior mesh refined; FEM discretisation fixed','Only supplied frequency samples and retained pressure observations',
                      'No independent acoustic solver or physical measurement','No absolute RMS/SPL normalisation',
                      'Strict circuit/reciprocity failures remain failures'],
        'scope':{'frequencies_hz':frequencies,'pressure_outputs':loaded[0][0]['pressure_ids']},
        'runs':[r for r,_,_ in loaded],'successive_comparisons':pairs}
    if sha256(Path(__file__))!=runner_digest:
        raise ValueError('comparison runner changed before publication')
    publish_report(args.output, report)
    print(args.output)


if __name__=='__main__': main()
