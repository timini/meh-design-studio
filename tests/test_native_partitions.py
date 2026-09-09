"""Reject incomplete or inconsistent raw frequency partitions before aggregation."""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

fixtures=Path(__file__).resolve().parents[1]/'validation/fixtures'
sys.path.insert(0,str(fixtures))
try:
    spec=importlib.util.spec_from_file_location('native_partitions_test',fixtures/'native_partitions.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
finally:sys.path.remove(str(fixtures))


def rows():
    frequencies=list(range(500,533));runtime={'native':'pinned'};records=[]
    for level in module.LEVELS:
        for chunk,part in enumerate(np.array_split(frequencies,module.PARTS)):
            # Raw pressures span two decades across chunks; per-chunk normalization would erase this.
            values=np.power(10.,(part-500)/16)
            records.append({'level':level,'chunk':chunk,'frequencies_hz':part.tolist(),
                'pressure_real':values.tolist(),'pressure_imag':np.zeros(len(part)).tolist(),'runtime':runtime,
                'mesh_identity':{'cad_geometry_sha256':'horn','exterior_mesh_size_m':.02,'compiler_runtime':{'gmsh':'same'}},
                'mesh_inventory':[('mesh',level)],'electrical_validation':{'passed':False},'export_checks':{'qualified':False}})
    return records,frequencies,runtime


def test_combines_raw_pressures_without_partition_gain_fitting():
    records,f,runtime=rows();combined,changes=module.combine(records,f,runtime)
    assert combined['0']['score']['ripple_db']==pytest.approx(40)
    assert all(x['maximum_magnitude_change_db']==0 and x['maximum_phase_change_deg']==0 for x in changes)
    assert not combined['0']['electrical_consistency_passed']


@pytest.mark.parametrize('damage',['missing','duplicate','frequencies','runtime','mesh','cad','pressure_length','nan','null'])
def test_rejects_invalid_partition_evidence(damage):
    records,f,runtime=rows()
    if damage=='missing':records.pop()
    elif damage=='duplicate':records[-1]=records[-2]
    elif damage=='frequencies':records[-1]['frequencies_hz'][0]+=1
    elif damage=='runtime':records[-1]['runtime']={'native':'different'}
    elif damage=='mesh':records[-1]['mesh_inventory']=[('mesh','different')]
    elif damage=='cad':
        for r in records:
            if r['level']=='2':r['mesh_identity']=r['mesh_identity']|{'cad_geometry_sha256':'changed'}
    elif damage=='pressure_length':records[-1]['pressure_real'].pop()
    elif damage=='nan':records[-1]['pressure_real'][0]=float('nan')
    else:records[-1]['pressure_real'][0]=0
    with pytest.raises(ValueError):module.combine(records,f,runtime)


def test_raw_phase_and_gain_changes_are_not_fitted_away():
    records,f,runtime=rows()
    for row in records:
        if row['level']=='2':
            values=np.asarray(row['pressure_real'])*1.2*np.exp(1j*np.deg2rad(6))
            row['pressure_real']=values.real.tolist();row['pressure_imag']=values.imag.tolist()
    _,changes=module.combine(records,f,runtime)
    assert changes[1]['maximum_magnitude_change_db']>.5
    assert changes[1]['maximum_phase_change_deg']>5


def test_assembly_persists_checked_report_and_rejects_changed_partition(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    records,f,identity=rows();search=tmp_path/'evidence/search';search.mkdir(parents=True)
    parts=tmp_path/'parts';parts.mkdir()
    by_key={}
    for row in records:
        if row['level']!='baseline':row['pressure_real']=np.ones(len(row['frequencies_hz'])).tolist()
        root=parts/f"{row['level']}-{row['chunk']}";root.mkdir()
        (root/'partition.json').write_text(json.dumps({'artifact_sha256':{}}))
        row['partition_sha256']=module.sha256(root/'partition.json');by_key[(row['level'],row['chunk'])]=row
    (search.parent/'baseline-search-grid.json').write_text('{"ripple_db":40}')
    (search.parent/'experiment.json').write_text(json.dumps({'status':'search_complete','runtime':identity,'stage_sha256':{}}))
    brief=SimpleNamespace(frequencies_hz=f[::2]);result={'runtime':identity,'winner_index':0,'winner':{'ripple_db':0}}
    monkeypatch.setattr(module,'load_search',lambda _:({},result,brief,None,None,.5,f,None,[.008,.006,.004]))
    monkeypatch.setattr(module,'read_partition',lambda search,root,level,chunk:by_key[(level,chunk)])
    class Runtime:
        def verify(self):return identity
    output=tmp_path/'assembled';module.assemble(search,parts,output,Runtime())
    report=json.loads((output/'experiment.json').read_text())
    assert report['status']=='complete' and report['results']['refinement_passed']
    assert report['results']['baseline_heldout_ripple_db']>1
    assert (output/'finalist-validation/validation.json').is_file()
    assert not report['results']['coupled_electrical_consistency_passed']
    (parts/'0-0/partition.json').write_text('{"artifact_sha256":{},"changed":true}')
    with pytest.raises(ValueError,match='partition changed during assembly'):
        module.assemble(search,parts,tmp_path/'changed',Runtime())
    assert json.loads((tmp_path/'changed/experiment.json').read_text())['status']=='failed'
