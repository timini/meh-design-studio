"""Exercise bundle contents and rejection without running an acoustic solve."""
import hashlib
import json
from pathlib import Path
import zipfile

import meshio
import numpy as np
import pytest

from meh_studio import search_results
from meh_studio.build_bundle import export_search
from meh_studio.cli import main
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from meh_studio.optimisation import SearchBrief, candidates, candidate_record
from meh_studio.boundary_lab import sha256


def saved_search(tmp_path, monkeypatch, count):
    examples=Path(__file__).resolve().parents[1]/'examples'
    data=json.loads((examples/'synthetic-search-brief.json').read_text())
    data.update(max_drivers=count,entry_fractions=[[.36]] if count==3 else [[.25,.65]],
                side_ids=['synthetic-side'],lengths_m=[.25],trial_budget=1)
    brief=SearchBrief.model_validate(data)
    base=HornGeometry.model_validate_json((examples/'three-driver-geometry.json').read_text())
    drivers=[DriverRevision.model_validate(d) for d in json.loads((examples/'synthetic-search-drivers.json').read_text())]
    winner=candidates(brief,base,drivers)[0]
    search=tmp_path/'search';trial=search/'trial-000';geometry=trial/'geometry'
    (geometry/'parts').mkdir(parents=True);(trial/'evaluation').mkdir();(trial/'system').mkdir()
    def write(path,value):path.write_text(json.dumps(value))
    write(search/'brief.json',brief.model_dump(mode='json'));write(search/'base-geometry.json',base.model_dump(mode='json'))
    write(search/'catalogue-snapshot.json',[d.model_dump(mode='json') for d in drivers])
    write(trial/'candidate.json',candidate_record(winner));write(trial/'evaluation/evaluation.json',{})
    score={'side_gain':.5,'electrical_validation':{'passed':False,'status':'unsupported_storage_precision'},
           'evaluation_sha256':sha256(trial/'evaluation/evaluation.json')}
    write(trial/'score.json',score);row=score|{'status':'complete','index':0}
    write(search/'search.json',{'status':'complete','winner_index':0,'winner':row,'trials':[row],'runtime':{'test':'fixture'},
        'control_sha256':{n:sha256(search/n) for n in ('brief.json','base-geometry.json','catalogue-snapshot.json')},
        'winner_candidate_sha256':sha256(trial/'candidate.json'),'winner_score_sha256':sha256(trial/'score.json')})
    monkeypatch.setattr(search_results,'verified_assessment',lambda *args:{'controls':{'evaluation.json':sha256(trial/'evaluation/evaluation.json')}})
    names=['throat']+[f'entry_{i}_{side}' for i in range((count-1)//2) for side in ('positive','negative')]
    write(trial/'system/project.blab.json',{'physical_system':{'excitation_ports':[
        {'id':'excitation:'+n,'component_id':'component:'+n} for n in names]}})
    meshio.write(geometry/'parts/tetra.stl',meshio.Mesh(np.array([[0.,0,0],[1.,0,0],[0,1.,0],[0,0,1.]]),
        [('triangle',np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]]))]),binary=True)
    write(geometry/'geometry.json',{'status':'complete','units':{'cad_and_stl':'mm'},'design':winner['design'].model_dump(mode='json'),
        'front_chamber_back_walls_verified':True,'sources':[{'id':n} for n in names],
        'material_volume_m3':{'tetra':1/6/1e9},'files':[{'path':'parts/tetra.stl','sha256':sha256(geometry/'parts/tetra.stl')}]})
    return search


@pytest.mark.parametrize('count',[3,5])
def test_bundle_counts_gains_units_and_hashes(tmp_path,monkeypatch,count):
    search=saved_search(tmp_path,monkeypatch,count);output=tmp_path/'horn.zip'
    report=export_search(search,output)
    assert report['driver_count']==count and report['driver_cost']==8+(count-1)*3
    assert not report['print_qualified'] and not report['finalist_validation_included']
    with zipfile.ZipFile(output) as z:
        bom=json.loads(z.read('bom.json'));gains=json.loads(z.read('gain-settings.json'));bundle=json.loads(z.read('bundle.json'))
        assert [r['quantity'] for r in bom['items']]==[1,count-1]
        assert bom['total']==report['driver_cost'] and bom['scope']=='drivers_only'
        assert [c['gain'] for c in gains['channels']]==[1.]+[.5]*(count-1)
        assert not gains['hardware_preset'] and len(gains['channels'])==count
        assert json.loads(z.read('assembly.json'))['units']=='mm'
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in bundle['files_sha256'].items())
        assert not bundle['physical_validation'] and not bundle['electrical_validation']['passed']
    with pytest.raises(FileExistsError):export_search(search,output)
    assert sha256(output)==report['sha256']


@pytest.mark.parametrize('fault',['geometry_hash','unsafe_path'])
def test_bad_geometry_does_not_publish_bundle(tmp_path,monkeypatch,fault):
    search=saved_search(tmp_path,monkeypatch,3);geometry=search/'trial-000/geometry'
    if fault=='geometry_hash':(geometry/'parts/tetra.stl').write_bytes(b'broken')
    else:
        p=geometry/'geometry.json';state=json.loads(p.read_text());state['files'][0]['path']='parts/../parts/tetra.stl';p.write_text(json.dumps(state))
    with pytest.raises(ValueError):export_search(search,tmp_path/'horn.zip')
    assert not list(tmp_path.glob('*.zip'))


def test_cli_exports_bundle_and_reports_invalid_input(tmp_path,monkeypatch,capsys):
    search=saved_search(tmp_path,monkeypatch,3)
    assert main(['export-search',str(search),'--output',str(tmp_path/'horn.zip')])==0
    assert json.loads(capsys.readouterr().out)['status']=='complete'
    assert main(['export-search',str(tmp_path/'missing'),'--output',str(tmp_path/'missing.zip')])==2
    assert 'error' in json.loads(capsys.readouterr().err)
