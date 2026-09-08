import json
from pathlib import Path
import numpy as np
import pytest
from meh_studio.measurements import (MeasurementMetadata,UncertaintyDeclaration,import_measurement,
    read_measurement,parse_trace,digest,MAX_INPUT_BYTES)
from meh_studio.measurement_cli import main


@pytest.fixture
def inputs(tmp_path):
    csv=tmp_path/'input.csv';meta=tmp_path/'input.json'
    csv.write_bytes(b'frequency_hz,real,imag\r\n50,1,-2\r\n100,3,-4\r\n200,0,0\r\n400,5,6\r\n')
    record=MeasurementMetadata(id='fixture',declared_origin='synthetic_fixture',source_description='Invented test only',
        fixture_id='test-rig',signal_definition='test sine',processing_recipe='none',quantity='pressure',unit='Pa',
        amplitude_convention='unknown',phasor_convention='exp(+i omega t)',valid_band={'low_hz':100.,'high_hz':200.},
        stimulus_rms_v=None,observation_xyz_m=(0.,0.,1.),calibration_sha256=None,
        uncertainty=UncertaintyDeclaration(magnitude_db=None,phase_deg=None,interpretation='unknown'))
    meta.write_text(record.canonical_json())
    return csv,meta,record,tmp_path/'bundle'


def test_import_preserves_raw_conventions_unknowns_and_excluded_samples(inputs):
    csv,meta,record,out=inputs
    manifest=import_measurement(csv,meta,out)
    csv.write_text('later source change')
    loaded,arrays=read_measurement(out)
    assert loaded==record
    assert arrays['real'].tolist()==[1,3,0,5]
    assert arrays['imag'].tolist()==[-2,-4,0,6]
    assert arrays['within_declared_band'].tolist()==[False,True,True,False]
    assert b'\r\n' in (out/'raw.csv').read_bytes()
    assert manifest['evidence']=='imported_not_qualified'
    assert loaded.uncertainty.magnitude_db is None
    assert main(['inspect',str(out)])==0


def test_calibration_bytes_and_hash_required(inputs,tmp_path):
    csv,meta,record,out=inputs
    calibration=tmp_path/'calibration';calibration.write_bytes(b'declared evidence only')
    record=MeasurementMetadata.model_validate(record.model_dump()|{'calibration_sha256':digest(calibration.read_bytes())})
    meta.write_text(record.canonical_json())
    with pytest.raises(ValueError,match='agree'):import_measurement(csv,meta,out)
    calibration.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='hash'):import_measurement(csv,meta,out,calibration_path=calibration)
    calibration.write_bytes(b'declared evidence only')
    import_measurement(csv,meta,out,calibration_path=calibration)
    assert read_measurement(out)[0].calibration_sha256==record.calibration_sha256
    (out/'calibration.bin').write_bytes(b'damaged')
    with pytest.raises(ValueError,match='integrity'):read_measurement(out)


@pytest.mark.parametrize('data',[b'',b'freq,real,imag\n100,1,2',b'frequency_hz,real,imag\n100,NaN,2',
    b'frequency_hz,real,imag\n100,1,2\n100,3,4',b'frequency_hz,real,imag\n200,1,2\n100,3,4',
    b'frequency_hz,real,imag\n100,1,',b'frequency_hz,real,imag\n-1,1,2',
    b'frequency_hz,real,imag\n1,1,2'])
def test_bad_samples_rejected_before_creating_output(inputs,data):
    csv,meta,_,out=inputs;csv.write_bytes(data)
    with pytest.raises(ValueError):import_measurement(csv,meta,out)
    assert not out.exists()


def test_archive_cannot_substitute_smoothed_values_even_with_updated_hash(inputs):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    np.savez(out/'trace.npz',frequency_hz=np.array([50.,100.,200.,400.]),real=np.zeros(4),
        imag=np.zeros(4),within_declared_band=np.array([False,True,True,False]))
    manifest=json.loads((out/'manifest.json').read_text());data=(out/'trace.npz').read_bytes()
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='raw evidence'):read_measurement(out)


