import json
import numpy as np
import pytest
from test_boundary_lab import artifact
from meh_studio.boundary_lab import SolveRequest,inspect_result,inspect_partial_result,sha256
from meh_studio.partial_results import inspect_stopped_evaluation


def partial(artifact):
    root,manifest=artifact
    manifest.update(status='running',frequencies_hz=[1000.,2000.],completion_mask=[True,False],
                    results=[manifest['results'][0],None])
    (root/'manifest.json').write_text(json.dumps(manifest))
    return root,manifest


def test_partial_inspection_preserves_failed_state_and_completed_arrays(artifact):
    root,manifest=partial(artifact);before=sha256(root/'manifest.json')
    request=SolveRequest(frequencies_hz=(1000.,2000.))
    with pytest.raises(ValueError,match='not complete'):inspect_result(root,request,'beat_cpu')
    result=inspect_partial_result(root,request,'beat_cpu')
    assert result['evidence']=='predicted_partial'
    assert result['frequencies_hz']==[1000.] and result['missing_frequencies_hz']==[2000.]
    assert result['requested_frequencies_hz']==[1000.,2000.]
    assert result['upstream_status']=='running' and sha256(root/'manifest.json')==before


@pytest.mark.parametrize('fault',['mask','row_missing','row_unfinished','nonfinite','domain','wrong_frequency','empty'])
def test_partial_rows_still_require_complete_physical_contracts(artifact,fault):
    root,manifest=partial(artifact)
    if fault=='mask':manifest['completion_mask']=[1,False]
    if fault=='row_missing':manifest['results'][0]=None
    if fault=='row_unfinished':manifest['results'][1]=manifest['results'][0]
    if fault=='nonfinite':np.savez(root/'frequencies/000000.npz',q0000=np.full((1,4),np.nan,dtype=np.complex64))
    if fault=='domain':
        d=json.loads((root/'domains.json').read_text());d['domains'][0]['metadata']['node_counts']=[5]
        (root/'domains.json').write_text(json.dumps(d))
    if fault=='wrong_frequency':manifest['results'][0]['freq_hz']=2000.
    if fault=='empty':manifest.update(completion_mask=[False,False],results=[None,None])
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):inspect_partial_result(root,SolveRequest(frequencies_hz=(1000.,2000.)),'beat_cpu')


@pytest.mark.parametrize('fault',[None,'live','completed','contract_failure','request','preflight','project','mesh'])
def test_managed_partial_reuse_binds_stopped_controls(artifact,fault):
    root,manifest=partial(artifact);evaluation=root.parent;project=root/'project.snapshot.blab.json'
    request=SolveRequest(frequencies_hz=(1000.,2000.))
    (evaluation/'request.json').write_text(request.canonical_json())
    preflight={'valid':True,'solve_kind':'interior_fem','output_ids':['acoustic:pressure:fem-nodes'],'meshes':manifest['meshes']}
    (evaluation/'preflight.json').write_text(json.dumps(preflight))
    saved={'status':'timed_out','runtime':{'backend':'beat_cpu'},'project_sha256':sha256(project),
        'request_sha256':sha256(evaluation/'request.json'),'preflight_sha256':sha256(evaluation/'preflight.json')}
    if fault=='live':saved['status']='running'
    if fault=='completed':saved['status']='complete'
    if fault=='contract_failure':saved.update(status='failed',error='runtime changed during evaluation')
    (evaluation/'evaluation.json').write_text(json.dumps(saved))
    if fault=='request':(evaluation/'request.json').write_text('{}')
    if fault=='preflight':(evaluation/'preflight.json').write_text('{}')
    if fault=='project':project.write_text('{}')
    if fault=='mesh':
        preflight['meshes'][0]['sha256']='a'*64
        (evaluation/'preflight.json').write_text(json.dumps(preflight))
        saved['preflight_sha256']=sha256(evaluation/'preflight.json')
        (evaluation/'evaluation.json').write_text(json.dumps(saved))
    if fault:
        with pytest.raises(ValueError):inspect_stopped_evaluation(project,evaluation)
    else:
        result=inspect_stopped_evaluation(project,evaluation)
        assert result['status']=='verified_partial_evidence' and result['original_status']=='timed_out'
        assert result['result']['missing_frequencies_hz']==[2000.]


def test_cli_reports_partial_evidence_without_starting_a_solver(tmp_path,monkeypatch,capsys):
    import meh_studio.partial_results as partial_module
    from meh_studio.cli import main
    seen=[]
    def inspect(project,evaluation):
        seen.append((project,evaluation))
        return {'status':'verified_partial_evidence','original_status':'timed_out',
                'result':{'missing_frequencies_hz':[5000.,7500.]}}
    monkeypatch.setattr(partial_module,'inspect_stopped_evaluation',inspect)
    assert main(['inspect-stopped',str(tmp_path/'project'),str(tmp_path/'evaluation')])==0
    assert seen==[(tmp_path/'project',tmp_path/'evaluation')]
    assert json.loads(capsys.readouterr().out)['original_status']=='timed_out'


