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
