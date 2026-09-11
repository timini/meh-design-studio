from pathlib import Path

import pytest

from meh_studio.geometry import HornGeometry
from meh_studio.radiation_geometry import export_exterior, surface_integrity


@pytest.mark.cad
def test_closed_exterior_has_one_mouth_and_positive_volume(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("gmsh")
    design = HornGeometry.model_validate_json((Path(__file__).resolve().parents[1] /
        "examples/three-driver-geometry.json").read_text())
    report = export_exterior(design, tmp_path / "exterior")
    assert report["status"] == "complete" and report["print_part"] is False
    assert report["surface"]["open_edges"] == report["surface"]["orientation_errors"] == 0
    assert report["surface"]["enclosed_volume_m3"] == pytest.approx(report["cad_volume_m3"], rel=.02)


@pytest.mark.cad
@pytest.mark.parametrize("fault", [None, "open", "mixed_orientation", "inward", "disconnected", "pinched"])
def test_bem_topology_checks_reject_invalid_surfaces(tmp_path, fault):
    pytest.importorskip("gmsh")
    nodes = [(0,0,0), (1,0,0), (0,1,0), (0,0,1)]
    faces = [(1,3,2), (1,2,4), (1,4,3), (2,3,4)]
    if fault == "open": faces.pop()
    if fault == "mixed_orientation": faces[0] = tuple(reversed(faces[0]))
    if fault == "inward": faces = [tuple(reversed(face)) for face in faces]
    if fault == "disconnected":
        nodes += [(x+2,y,z) for x,y,z in nodes[:]]
        faces += [tuple(node+4 for node in face) for face in faces[:]]
    if fault == "pinched":
        nodes += [(-1,0,0), (0,-1,0), (0,0,-1)]
        mapping = {1:1, 2:5, 3:6, 4:7}
        faces += [tuple(mapping[n] for n in reversed(face)) for face in faces[:]]
    lines = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(nodes))]
    lines += [f"{i} {x} {y} {z}" for i,(x,y,z) in enumerate(nodes,1)]
    lines += ["$EndNodes", "$Elements", str(len(faces))]
    lines += [f"{i} 2 2 1 1 " + " ".join(map(str,face)) for i,face in enumerate(faces,1)]
    lines += ["$EndElements"]
    path = tmp_path / "surface.msh"
    path.write_text("\n".join(lines) + "\n")
    if fault is not None:
        with pytest.raises(ValueError): surface_integrity(path)
    else:
        assert surface_integrity(path)["enclosed_volume_m3"] == pytest.approx(1/6)
        with pytest.raises(ValueError,match='1–3'):
            surface_integrity(path,maximum_triangles=3)
        assert surface_integrity(path,maximum_triangles=4)['triangles']==4


def test_radiating_command_imports_and_reports_invalid_runtime(tmp_path, monkeypatch, capsys):
    from meh_studio.radiating_system import compile_radiating_system
    class InvalidRuntime:
        def verify(self):
            raise ValueError("invalid runtime")
    with pytest.raises(ValueError, match="invalid runtime"):
        compile_radiating_system(tmp_path, None, tmp_path / "output", InvalidRuntime())


