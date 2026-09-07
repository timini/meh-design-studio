"""Lossless single-trace measurement ingestion; importing never grants qualification."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import zipfile
import zlib
import stat
import struct

from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, model_validator

from .domain import Band, Digest, Identifier, Nonnegative, Positive, Record

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 4096
MAX_SAMPLES = 100_000
Text = Annotated[str, Field(min_length=1, max_length=4096)]


class UncertaintyDeclaration(Record):
    # Optional values remain unknown, never zero. These are declared constant
    # bounds for this trace, not independently established uncertainties.
    magnitude_db: Nonnegative | None
    phase_deg: Annotated[float, Field(strict=True, ge=0, le=180, allow_inf_nan=False)] | None
    interpretation: Literal["standard", "expanded", "unknown"]
    coverage_factor: Positive | None = None

    @model_validator(mode="after")
    def coverage(self):
        if self.interpretation == "expanded":
            if self.coverage_factor is None or self.coverage_factor <= 1:
                raise ValueError("expanded uncertainty requires coverage_factor > 1")
        elif self.coverage_factor is not None:
            raise ValueError("coverage factor applies only to expanded uncertainty")
        return self


class MeasurementMetadata(Record):
    id: Identifier
    declared_origin: Literal["physical_measurement", "synthetic_fixture"]
    source_description: Text
    fixture_id: Identifier
    signal_definition: Text
    processing_recipe: Text
    quantity: Literal["pressure", "impedance"]
    unit: Literal["Pa", "ohm"]
    amplitude_convention: Literal["rms", "peak", "unknown"]
    phasor_convention: Literal["exp(-i omega t)", "exp(+i omega t)"]
    valid_band: Band
    stimulus_rms_v: Positive | None
    observation_xyz_m: tuple[Annotated[float, Field(strict=True)], Annotated[float, Field(strict=True)], Annotated[float, Field(strict=True)]] | None
    calibration_sha256: Digest | None
    uncertainty: UncertaintyDeclaration

    @model_validator(mode="after")
    def physical_contract(self):
        if self.unit != {"pressure":"Pa", "impedance":"ohm"}[self.quantity]:
            raise ValueError("quantity and unit do not match")
        if self.quantity == "pressure" and self.observation_xyz_m is None:
            raise ValueError("pressure requires an explicit observation position")
        if self.quantity == "impedance" and self.observation_xyz_m is not None:
            raise ValueError("impedance has no acoustic observation position")
        return self


def digest(payload: bytes):
    return hashlib.sha256(payload).hexdigest()


def read_bounded(path: Path, *, max_bytes: int = MAX_INPUT_BYTES):
    path=Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('measurement input must be a regular file')
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_BINARY',0))
    with os.fdopen(descriptor,'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('measurement input must be a regular file')
        if before.st_size > max_bytes:
            raise ValueError("measurement input exceeds byte limit (16 MiB maximum)")
        payload=stream.read(max_bytes+1)
        after=os.fstat(stream.fileno())
    if len(payload)>max_bytes:
        raise ValueError("measurement input exceeds 16 MiB")
    if (before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError("measurement input changed during read")
    return payload


def parse_trace(payload: bytes, metadata: MeasurementMetadata):
    """Exact header: frequency_hz,real,imag. No smoothing, sorting or phase fitting."""
    if len(payload)>MAX_INPUT_BYTES: raise ValueError("measurement input exceeds 16 MiB")
    rows=[]
    try:
        reader=csv.reader(io.StringIO(payload.decode('utf-8-sig'),newline=''),strict=True)
        if next(reader,None) != ['frequency_hz','real','imag']:
            raise ValueError("CSV header must be frequency_hz,real,imag")
        for row in reader:
            if len(row)!=3 or any(not cell.strip() for cell in row):
                raise ValueError("each measurement row requires three numeric fields")
            rows.append(tuple(float(cell) for cell in row))
            if len(rows)>MAX_SAMPLES: raise ValueError("measurement exceeds sample limit")
    except (UnicodeError,csv.Error) as exc:
        raise ValueError("invalid UTF-8 CSV measurement") from exc
    values=np.asarray(rows,dtype="<f8")
    if not rows or not np.isfinite(values).all():
        raise ValueError("measurement requires finite nonempty samples")
    f=values[:,0]
    if np.any(f<=0) or np.any(np.diff(f)<=0):
        raise ValueError("measurement frequencies must be positive, unique and increasing")
    valid=(f>=metadata.valid_band.low_hz)&(f<=metadata.valid_band.high_hz)
    if not valid.any(): raise ValueError("declared validity band contains no measured samples")
    return {'frequency_hz':f,'real':values[:,1],'imag':values[:,2],'within_declared_band':valid}


def import_measurement(csv_path: Path, metadata_path: Path, output: Path, *, calibration_path: Path | None=None):
    raw=read_bounded(csv_path); declaration=read_bounded(metadata_path)
    metadata=MeasurementMetadata.model_validate_json(declaration)
    arrays=parse_trace(raw,metadata)
    calibration=read_bounded(calibration_path) if calibration_path is not None else None
    if (calibration is None) != (metadata.calibration_sha256 is None):
        raise ValueError("calibration declaration and supplied evidence must agree")
    if calibration is not None and digest(calibration) != metadata.calibration_sha256:
        raise ValueError("calibration evidence hash mismatch")
    # Inputs are fully checked before reserving a fresh destination. Files are
    # raw copies of the exact bounded reads, independent of later source edits.
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    files={'raw.csv':raw,'metadata.json':declaration}
    if calibration is not None: files['calibration.bin']=calibration
    for name,data in files.items(): (output/name).write_bytes(data)
    np.savez(output/'trace.npz',**arrays)
    files['trace.npz']=read_bounded(output/'trace.npz')
    manifest={'schema_version':1,'kind':'single_complex_measurement','status':'complete',
        'evidence':'imported_not_qualified','metadata_hash':metadata.content_hash,
        'files':{name:{'sha256':digest(data),'size_bytes':len(data)} for name,data in files.items()}}
    temporary=output/'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(output/'manifest.json')
    return manifest


def _check_array_directory(data: bytes, count: int):
    """Bound directory work before ZipFile can allocate per-entry objects.

    Bundles use a small, single-disk directory with no archive comment or
    ZIP64 directory. NumPy's local ZIP64 size headers remain supported.
    """
    if len(data)<22:
        raise ValueError("invalid measurement array archive")
    signature,disk,start_disk,on_disk,total,size,offset,comment=struct.unpack_from('<4s4H2IH',data,len(data)-22)
    if (signature!=b'PK\x05\x06' or disk or start_disk or comment
            or on_disk!=count or total!=count or size>4096
            or offset+size!=len(data)-22):
        raise ValueError("invalid measurement array archive directory")
    cursor=offset
    end=offset+size
    for _ in range(count):
        if cursor+46>end or data[cursor:cursor+4]!=b'PK\x01\x02':
            raise ValueError("invalid measurement array archive directory")
        name,extra,note=struct.unpack_from('<3H',data,cursor+28)
        cursor+=46+name+extra+note
        if cursor>end:
            raise ValueError("invalid measurement array archive directory")
    if cursor!=end:
        raise ValueError("invalid measurement array archive directory")


def read_measurement(output: Path):
    """Verify copied evidence and recompute arrays from raw CSV before use."""
    output=Path(output)
    if (output/'manifest.json').is_symlink():
        raise ValueError('measurement manifest cannot be a symlink')
    try:
        manifest=json.loads(read_bounded(output/'manifest.json',max_bytes=MAX_MANIFEST_BYTES))
    except RecursionError as exc:
        raise ValueError('measurement manifest exceeds nesting limit') from exc
    if (set(manifest)!={'schema_version','kind','status','evidence','metadata_hash','files'}
            or manifest['schema_version'] != 1 or manifest['kind'] != 'single_complex_measurement'
            or manifest['status'] != 'complete' or manifest['evidence'] != 'imported_not_qualified'):
        raise ValueError("unsupported measurement bundle")
    names=set(manifest['files'])
    required={'raw.csv','metadata.json','trace.npz'}
    if names not in (required,required|{'calibration.bin'}):
        raise ValueError("measurement bundle has missing or unexpected files")
    payloads={}
    for name in names:
        path=output/name
        if path.is_symlink(): raise ValueError("measurement bundle files cannot be symlinks")
        data=read_bounded(path)
        if manifest['files'][name] != {'sha256':digest(data),'size_bytes':len(data)}:
            raise ValueError("measurement artifact integrity mismatch")
        payloads[name]=data
    metadata=MeasurementMetadata.model_validate_json(payloads['metadata.json'])
    if metadata.content_hash!=manifest['metadata_hash']:
        raise ValueError("measurement metadata identity mismatch")
    calibration=payloads.get('calibration.bin')
    if (None if calibration is None else digest(calibration)) != metadata.calibration_sha256:
        raise ValueError("measurement calibration identity mismatch")
    expected=parse_trace(payloads['raw.csv'],metadata)
    _check_array_directory(payloads['trace.npz'],len(expected))
    try:
        with zipfile.ZipFile(io.BytesIO(payloads['trace.npz'])) as archive:
            expected_names={name+'.npy' for name in expected}
            if len(archive.infolist())!=len(expected_names) or set(archive.namelist())!=expected_names:
                raise ValueError("measurement array inventory mismatch")
            for name,values in expected.items():
                info=archive.getinfo(name+'.npy')
                if info.file_size>values.nbytes+1024:
                    raise ValueError("measurement array exceeds expected byte size")
                # ZipExtFile bounds DEFLATE output with max_length. BZIP2,
                # LZMA and Zstandard do not share that guarantee across runtimes.
                if info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
                    raise ValueError("invalid measurement array archive compression")
                with archive.open(info) as stream:
                    if np.lib.format.read_magic(stream)!=(1,0):
                        raise ValueError("unsupported measurement array encoding")
                    shape,fortran,dtype=np.lib.format.read_array_header_1_0(stream,max_header_size=1024)
                    if shape!=values.shape or dtype!=values.dtype or fortran:
                        raise ValueError("measurement array header differs from raw evidence")
                    data=stream.read(values.nbytes+1)
                    if len(data)!=values.nbytes or data != values.tobytes(order="C"):
                        raise ValueError("measurement arrays differ from raw evidence")
    except (zipfile.BadZipFile,EOFError,NotImplementedError,RuntimeError,OSError,zlib.error) as exc:
        raise ValueError("invalid measurement array archive") from exc
    return metadata,expected
