import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('reference_runner', Path(__file__).resolve().parents[1] / 'validation/fixtures/run_coupled_reference.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('version', ['julia version 1.12.6', 'julia version 1.11.0'])
def test_reference_requires_exact_julia_runtime(tmp_path, monkeypatch, version):
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


def test_reference_python_inventory_and_version_gate(monkeypatch):
    monkeypatch.setattr(module.sys, 'version_info', (3, 11, 15))
    identity = module.python_identity()
    assert identity['python'] and identity['python_executable'] and identity['packages']
    monkeypatch.setattr(module.sys, 'version_info', (3, 12, 0))
    with pytest.raises(ValueError, match='Python 3.11'):
        module.python_identity()


def test_reference_failure_is_finalized_despite_cleanup_error():
    class Session:
        def stop(self): raise RuntimeError('cleanup failed')
    class Writer:
        def finish(self, **kwargs): self.result = kwargs
    writer = Writer()
    error = ValueError('original solve failed')
    module.finish_failed_reference(Session(), writer, error)
    assert writer.result == {'status':'failed','error':'original solve failed'}
    assert 'cleanup failed' in error.__notes__[0]