def test_threaded_compilation_rejected_without_side_effects(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from meh_studio.radiating_system import compile_radiating_system
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(compile_radiating_system, tmp_path, None, tmp_path/'out', None)
        with pytest.raises(ValueError, match='background thread'):
            result.result()
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('fault', [None, 'name', 'tag', 'coverage'])
def test_conformed_exterior_physical_groups(tmp_path, fault):
    from meh_studio.radiation_geometry import verify_exterior_groups
    name = 'wrong_mouth' if fault == 'name' else 'mouth_interface'
    tag = 11 if fault == 'tag' else 10
    element_tag = 99 if fault == 'coverage' else tag
    path = tmp_path/'surface.msh'
    path.write_text(f'''$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
2
2 {tag} "{name}"
2 99 "rigid_exterior"
$EndPhysicalNames
$Nodes
4
1 0 0 0
2 1 0 0
3 0 1 0
4 0 0 1
$EndNodes
$Elements
4
1 2 2 {element_tag} 1 1 3 2
2 2 2 99 2 1 2 4
3 2 2 99 2 1 4 3
4 2 2 99 2 2 3 4
$EndElements
''')
    if fault:
        with pytest.raises(ValueError, match='physical'):
            verify_exterior_groups(path)
    else:
        verify_exterior_groups(path)


def test_conformed_mouth_facets_must_match_fem(tmp_path):
    from meh_studio.radiation_geometry import verify_exterior_groups
    import meshio
    import numpy as np
    points = np.array([[0.,0,0],[1.,0,0],[0,1.,0],[0,0,1.]])
    faces = np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    def write(path, tags, names):
        meshio.write(path, meshio.Mesh(points, [('triangle', faces)],
            cell_data={'gmsh:physical':[np.array(tags)],'gmsh:geometrical':[np.ones(4,dtype=int)]},
            field_data=names), file_format='gmsh22', binary=False)
    front, exterior = tmp_path/'front.msh', tmp_path/'exterior.msh'
    write(front, [10,99,99,99], {'mouth_interface':[10,2], 'rigid_walls':[99,2]})
    names = {'mouth_interface':[10,2], 'rigid_exterior':[99,2]}
    write(exterior, [10,99,99,99], names)
    verify_exterior_groups(exterior, front)
    write(exterior, [99,10,99,99], names)
    with pytest.raises(ValueError, match='triangle membership'):
        verify_exterior_groups(exterior, front)


def test_step_geometry_identity_ignores_only_header(tmp_path):
    from meh_studio.radiation_geometry import step_geometry_sha256
    path = tmp_path/'shape.step'
    path.write_text('HEADER; timestamp A; ENDSEC; DATA; #1=POINT(1,2,3); ENDSEC;')
    original = step_geometry_sha256(path)
    path.write_text('HEADER; timestamp B; ENDSEC; DATA; #1=POINT(1,2,3); ENDSEC;')
    assert step_geometry_sha256(path) == original
    path.write_text('HEADER; timestamp B; ENDSEC; DATA; #1=POINT(9,2,3); ENDSEC;')
    assert step_geometry_sha256(path) != original


@pytest.mark.cad
def test_regenerated_exterior_has_stable_geometry_identity(tmp_path):
    import importlib.util
    if importlib.util.find_spec('cadquery') is None or importlib.util.find_spec('gmsh') is None:
        pytest.skip('CAD runtimes unavailable')
    design = HornGeometry.model_validate_json((Path(__file__).resolve().parents[1]/'examples/three-driver-geometry.json').read_text())
    coarse = export_exterior(design, tmp_path/'coarse', .02)
    fine = export_exterior(design, tmp_path/'fine', .015)
    assert coarse['cad_geometry_sha256'] == fine['cad_geometry_sha256']
    assert coarse['surface']['sha256'] != fine['surface']['sha256']


@pytest.mark.parametrize('options',[{'exterior_mesh_size_m':.001},{'timeout_s':0},{'timeout_s':float('nan')}])
def test_invalid_radiating_options_do_not_reserve_output(tmp_path, options):
    from meh_studio.radiating_system import compile_radiating_system
    with pytest.raises(ValueError):
        compile_radiating_system(tmp_path,None,tmp_path/'out',None,**options)
    assert not (tmp_path/'out').exists()


def test_missing_cad_dependencies_do_not_reserve_compilation(tmp_path,monkeypatch):
    import meh_studio.radiating_system as radiation
    class Runtime:
        def verify(self):return {}
    def missing():raise ImportError('optional CAD dependencies missing')
    monkeypatch.setattr(radiation,'require_cad_dependencies',missing)
    with pytest.raises(ImportError,match='optional CAD'):
        radiation.compile_radiating_system(tmp_path,None,tmp_path/'out',Runtime())
    assert not (tmp_path/'out').exists()


def test_missing_cad_dependency_is_a_structured_cli_error(tmp_path,monkeypatch,capsys):
    from meh_studio.cli import main
    from meh_studio.boundary_lab import BoundaryLabRuntime
    import meh_studio.radiating_system as radiation
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:{})
    def missing():raise ImportError('optional CAD dependencies missing')
    monkeypatch.setattr(radiation,'require_cad_dependencies',missing)
    sources=Path(__file__).resolve().parents[1]/'examples/synthetic-horn-sources.json'
    code=main(['compile-radiating',str(tmp_path),'--sources',str(sources),'--output',str(tmp_path/'out'),
               '--checkout',str(tmp_path),'--python','python','--julia','julia'])
    assert code==2 and 'optional CAD dependencies missing' in capsys.readouterr().err
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('distance',[0.,-1.,float('nan'),float('inf'),True,'20'])
def test_invalid_observation_distance_does_not_reserve_output(tmp_path,distance):
    from meh_studio.radiating_system import compile_radiating_system
    with pytest.raises(ValueError,match='observation distance'):
        compile_radiating_system(tmp_path,None,tmp_path/'out',None,observation_distance_m=distance)
    assert not (tmp_path/'out').exists()


def test_observation_sphere_encloses_asymmetric_translated_mesh_vertices(tmp_path):
    import meshio
    import numpy as np
    from meh_studio.radiating_system import observation_enclosing_radius
    points=np.array([[0.,0.,.3],[.2,0.,.3],[0.,-.4,.3]])
    path=tmp_path/'surface.msh'
    meshio.write(path,meshio.Mesh(points,[('triangle',np.array([[0,1,2]]))]),file_format='gmsh22',binary=False)
    assert observation_enclosing_radius(path)==pytest.approx(.5)