def test_existing_and_partial_destinations_are_not_overwritten(inputs,monkeypatch):
    csv,meta,_,out=inputs
    def fail(*args,**kwargs):raise OSError('disk full')
    monkeypatch.setattr(np,'savez',fail)
    with pytest.raises(OSError):import_measurement(csv,meta,out)
    assert not (out/'manifest.json').exists()
    with pytest.raises(FileExistsError):import_measurement(csv,meta,out)
    with pytest.raises(FileNotFoundError):read_measurement(out)


def test_unknown_units_and_uncertainty_are_not_inferred(inputs):
    _,_,record,_=inputs
    with pytest.raises(ValueError):MeasurementMetadata.model_validate(record.model_dump()|{'unit':'dB'})
    with pytest.raises(ValueError):UncertaintyDeclaration(magnitude_db=1,phase_deg=2,interpretation='expanded')
    with pytest.raises(ValueError):UncertaintyDeclaration(magnitude_db=-1,phase_deg=2,interpretation='standard')


def test_sparse_oversized_input_is_rejected(inputs):
    csv,meta,_,out=inputs
    with csv.open('wb') as stream:stream.truncate(MAX_INPUT_BYTES+1)
    with pytest.raises(ValueError,match='16 MiB'):import_measurement(csv,meta,out)


def test_zip_expansion_is_bounded_before_loading_array(inputs):
    import zipfile
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    with zipfile.ZipFile(out/'trace.npz','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in ('frequency_hz','real','imag','within_declared_band'):
            z.writestr(name+'.npy',bytes(1_000_000))
    manifest=json.loads((out/'manifest.json').read_text());data=(out/'trace.npz').read_bytes()
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='expected byte size'):read_measurement(out)


def test_signed_zero_is_preserved_and_substitution_rejected(inputs):
    csv,meta,_,out=inputs
    csv.write_bytes(b'frequency_hz,real,imag\n100,-1,-0.0\n200,0,0\n')
    import_measurement(csv,meta,out)
    _,arrays=read_measurement(out)
    assert np.signbit(arrays['imag'][0])
    arrays['imag'][0]=0.
    np.savez(out/'trace.npz',**arrays)
    manifest=json.loads((out/'manifest.json').read_text());data=(out/'trace.npz').read_bytes()
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='raw evidence'):read_measurement(out)


def test_unsupported_zip_compression_is_structured_cli_error(inputs,capsys):
    import struct
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    data=bytearray((out/'trace.npz').read_bytes())
    struct.pack_into('<H',data,8,99)
    central=data.index(b'PK\x01\x02')
    struct.pack_into('<H',data,central+10,99)
    (out/'trace.npz').write_bytes(data)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    assert main(['inspect',str(out)])==2
    assert 'invalid measurement array archive' in json.loads(capsys.readouterr().err)['error']


@pytest.mark.parametrize('value',[False,True,'0','1.2'])
def test_declared_numbers_do_not_accept_booleans_or_strings(inputs,value):
    _,_,record,_=inputs
    with pytest.raises(ValueError):UncertaintyDeclaration(magnitude_db=None,phase_deg=value,interpretation='unknown')
    with pytest.raises(ValueError):MeasurementMetadata.model_validate(record.model_dump()|{'observation_xyz_m':[value,0.,1.]})