@pytest.fixture
def frequency_parts(artifact,monkeypatch):
    """Contract fixture: no native acoustic or electrical accuracy claim."""
    import shutil
    import meh_studio.optimisation as optimisation
    monkeypatch.setattr(optimisation,'validate_electrical_basis',lambda *args:{'passed':False})
    root,manifest=partial(artifact);first=root.parent;second=first/'second';project=root/'project.snapshot.blab.json'
    (root/'compiled-system.json').write_text('{}')
    manifest['compiled_system_file']='compiled-system.json'
    (root/'manifest.json').write_text(json.dumps(manifest))
    second.mkdir();shutil.copytree(root,second/'upstream')
    second_manifest=json.loads((second/'upstream/manifest.json').read_text())
    second_manifest.update(status='complete',completion_mask=[True,True])
    second_manifest['results'][1]={'freq_hz':2000.,'metadata_file':'frequencies/000001.json','arrays_file':'frequencies/000001.npz'}
    metadata=json.loads((root/'frequencies/000000.json').read_text())
    metadata.update(freq_hz=2000.,arrays_file='000001.npz')
    (second/'upstream/frequencies/000001.json').write_text(json.dumps(metadata))
    np.savez(second/'upstream/frequencies/000001.npz',q0000=np.full((1,4),2+1j,dtype=np.complex64))
    (second/'upstream/manifest.json').write_text(json.dumps(second_manifest))
    request=SolveRequest(frequencies_hz=(1000.,2000.))
    for directory,status in ((first,'timed_out'),(second,'complete')):
        (directory/'request.json').write_text(request.canonical_json())
        preflight={'valid':True,'solve_kind':'interior_fem','output_ids':['acoustic:pressure:fem-nodes'],'meshes':manifest['meshes']}
        (directory/'preflight.json').write_text(json.dumps(preflight))
        saved={'status':status,'runtime':{'backend':'beat_cpu'},'project_sha256':sha256(project),
            'request_sha256':sha256(directory/'request.json'),'preflight_sha256':sha256(directory/'preflight.json')}
        if status=='complete':saved['result']=inspect_result(directory/'upstream',request,'beat_cpu',project_path=project)
        (directory/'evaluation.json').write_text(json.dumps(saved))
    return project,(first,second),request


def test_frequency_assembly_indexes_each_sample_without_rewriting_timeout(frequency_parts):
    from meh_studio.partial_results import assemble_frequency_evidence,verify_frequency_assembly
    project,parts,request=frequency_parts;before=sha256(parts[0]/'evaluation.json')
    report=assemble_frequency_evidence(project,parts,request)
    assert report['kind']=='derived_frequency_assembly'
    assert [row['source_index'] for row in report['rows']]==[0,1]
    assert [row['frequency_hz'] for row in report['rows']]==[1000.,2000.]
    assert report['sources'][0]['original_status']=='timed_out'
    assert report['overlap_checks'][0]['frequency_hz']==1000.
    assert sha256(parts[0]/'evaluation.json')==before
    report['rows'][0]['arrays_file']=report['rows'][1]['arrays_file']
    with pytest.raises(ValueError,match='assembled rows'):verify_frequency_assembly(report)


@pytest.mark.parametrize('fault',['overlap','runtime','solver','missing','no_overlap','source_changed'])
def test_frequency_assembly_rejects_incompatible_parts(frequency_parts,fault):
    from meh_studio.partial_results import assemble_frequency_evidence,verify_frequency_assembly
    project,parts,request=frequency_parts;second=parts[1]
    if fault=='missing':request=SolveRequest(frequencies_hz=(1000.,2000.,3000.))
    if fault in ('overlap','solver','no_overlap'):
        if fault=='overlap':np.savez(second/'upstream/frequencies/000000.npz',q0000=np.full((1,4),5+1j,dtype=np.complex64))
        manifest=json.loads((second/'upstream/manifest.json').read_text())
        if fault=='solver':manifest['solver_options']={'quadrature_order':99}
        if fault=='no_overlap':
            manifest.update(frequencies_hz=[2000.],completion_mask=[True],results=[manifest['results'][1]])
            (second/'request.json').write_text(SolveRequest(frequencies_hz=(2000.,)).canonical_json())
        (second/'upstream/manifest.json').write_text(json.dumps(manifest))
        saved=json.loads((second/'evaluation.json').read_text())
        own_request=SolveRequest.model_validate_json((second/'request.json').read_text())
        saved.update(request_sha256=sha256(second/'request.json'),
            result=inspect_result(second/'upstream',own_request,'beat_cpu',project_path=project))
        (second/'evaluation.json').write_text(json.dumps(saved))
    if fault=='runtime':
        saved=json.loads((second/'evaluation.json').read_text());saved['runtime']['julia_threads']=99
        (second/'evaluation.json').write_text(json.dumps(saved))
    if fault=='source_changed':
        report=assemble_frequency_evidence(project,parts,request)
        (parts[0]/'upstream/frequencies/000000.npz').write_bytes(b'changed')
        with pytest.raises(ValueError,match='source arrays'):verify_frequency_assembly(report)
        return
    with pytest.raises(ValueError):assemble_frequency_evidence(project,parts,request)


def test_cli_frequency_assembly_uses_the_explicit_full_request(tmp_path,monkeypatch,capsys):
    import meh_studio.partial_results as partial_module
    from meh_studio.cli import main
    request=tmp_path/'request.json';request.write_text(SolveRequest(frequencies_hz=(1000.,2000.)).canonical_json())
    seen=[]
    def assemble(project,evaluations,request):
        seen.append((project,evaluations,request.frequencies_hz))
        return {'kind':'derived_frequency_assembly','original_evaluations_modified':False}
    monkeypatch.setattr(partial_module,'assemble_frequency_evidence',assemble)
    assert main(['assemble-frequencies','project','partial','completion','--request',str(request)])==0
    assert seen[0][2]==(1000.,2000.) and len(seen[0][1])==2
    assert json.loads(capsys.readouterr().out)['original_evaluations_modified'] is False
