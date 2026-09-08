"""Bounded input copies with portable identities for queued jobs.

Callers enumerate dependencies. Captures are sequential, not filesystem-wide
transactions; verify the expected identity immediately before consuming files.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Annotated, Mapping, Literal

from pydantic import Field, model_validator

from .domain import Digest, Record

MAX_FILES = 128
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
Name = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')]


class SnapshotFile(Record):
    name: Name
    sha256: Digest
    size_bytes: Annotated[int, Field(strict=True, ge=0, le=MAX_FILE_BYTES)]

    @property
    def filename(self):
        return f'input-{self.name}.bin'


class InputSnapshot(Record):
    schema_version: Annotated[int, Field(strict=True)] = 1
    kind: Literal['input_snapshot'] = 'input_snapshot'
    files: Annotated[tuple[SnapshotFile, ...], Field(min_length=1, max_length=MAX_FILES)]

    @model_validator(mode='after')
    def contract(self):
        if self.schema_version != 1:
            raise ValueError('unsupported snapshot schema')
        names=[entry.name for entry in self.files]
        if names != sorted(set(names)):
            raise ValueError('snapshot names must be unique and sorted')
        if sum(entry.size_bytes for entry in self.files)>MAX_TOTAL_BYTES:
            raise ValueError('snapshot exceeds total byte limit')
        return self


def _open_source(path: Path):
    path=Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('snapshot input must be a regular non-symlink file')
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0)
    descriptor=os.open(path,flags)
    return os.fdopen(descriptor,'rb')


def _stream_file(path: Path, limit: int, destination=None):
    with _open_source(path) as source:
        return _stream_handle(source,limit,destination)


def _stream_handle(source, limit: int, destination=None):
    before=os.fstat(source.fileno())
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('snapshot input must be a regular file')
    if before.st_size>limit:
        raise ValueError('snapshot byte limit exceeded')
    size=0
    digest=hashlib.sha256()
    while True:
        chunk=source.read(min(1024*1024,limit-size+1))
        if not chunk:
            break
        size+=len(chunk)
        if size>limit:
            raise ValueError('snapshot byte limit exceeded')
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
    after=os.fstat(source.fileno())
    def state(value):
        return value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns
    if state(before)!=state(after) or size!=before.st_size:
        raise ValueError('snapshot input changed during capture')
    return digest.hexdigest(),size


def _private_output(path: Path):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
    return os.fdopen(descriptor,'wb')


def capture_inputs(inputs: Mapping[str, Path], output: Path) -> InputSnapshot:
    """Reserve a new directory; publish the manifest last, never overwrite.

    A failed capture can leave a partial directory without a manifest. Such a
    directory is never accepted; retry into a new directory.
    """
    if not 1<=len(inputs)<=MAX_FILES:
        raise ValueError('snapshot requires 1 to 128 named inputs')
    # Validate all names before creating anything. Names cannot be paths.
    placeholders=[SnapshotFile(name=name,sha256='0'*64,size_bytes=0) for name in inputs]
    ordered=sorted(placeholders,key=lambda entry:entry.name)
    output=Path(output).absolute()
    if output.is_symlink():
        raise ValueError('snapshot output cannot be a symlink')
    # Resolve parent aliases once; keep the final entry exclusive and unfollowed.
    output=output.parent.resolve()/output.name
    sources={entry.name:Path(inputs[entry.name]) for entry in ordered}
    if any(path.resolve().is_relative_to(output.resolve()) for path in sources.values()):
        raise ValueError('snapshot sources cannot be inside the output directory')
    with ExitStack() as stack:
        handles={name:stack.enter_context(_open_source(path)) for name,path in sources.items()}
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        entries=[]
        total=0
        for entry in ordered:
            with _private_output(output/entry.filename) as destination:
                digest,size=_stream_handle(handles[entry.name],min(MAX_FILE_BYTES,MAX_TOTAL_BYTES-total),destination)
            total+=size
            entries.append(SnapshotFile(name=entry.name,sha256=digest,size_bytes=size))
    snapshot=InputSnapshot(files=tuple(entries))
    temporary=output/'manifest.json.tmp'
    with _private_output(temporary) as stream:
        stream.write(snapshot.canonical_json().encode('utf-8'))
    temporary.replace(output/'manifest.json')
    return snapshot


def verify_snapshot(output: Path, expected_digest: str) -> InputSnapshot:
    """Rehash every copied dependency against an identity held by the caller."""
    output=Path(output)
    # Stream into a bounded buffer only for the small manifest.
    import io
    buffer=io.BytesIO()
    _stream_file(output/'manifest.json',MAX_MANIFEST_BYTES,buffer)
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError('duplicate snapshot manifest key')
            result[key]=value
        return result
    try:
        snapshot=InputSnapshot.model_validate(json.loads(buffer.getvalue(),object_pairs_hook=unique))
    except RecursionError as exc:
        raise ValueError('snapshot manifest exceeds nesting limit') from exc
    if snapshot.content_hash!=expected_digest:
        raise ValueError('snapshot identity mismatch')
    for entry in snapshot.files:
        digest,size=_stream_file(output/entry.filename,entry.size_bytes)
        if digest!=entry.sha256 or size!=entry.size_bytes:
            raise ValueError('snapshot input integrity mismatch')
    return snapshot