def test_invalid_deflate_stream_is_structured_cli_error(inputs,capsys):
    import zipfile,struct
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    with zipfile.ZipFile(out/'trace.npz') as archive:
        entries={info.filename:archive.read(info) for info in archive.infolist()}
    with zipfile.ZipFile(out/'trace.npz','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,payload in entries.items():archive.writestr(name,payload)
    data=bytearray((out/'trace.npz').read_bytes())
    name_len,extra_len=struct.unpack_from('<HH',data,26)
    data[30+name_len+extra_len]=0x07  # DEFLATE's reserved block type
    (out/'trace.npz').write_bytes(data)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    assert main(['inspect',str(out)])==2
    assert 'invalid measurement array archive' in json.loads(capsys.readouterr().err)['error']


def test_deep_manifest_is_structured_cli_error(inputs,capsys):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    (out/'manifest.json').write_text('{"nested":'+'['*10000+'0'+']'*10000+'}')
    assert main(['inspect',str(out)])==2
    assert json.loads(capsys.readouterr().err)['error']


def test_bare_carriage_return_records_are_preserved(inputs):
    csv,meta,_,out=inputs
    raw=b'frequency_hz,real,imag\r100,1,-2\r200,3,-4\r'
    csv.write_bytes(raw);import_measurement(csv,meta,out)
    _,arrays=read_measurement(out)
    assert arrays['frequency_hz'].tolist()==[100,200]
    assert (out/'raw.csv').read_bytes()==raw


def test_decoder_recursion_is_structured_cli_error(inputs,monkeypatch,capsys):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    def fail(*args,**kwargs):raise RecursionError('decoder depth')
    with monkeypatch.context() as patch:
        patch.setattr(json,'loads',fail)
        assert main(['inspect',str(out)])==2
    assert 'nesting limit' in json.loads(capsys.readouterr().err)['error']


@pytest.mark.skipif(not hasattr(__import__('os'),'mkfifo'),reason='POSIX FIFO')
@pytest.mark.parametrize('name',['manifest.json','raw.csv'])
def test_fifo_bundle_artifacts_fail_without_blocking(inputs,name):
    import os,subprocess,sys
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    (out/name).unlink();os.mkfifo(out/name)
    result=subprocess.run([sys.executable,'-m','meh_studio.measurement_cli','inspect',str(out)],capture_output=True,text=True,timeout=5)
    assert result.returncode==2
    assert 'regular file' in json.loads(result.stderr)['error']


@pytest.mark.skipif(__import__('sys').version_info<(3,14),reason='stdlib Zstandard starts in Python 3.14')
def test_corrupt_zstandard_is_structured_error(inputs,capsys):
    import zipfile,struct
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    with zipfile.ZipFile(out/'trace.npz') as archive:entries={i.filename:archive.read(i) for i in archive.infolist()}
    with zipfile.ZipFile(out/'trace.npz','w',compression=zipfile.ZIP_ZSTANDARD) as archive:
        for name,payload in entries.items():archive.writestr(name,payload)
    data=bytearray((out/'trace.npz').read_bytes())
    name_len,extra_len=struct.unpack_from('<HH',data,26)
    data[30+name_len+extra_len]^=0xff
    (out/'trace.npz').write_bytes(data)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    assert main(['inspect',str(out)])==2
    assert 'invalid measurement array archive' in json.loads(capsys.readouterr().err)['error']


@pytest.mark.parametrize('forged_count',[False,True])
@pytest.mark.parametrize('entry_count',[5,100])
def test_directory_entries_rejected_before_zipfile_allocation(inputs,monkeypatch,forged_count,entry_count):
    import zipfile,struct
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    with zipfile.ZipFile(out/'trace.npz','w') as archive:
        for i in range(entry_count):archive.writestr(str(i),b'')
    data=bytearray((out/'trace.npz').read_bytes())
    if forged_count:
        struct.pack_into('<HH',data,len(data)-14,4,4)
    (out/'trace.npz').write_bytes(data)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    def forbidden(*args,**kwargs):pytest.fail('ZipFile allocated before directory bounds check')
    monkeypatch.setattr(zipfile,'ZipFile',forbidden)
    with pytest.raises(ValueError,match='archive directory'):read_measurement(out)


@pytest.mark.parametrize('method',[12,14,93])
def test_unbounded_compression_rejected_before_open(inputs,monkeypatch,method):
    import zipfile,struct
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    data=bytearray((out/'trace.npz').read_bytes())
    central=data.index(b'PK\x01\x02')
    struct.pack_into('<H',data,central+10,method)
    (out/'trace.npz').write_bytes(data)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['files']['trace.npz']={'sha256':digest(data),'size_bytes':len(data)}
    (out/'manifest.json').write_text(json.dumps(manifest))
    def forbidden(*args,**kwargs):pytest.fail('unsafe compressed stream was opened')
    monkeypatch.setattr(zipfile.ZipFile,'open',forbidden)
    with pytest.raises(ValueError,match='archive compression'):read_measurement(out)


def test_manifest_size_rejected_before_json_decoding(inputs,monkeypatch):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    (out/'manifest.json').write_text(json.dumps({'files':{str(i):{} for i in range(1000)}}))
    def forbidden(*args,**kwargs):pytest.fail('oversized manifest decoded')
    monkeypatch.setattr(json,'loads',forbidden)
    with pytest.raises(ValueError,match='byte limit'):read_measurement(out)


def test_derived_arrays_use_fixed_little_endian_even_if_native_alias_changes(inputs,monkeypatch):
    csv,_,record,_=inputs
    monkeypatch.setattr(np,'float64',np.dtype('>f8'))
    arrays=parse_trace(csv.read_bytes(),record)
    for key in ('frequency_hz','real','imag'):
        assert arrays[key].dtype.str=='<f8'
    import struct
    assert arrays['real'].tobytes()==struct.pack('<4d',1,3,0,5)


def test_importer_loads_without_optional_decoders(inputs):
    import subprocess,sys
    code="""
import sys
sys.modules['lzma']=None
sys.modules['_lzma']=None
sys.modules['compression.zstd']=None
from meh_studio.measurements import import_measurement,read_measurement
from pathlib import Path
import_measurement(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
read_measurement(Path(sys.argv[3]))
"""
    csv,meta,_,out=inputs
    result=subprocess.run([sys.executable,'-c',code,str(csv),str(meta),str(out)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('version',[True,1.0,'1'])
def test_manifest_requires_integer_version(inputs,version):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    manifest=json.loads((out/'manifest.json').read_text());manifest['schema_version']=version
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='unsupported'):read_measurement(out)


@pytest.mark.parametrize('inspection',[False,True])
def test_metadata_size_rejected_before_validation(inputs,monkeypatch,inspection):
    from meh_studio.measurements import MAX_METADATA_BYTES
    csv,meta,_,out=inputs
    if inspection:import_measurement(csv,meta,out)
    payload=b'{"extra":"'+b'x'*MAX_METADATA_BYTES+b'"}'
    target=out/'metadata.json' if inspection else meta
    target.write_bytes(payload)
    if inspection:
        manifest=json.loads((out/'manifest.json').read_text())
        manifest['files']['metadata.json']={'sha256':digest(payload),'size_bytes':len(payload)}
        (out/'manifest.json').write_text(json.dumps(manifest))
    def forbidden(*args,**kwargs):pytest.fail('oversized metadata validated')
    monkeypatch.setattr(MeasurementMetadata,'model_validate',forbidden)
    with pytest.raises(ValueError,match='byte limit'):
        if inspection:read_measurement(out)
        else:import_measurement(csv,meta,out)


@pytest.mark.parametrize('inspection',[False,True])
def test_duplicate_metadata_keys_rejected(inputs,inspection):
    csv,meta,_,out=inputs
    if inspection:import_measurement(csv,meta,out)
    payload=meta.read_bytes().rstrip()[:-1]+b',"phasor_convention":"exp(-i omega t)"}'
    target=out/'metadata.json' if inspection else meta
    target.write_bytes(payload)
    if inspection:
        manifest=json.loads((out/'manifest.json').read_text())
        manifest['files']['metadata.json']={'sha256':digest(payload),'size_bytes':len(payload)}
        (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='duplicate JSON'):
        if inspection:read_measurement(out)
        else:import_measurement(csv,meta,out)


@pytest.mark.parametrize('value',[True,False,1.0,'1',None,-1])
def test_artifact_size_requires_nonnegative_integer(inputs,value):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    manifest=json.loads((out/'manifest.json').read_text())
    if value==1.0 and type(value) is float:
        value=float(manifest['files']['raw.csv']['size_bytes'])
    manifest['files']['raw.csv']['size_bytes']=value
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='artifact record'):read_measurement(out)


@pytest.mark.parametrize('entry',[None,[],{}, {'size_bytes':1}, {'size_bytes':1,'sha256':None}])
def test_malformed_artifact_records_rejected(inputs,entry):
    csv,meta,_,out=inputs;import_measurement(csv,meta,out)
    manifest=json.loads((out/'manifest.json').read_text());manifest['files']['raw.csv']=entry
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='artifact record'):read_measurement(out)
