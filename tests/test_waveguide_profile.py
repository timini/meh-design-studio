import json
from pathlib import Path
import pytest
from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry
from meh_studio.waveguide_profile import ProfileSection, mouth_face

EXAMPLES=Path(__file__).resolve().parents[1]/'examples'


def test_profile_controls_require_full_ordered_sections():
    base=json.loads((EXAMPLES/'compact-ring-geometry.json').read_text())
    for controls in ([{'fraction':1.,'radial_scales':[1.]*8}],
                     [{'fraction':.7,'radial_scales':[1.]*8},{'fraction':.5,'radial_scales':[1.]*8}],
                     [{'fraction':.4,'radial_scales':[1.]*7},{'fraction':1.,'radial_scales':[1.]*8}]):
        with pytest.raises(ValueError):HornGeometry.model_validate(base|{'profile_sections':controls})
    with pytest.raises(ValueError):ProfileSection(fraction=.5,radial_scales=[float('nan')]*8)


@pytest.mark.cad
def test_freeform_ring_uses_actual_non_circular_mouth(tmp_path):
    pytest.importorskip('cadquery');pytest.importorskip('gmsh')
    from meh_studio.radiation_geometry import export_exterior
    from meh_studio.generated_system import HornSources,compile_interior_system
    design=HornGeometry.model_validate_json((EXAMPLES/'freeform-ring-geometry.json').read_text())
    geometry=export_geometry(design,tmp_path/'geometry')
    mouth=geometry['mouth_interface']
    assert geometry['driver_count']==5
    assert mouth['area_m2']>0
    import math
    assert abs(mouth['area_m2']/(math.pi*design.mouth_radius_m**2)-1)>.01
    mesh=mesh_geometry(tmp_path/'geometry')
    assert len(mesh['regions'])==5
    for region in mesh['regions']:
        assert all(c['relative_area_error']<.01 for c in region['source_area_checks'])
    sources=json.loads((EXAMPLES/'synthetic-horn-sources.json').read_text())
    sources['side']['sd_m2']=math.pi*design.front_radius_m**2
    compilation=compile_interior_system(tmp_path/'geometry',HornSources.model_validate(sources),tmp_path/'system')
    assert compilation['driver_count']==5
    exterior=export_exterior(design,tmp_path/'exterior',.01)
    assert exterior['status']=='complete'
    assert exterior['surface']['orientation_errors']==0


@pytest.mark.cad
def test_irregular_mouth_polygons_agree_before_conforming(tmp_path):
    """Regression: an evolved rim failed native conformity by 0.97 mm."""
    pytest.importorskip('cadquery');pytest.importorskip('gmsh')
    import numpy as np
    import meshio
    from collections import Counter
    from meh_studio.radiation_geometry import export_exterior
    fixture=Path(__file__).parent/'fixtures/freeform-curved-rim.json'
    design=HornGeometry.model_validate_json(fixture.read_text())
    export_geometry(design,tmp_path/'geometry')
    mesh_geometry(tmp_path/'geometry')
    exterior=export_exterior(design,tmp_path/'exterior',.01)
    assert exterior['mouth_rim_sampling']['maximum_target_spacing_m']==design.mesh_size_m/2

    def rim(path):
        mesh=meshio.read(path)
        tag=int(mesh.field_data['mouth_interface'][0]);edges=Counter()
        for block,tags in zip(mesh.cells,mesh.cell_data['gmsh:physical']):
            if block.type!='triangle':continue
            for a,b,c in block.data[np.asarray(tags)==tag]:
                edges.update(tuple(sorted(e)) for e in ((a,b),(b,c),(c,a)))
        boundary=np.array([e for e,n in edges.items() if n==1])
        assert len(boundary)>8
        return mesh.points[np.unique(boundary)],mesh.points[boundary]

    a,edges_a=rim(tmp_path/'geometry/analysis/front.msh')
    b,edges_b=rim(tmp_path/'exterior/exterior.msh')
    def deviation(points,edges):
        start=edges[:,0];delta=edges[:,1]-start
        t=np.clip(np.sum((points[:,None]-start)*delta,axis=2)/np.sum(delta*delta,axis=1),0,1)
        distance=np.linalg.norm(points[:,None]-start-t[:,:,None]*delta,axis=2)
        return float(distance.min(axis=1).max())
    # The actual failed native perimeter tolerance was 0.802 mm. Use a
    # stricter independent geometric screen; do not relax native acceptance.
    assert max(deviation(a,edges_b),deviation(b,edges_a))<.0005
