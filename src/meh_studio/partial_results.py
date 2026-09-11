"""Read completed samples from a stopped managed evaluation without changing it."""
from pathlib import Path
from .boundary_lab import (SolveRequest,_read_json,sha256,_mesh_inventory,_output_ids,
    _result_output_ids,_project_solve_kind,inspect_partial_result)


def inspect_stopped_evaluation(project, evaluation):
    """Validate stopped controls and every completed native row; never mark a solve complete."""
    project=Path(project).resolve();evaluation=Path(evaluation).resolve()
    names=('evaluation.json','request.json','preflight.json')
    hashes={name:sha256(evaluation/name) for name in names}
    saved=_read_json(evaluation/'evaluation.json')
    if saved.get('status') not in ('timed_out','cancelled'):
        raise ValueError('partial reuse requires a timed-out or cancelled managed evaluation')
    project_hash=sha256(project)
    if (saved.get('project_sha256')!=project_hash or saved.get('request_sha256')!=hashes['request.json']
            or saved.get('preflight_sha256')!=hashes['preflight.json']):
        raise ValueError('stopped evaluation control identity mismatch')
    request=SolveRequest.model_validate(_read_json(evaluation/'request.json'))
    preflight=_read_json(evaluation/'preflight.json')
    if preflight.get('valid') is not True:
        raise ValueError('stopped evaluation has no valid preflight')
    project_data=_read_json(project);kind=_project_solve_kind(project_data)
    if preflight.get('solve_kind')!=kind:
        raise ValueError('stopped preflight differs from project topology')
    backend=saved['runtime']['backend']
    outputs=_result_output_ids(project_data,_output_ids(preflight.get('output_ids')))
    result=inspect_partial_result(evaluation/'upstream',request,backend,outputs,kind,project)
    manifest=_read_json(evaluation/'upstream/manifest.json')
    if _mesh_inventory(manifest)!=_mesh_inventory(preflight):
        raise ValueError('stopped mesh identity changed between preflight and solve')
    if backend=='coupled_reference' and (
            manifest.get('reference_runner_sha256')!=saved['runtime'].get('reference_runner_sha256')
            or manifest.get('source_request_sha256')!=hashes['request.json']):
        raise ValueError('stopped FP64 runner/request identity mismatch')
    if sha256(project)!=project_hash or any(sha256(evaluation/name)!=digest for name,digest in hashes.items()):
        raise ValueError('stopped evaluation changed during inspection')
    return {'status':'verified_partial_evidence','original_status':saved['status'],
        'original_evaluation':str(evaluation),'project_sha256':project_hash,'controls_sha256':hashes,
        'runtime':saved['runtime'],'result':result,'qualified':False,'physical_validation':False}


def assemble_frequency_evidence(project, evaluations, request):
    """Index a complete grid across immutable runs with a checked overlap.

    This creates a distinct derived assessment. It never rewrites a native
    manifest or turns a timed-out search/evaluation into a completed one.
    """
    import numpy as np
    from .boundary_lab import _contained
    from .optimisation import verified_assessment
    project=Path(project).resolve()
    paths=tuple(Path(p).resolve() for p in evaluations)
    if not paths or len(paths)>100 or len(set(paths))!=len(paths):
        raise ValueError('distinct nonempty evaluation list required')
    if not isinstance(request,SolveRequest):raise ValueError('explicit SolveRequest required')
    sources=[];selected={};overlaps=[];common=None
    for source_index,path in enumerate(paths):
        saved=_read_json(path/'evaluation.json')
        if saved.get('status')=='complete':
            assessment=verified_assessment(project,path)
            controls=assessment['controls'];result=assessment['result']
        else:
            assessment=inspect_stopped_evaluation(project,path)
            controls=assessment['controls_sha256'];result=assessment['result']
        original_request=SolveRequest.model_validate(_read_json(path/'request.json'))
        if original_request.model_dump(exclude={'frequencies_hz'})!=request.model_dump(exclude={'frequencies_hz'}):
            raise ValueError('frequency parts differ in requested outputs or excitation controls')
        root=path/'upstream';manifest=_read_json(root/'manifest.json')
        identity={'runtime':saved['runtime'],'project_sha256':manifest['project_sha256'],
            'solve_kind':result['solve_kind'],'excitation_port_ids':result['excitation_port_ids'],
            'domains_metadata':result['artifact_hashes']['domains_metadata'],
            'domains_arrays':result['artifact_hashes']['domains_arrays'],
            'solver_options':manifest.get('solver_options'),
            'compiled_system':sha256(_contained(root,manifest['compiled_system_file']))}
        if common is None:common=identity
        elif identity!=common:raise ValueError('frequency parts have different physical domains, solver controls or runtime')
        rows={row['freq_hz']:row for row in manifest['results'] if row is not None}
        source={'evaluation':str(path),'original_status':saved['status'],'controls_sha256':controls,
            'result':result,'compiled_system_sha256':identity['compiled_system']}
        shared=[]
        for item in result['inventory']:
            frequency=item['frequency_hz']
            if frequency not in request.frequencies_hz:
                raise ValueError('frequency part contains samples outside the assembled request')
            row=rows[frequency]
            current={'frequency_hz':frequency,'source_index':source_index,
                'metadata_file':str(_contained(root,row['metadata_file'])),
                'arrays_file':str(_contained(root,row['arrays_file'])),
                'metadata_sha256':item['metadata_sha256'],'arrays_sha256':item['arrays_sha256']}
            if frequency in selected:
                before=selected[frequency]
                a_meta=_read_json(Path(before['metadata_file']));b_meta=_read_json(Path(current['metadata_file']))
                a_q={q['id']:q for q in a_meta['quantities']};b_q={q['id']:q for q in b_meta['quantities']}
                if ({k:{x:y for x,y in q.items() if x!='key'} for k,q in a_q.items()}!=
                        {k:{x:y for x,y in q.items() if x!='key'} for k,q in b_q.items()}):
                    raise ValueError('overlapping frequency quantity contracts differ')
                errors={}
                with np.load(before['arrays_file'],allow_pickle=False) as a, np.load(current['arrays_file'],allow_pickle=False) as b:
                    for name,q in a_q.items():
                        left=a[q['key']].astype(complex);right=b[b_q[name]['key']].astype(complex)
                        scale=float(np.linalg.norm(left));difference=float(np.linalg.norm(right-left))
                        if scale==0 and difference!=0:raise ValueError('overlap changed a zero reference quantity')
                        norm=difference/scale if scale else 0.
                        if not np.isfinite(norm) or norm>1e-5:
                            raise ValueError('overlapping complex quantities exceed the 1e-5 relative norm limit')
                        record={'relative_complex_norm_error':norm}
                        if q['quantity']=='exterior_pressure':
                            # Per-excitation null floor: weak sources cannot hide behind strong ones.
                            threshold=.001*abs(left).max(axis=1,keepdims=True)
                            mask=(abs(left)>=threshold)&(abs(left)>0)
                            if not mask.any():raise ValueError('overlap has no nonzero exterior reference samples')
                            ratio=right[mask]/left[mask]
                            magnitude=float(abs(20*np.log10(abs(ratio))).max())
                            phase=float(abs(np.angle(ratio,deg=True)).max())
                            if not np.isfinite(magnitude) or magnitude>.05 or phase>.5:
                                raise ValueError('overlapping exterior pressure exceeds magnitude/phase limits')
                            record.update(maximum_magnitude_change_db=magnitude,maximum_phase_change_deg=phase,
                                excluded_samples=int((~mask).sum()),relative_null_floor=.001)
                        errors[name]=record
                shared.append({'frequency_hz':frequency,'first_source_index':before['source_index'],
                               'second_source_index':source_index,'quantity_errors':errors})
            else:selected[frequency]=current
        if source_index and not shared:
            raise ValueError('each additional frequency part requires a verified overlapping sample')
        overlaps.extend(shared);sources.append(source)
    if set(selected)!=set(request.frequencies_hz):raise ValueError('assembled frequency coverage is incomplete')
    report={'status':'verified_complete_frequency_evidence','kind':'derived_frequency_assembly',
        'project':str(project),'project_sha256':sha256(project),'request':request.model_dump(mode='json'),
        'identity':common,'sources':sources,'overlap_checks':overlaps,
        'rows':[selected[f] for f in request.frequencies_hz],
        'qualified':False,'physical_validation':False,'original_evaluations_modified':False}
    _verify_source_files(report)
    return report


