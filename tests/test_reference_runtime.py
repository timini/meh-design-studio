import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('reference_runner', Path(__file__).resolve().parents[1] / 'validation/fixtures/run_coupled_reference.py')
legacy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy_module)
from meh_studio import native_reference


def test_packaged_progress_counts_saved_results_in_preallocated_slots(tmp_path, capsys):
    import json
    request = tmp_path/'request.json'
    request.write_text('{}')
    output = tmp_path/'output'
    output.mkdir()
    class Writer:
        manifest = {'results': [None, None, None]}
        def write_result(self, index):
            self.manifest['results'][index] = {'freq_hz': [350, 700, 1000][index]}
        def finish(self, **kwargs):
            self.result = kwargs
    class Session:
        def solve_stream(self):
            return iter([2, 0, 1])
    writer = Writer()
    native_reference.execute_reference(writer, output, {}, request,
        native_reference.hashlib.sha256(request.read_bytes()).hexdigest(),
        Session, lambda result: result, lambda: {})
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events == [{'event': 'frequency_completed', 'solved_count': count} for count in (1, 2, 3)]
    assert writer.result == {'status': 'complete'}


@pytest.fixture(params=[legacy_module, native_reference], ids=['legacy-fixture','packaged-runner'])
def module(request):
    return request.param


@pytest.mark.parametrize('version', ['julia version 1.12.6', 'julia version 1.11.0'])
def test_reference_requires_exact_julia_runtime(tmp_path, monkeypatch, version, module):
    calls = []
    def probe(command, **kwargs):
        calls.append(command)
        return version + '\n'
    monkeypatch.setattr(module.subprocess, 'check_output', probe)
    path = tmp_path / 'julia'
    if version.endswith('1.12.6'):
        assert module.verify_julia(path) == {'julia_executable':str(path), 'julia_version':version}
    else:
        with pytest.raises(ValueError, match='pinned Julia'):
            module.verify_julia(path)
    assert calls == [[str(path), '--version']]


def test_reference_python_inventory_and_version_gate(monkeypatch, module):
    monkeypatch.setattr(module.sys, 'version_info', (3, 11, 15))
    identity = module.python_identity()
    assert identity['python'] and identity['python_executable'] and identity['packages']
    monkeypatch.setattr(module.sys, 'version_info', (3, 12, 0))
    with pytest.raises(ValueError, match='Python 3.11'):
        module.python_identity()


def test_reference_failure_is_finalized_despite_cleanup_error(module):
    class Session:
        def stop(self): raise RuntimeError('cleanup failed')
    class Writer:
        def finish(self, **kwargs): self.result = kwargs
    writer = Writer()
    error = ValueError('original solve failed')
    module.finish_failed_reference(Session(), writer, error)
    assert writer.result == {'status':'failed','error':'original solve failed'}
    assert 'cleanup failed' in error.__notes__[0]


def test_request_preparation_uses_one_snapshot(tmp_path, module):
    import json
    path = tmp_path/'request.json'
    path.write_text('{"frequencies_hz":[1000]}')
    def loader(snapshot):
        path.write_text('{"frequencies_hz":[2000]}')
        return json.loads(snapshot.read_bytes())
    spec, public, digest = module.request_snapshot(path, loader)
    assert spec == public == {'frequencies_hz':[1000]}
    assert digest != module.hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('fault', [None, 'setup', 'runtime_write', 'request_change', 'runtime_change'])
def test_reference_setup_and_evidence_are_finalized(tmp_path, monkeypatch, fault, module):
    import json
    request = tmp_path/'input.json'
    request.write_text('{}')
    digest = module.hashlib.sha256(request.read_bytes()).hexdigest()
    output = tmp_path/'output'
    output.mkdir()
    class Writer:
        manifest = {}
        def finish(self, **kwargs):
            self.result = kwargs
        def write_result(self, result): pass
    class Session:
        def solve_stream(self):
            if fault == 'request_change': request.write_text('{"changed":true}')
            return iter([])
        def stop(self): pass
    writer = Writer()
    def make_session():
        if fault == 'setup': raise RuntimeError('backend setup failed')
        return Session()
    original = Path.write_bytes
    def fail_write(path, data):
        if path.name == 'runtime.json': raise OSError('runtime write failed')
        return original(path,data)
    if fault == 'runtime_write': monkeypatch.setattr(Path,'write_bytes',fail_write)
    if fault:
        with pytest.raises((RuntimeError,ValueError,OSError)):
            module.execute_reference(writer,output,{'python':'pinned'},request,digest,make_session,lambda r:r,
                lambda: {'python':'changed' if fault=='runtime_change' else 'pinned'})
        assert writer.result['status'] == 'failed'
    else:
        module.execute_reference(writer,output,{'python':'pinned'},request,digest,make_session,lambda r:r,
                lambda: {'python':'changed' if fault=='runtime_change' else 'pinned'})
        assert writer.result['status'] == 'complete'
        assert writer.manifest['reference_runner_sha256'] == module.hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        runtime = writer.manifest['reference_runtime']
        assert runtime['sha256'] == module.hashlib.sha256((output/'runtime.json').read_bytes()).hexdigest()
        assert runtime['identity'] == json.loads((output/'runtime.json').read_bytes())
