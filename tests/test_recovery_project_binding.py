"""Compiler contract fixtures; real native recovery is recorded separately."""
from pathlib import Path
import shutil

import pytest

from test_generated_system import generated
from meh_studio.boundary_lab import _read_json, _write_json, sha256
from meh_studio.geometry import HornGeometry
from meh_studio.search_resume import verify_candidate_project


@pytest.fixture
def compiled(generated, monkeypatch, request):
    import meh_studio.radiating_system as module
    geometry, sources, _ = generated
    root=geometry.parent
    output=root/'system'
    class Runtime:
        python=Path('not-executed-python')
        checkout=root
        def verify(self): return {}
    def exterior(design, directory, mesh_size):
        directory.mkdir()
        (directory/'exterior.msh').write_bytes(b'contract fixture, not a physical mesh')
        report={'design_hash':design.content_hash,'mesh_size_m':mesh_size,
                'compiler_runtime':{},'cad_volume_m3':1.,'cad_geometry_sha256':'a'*64}
        _write_json(directory/'exterior.json', report)
        return report
    monkeypatch.setattr(module,'require_cad_dependencies',lambda:None)
    monkeypatch.setattr(module,'export_exterior',exterior)
    monkeypatch.setattr(module,'_execute',lambda command,*args:shutil.copyfile(command[6],command[7]))
    monkeypatch.setattr(module,'restore_fem_interface_coordinates',lambda raw,front,out:shutil.copyfile(raw,out) and {})
    monkeypatch.setattr(module,'surface_integrity',lambda path,**kwargs:{'sha256':sha256(path),'enclosed_volume_m3':1.})
    monkeypatch.setattr(module,'verify_exterior_groups',lambda *args:None)
    monkeypatch.setattr(module,'meshing_runtime_identity',lambda:{})
    monkeypatch.setattr(module,'observation_enclosing_radius',lambda path:.3)
    module.compile_radiating_system(geometry,sources,output,Runtime(),exterior_mesh_size_m=.01,
                                   sphere_angle_deg=getattr(request,'param',None))
    candidate={'design':HornGeometry.model_validate(_read_json(geometry/'geometry.json')['design']),
               'sources':sources}
    return root,candidate


def test_matching_compiled_candidate_is_accepted(compiled):
    root,candidate=compiled
    verify_candidate_project(root,candidate,.01)


@pytest.mark.parametrize('change',['mesh','source','medium','port','boundary'])
def test_consistently_rehashed_foreign_project_is_rejected(compiled, change):
    root,candidate=compiled
    path=root/'system/project.blab.json'
    project=_read_json(path)
    system=project['physical_system']
    if change=='mesh': system['metadata']['generated_mesh_sha256']['mesh:front']='b'*64
    if change=='source': system['components'][0]['parameters']['bl_n_per_a']*=2
    if change=='medium': system['regions'][0]['density_kg_per_m3']*=2
    if change=='port': system['excitation_ports'][0]['component_id']=system['components'][1]['id']
    if change=='boundary': system['components'][0]['boundary_ids']=system['components'][1]['boundary_ids']
    _write_json(path,project)
    report=_read_json(root/'system/compilation.json')
    report['project_sha256']=sha256(path)
    _write_json(root/'system/compilation.json',report)
    with pytest.raises(ValueError,match='differs from declared candidate'):
        verify_candidate_project(root,candidate,.01)


@pytest.mark.parametrize('compiled',[10.],indirect=True)
@pytest.mark.parametrize('change',[None,'undeclared','precision','disabled','metadata'])
def test_sphere_compilation_replays_only_with_matching_declared_sampling(compiled,change):
    root,candidate=compiled
    path=root/'system/project.blab.json'
    project=_read_json(path)
    report_path=root/'system/compilation.json'
    report=_read_json(report_path)
    if change=='precision':project['project_preferences']['balloon_angle_precision_deg']=5.
    if change=='disabled':project['project_preferences']['spherical_sampling_enabled']=False
    if change=='metadata':report['sphere_sampling']['point_count']=100
    _write_json(path,project);report['project_sha256']=sha256(path);_write_json(report_path,report)
    if change is None:
        verify_candidate_project(root,candidate,.01,10.)
    else:
        with pytest.raises(ValueError,match='sphere sampling|differs from declared candidate'):
            verify_candidate_project(root,candidate,.01,None if change=='undeclared' else 10.)


def test_recovery_requires_the_declared_observation_distance(compiled):
    root,candidate=compiled
    path=root/'system/project.blab.json'
    project=_read_json(path)
    project['project_preferences']['polar_observation_distance_m']=20.
    _write_json(path,project)
    report=_read_json(root/'system/compilation.json')
    report['project_sha256']=sha256(path)
    _write_json(root/'system/compilation.json',report)
    with pytest.raises(ValueError,match='differs from declared candidate'):
        verify_candidate_project(root,candidate,.01)
    verify_candidate_project(root,candidate,.01,observation_distance_m=20.)