def _verify_source_files(report):
    """Check immutable files and the selected rows, including during assembly."""
    from .boundary_lab import _contained
    if sha256(Path(report['project']))!=report['project_sha256']:
        raise ValueError('assembled project changed')
    expected_rows={}
    for source_index,source in enumerate(report['sources']):
        path=Path(source['evaluation']);root=path/'upstream'
        if any(sha256(path/name)!=digest for name,digest in source['controls_sha256'].items()):
            raise ValueError('frequency source controls changed')
        manifest=_read_json(root/'manifest.json')
        artifacts={'manifest':root/'manifest.json','domains_metadata':_contained(root,manifest['domains_metadata_file']),
                   'domains_arrays':_contained(root,manifest['domains_file'])}
        if 'reference_runtime' in source['result']['artifact_hashes']:
            artifacts['reference_runtime']=_contained(root,manifest['reference_runtime']['file'])
        if any(sha256(artifacts[name])!=digest for name,digest in source['result']['artifact_hashes'].items()):
            raise ValueError('frequency source domain artifacts changed')
        if sha256(_contained(root,manifest['compiled_system_file']))!=source['compiled_system_sha256']:
            raise ValueError('frequency source compiled system changed')
        by_frequency={row['freq_hz']:row for row in manifest['results'] if row is not None}
        for item in source['result']['inventory']:
            row=by_frequency[item['frequency_hz']]
            if (sha256(_contained(root,row['metadata_file']))!=item['metadata_sha256']
                    or sha256(_contained(root,row['arrays_file']))!=item['arrays_sha256']):
                raise ValueError('frequency source arrays or metadata changed')
            expected_rows.setdefault(item['frequency_hz'],{'frequency_hz':item['frequency_hz'],
                'source_index':source_index,'metadata_file':str(_contained(root,row['metadata_file'])),
                'arrays_file':str(_contained(root,row['arrays_file'])),
                'metadata_sha256':item['metadata_sha256'],'arrays_sha256':item['arrays_sha256']})
        for mesh in manifest['meshes']:
            if sha256(Path(mesh['file']))!=mesh['sha256']:
                raise ValueError('frequency source mesh changed')
    request=SolveRequest.model_validate(report['request'])
    if (set(expected_rows)!=set(request.frequencies_hz)
            or report['rows']!=[expected_rows[f] for f in request.frequencies_hz]):
        raise ValueError('assembled rows differ from verified source samples')


def verify_frequency_assembly(report):
    """Rebuild the assessment from its sources before accepting derived claims.

    Hashes alone establish file immutability, not that a report describes those
    files. Re-derivation also binds project, request, runtime, overlap checks,
    original statuses, and the required hash inventories to the source contracts.
    """
    _verify_source_files(report)
    expected = assemble_frequency_evidence(
        report['project'], [source['evaluation'] for source in report['sources']],
        SolveRequest.model_validate(report['request']),
    )
    if expected != report:
        raise ValueError('assembled report differs from verified source contracts')
