from pathlib import Path
import json
import os

import pytest

from meh_studio.snapshots import capture_inputs,verify_snapshot,InputSnapshot,SnapshotFile
from meh_studio.jobs import JobSpec


def test_identity_survives_source_edits_and_relocation(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'original mesh')
    first=capture_inputs({'mesh':source},tmp_path/'first')
    second=capture_inputs({'mesh':source},tmp_path/'second')
    assert first.content_hash==second.content_hash
    source.write_bytes(b'edited mesh')
    assert verify_snapshot(tmp_path/'first',first.content_hash)==first
    assert (tmp_path/'first/input-mesh.bin').read_bytes()==b'original mesh'
    third=capture_inputs({'mesh':source},tmp_path/'third')
    assert first.content_hash!=third.content_hash
    spec=JobSpec(kind='mesh',input_digest=first.content_hash,parameters_json='{}')
    assert spec.input_digest==first.content_hash


def test_logical_names_order_and_content_bind_identity(tmp_path):
    a=tmp_path/'a';a.write_bytes(b'a')
    b=tmp_path/'b';b.write_bytes(b'b')
    first=capture_inputs({'second':b,'first':a},tmp_path/'first')
    second=capture_inputs({'first':a,'second':b},tmp_path/'second')
    swapped=capture_inputs({'first':b,'second':a},tmp_path/'swapped')
    assert first.content_hash==second.content_hash
    assert first.content_hash!=swapped.content_hash


@pytest.mark.parametrize('name',['../escape','A','con.txt','a/b','a\\b','a:b','', 'x'*65])
def test_names_rejected_before_output_creation(tmp_path,name):
    with pytest.raises(ValueError):capture_inputs({name:tmp_path/'absent'},tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_no_overwrite_and_corruption_detection(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'abc')
    out=tmp_path/'out';snapshot=capture_inputs({'source':source},out)
    with pytest.raises(FileExistsError):capture_inputs({'source':source},out)
    (out/'input-source.bin').write_bytes(b'xyz')
    with pytest.raises(ValueError,match='integrity'):verify_snapshot(out,snapshot.content_hash)


def test_manifest_replacement_cannot_change_expected_identity(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'abc')
    out=tmp_path/'out';snapshot=capture_inputs({'source':source},out)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files'][0]['sha256']='0'*64
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='identity'):verify_snapshot(out,snapshot.content_hash)


def test_failed_capture_never_publishes_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):capture_inputs({'missing':tmp_path/'missing'},tmp_path/'out')
    assert not (tmp_path/'out/manifest.json').exists()


def test_streaming_limit_and_partial_capture(tmp_path,monkeypatch):
    import meh_studio.snapshots as module
    source=tmp_path/'source';source.write_bytes(b'12345')
    monkeypatch.setattr(module,'MAX_FILE_BYTES',4)
    with pytest.raises(ValueError,match='byte limit'):capture_inputs({'source':source},tmp_path/'out')
    assert not (tmp_path/'out/manifest.json').exists()


def test_symlink_rejected(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'abc')
    link=tmp_path/'link'
    try:link.symlink_to(source)
    except OSError:pytest.skip('symlinks unavailable')
    with pytest.raises(ValueError,match='non-symlink'):capture_inputs({'source':link},tmp_path/'out')


@pytest.mark.skipif(os.name=='nt',reason='POSIX FIFO')
def test_fifo_rejected_without_open(tmp_path):
    source=tmp_path/'fifo';os.mkfifo(source)
    with pytest.raises(ValueError,match='regular'):capture_inputs({'source':source},tmp_path/'out')


def test_strict_manifest_sizes_and_order():
    with pytest.raises(ValueError):SnapshotFile(name='x',sha256='0'*64,size_bytes=1.0)
    entry=SnapshotFile(name='x',sha256='0'*64,size_bytes=1)
    with pytest.raises(ValueError):InputSnapshot(files=(entry,entry))
    with pytest.raises(ValueError):InputSnapshot(files=(entry,),schema_version=True)


def test_total_limit_spans_multiple_files(tmp_path,monkeypatch):
    import meh_studio.snapshots as module
    source=tmp_path/'source';source.write_bytes(b'abc')
    monkeypatch.setattr(module,'MAX_TOTAL_BYTES',5)
    with pytest.raises(ValueError,match='byte limit'):
        capture_inputs({'first':source,'second':source},tmp_path/'out')
    assert not (tmp_path/'out/manifest.json').exists()


def test_change_during_capture_rejected(tmp_path,monkeypatch):
    import meh_studio.snapshots as module
    from types import SimpleNamespace
    source=tmp_path/'source';source.write_bytes(b'abc')
    original=module.os.fstat
    count=0
    def changed(fd):
        nonlocal count
        value=original(fd);count+=1
        return SimpleNamespace(st_dev=value.st_dev,st_ino=value.st_ino,st_size=value.st_size,
            st_mode=value.st_mode,st_mtime_ns=value.st_mtime_ns+count,st_ctime_ns=value.st_ctime_ns)
    monkeypatch.setattr(module.os,'fstat',changed)
    with pytest.raises(ValueError,match='changed during'):capture_inputs({'source':source},tmp_path/'out')
    assert not (tmp_path/'out/manifest.json').exists()
