"""Axially refined P1 tetrahedra in a source-face extrusion verified against CAD."""
import math
import hashlib
from pathlib import Path


def layered_rear_volume(gmsh, volumes, source_tag, axis, depth, spacing):
    """Extrude the actual imported source face; verify the original CAD volume."""
    if len(volumes) != 1:
        raise ValueError('layered rear mesh requires one air volume')
    original_volume = gmsh.model.occ.getMass(*volumes[0])
    norm = math.sqrt(sum(v*v for v in axis))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError('layered rear mesh requires a finite motion axis')
    layers = math.ceil(depth / spacing)
    source = gmsh.model.occ.copy([(2, source_tag)])
    delta = [v * depth / norm for v in axis]
    extruded = gmsh.model.occ.extrude(source, *delta, numElements=[layers], recombine=False)
    new_volumes = [entity for entity in extruded if entity[0] == 3]
    if len(new_volumes) != 1:
        raise ValueError('rear source extrusion must produce one volume')
    volume = gmsh.model.occ.getMass(*new_volumes[0])
    # Equal volume alone cannot establish that the source was extruded in the
    # correct direction or that a future non-cylindrical cavity is represented.
    common, _ = gmsh.model.occ.intersect(gmsh.model.occ.copy(volumes),
                                        gmsh.model.occ.copy(new_volumes))
    overlap = sum(gmsh.model.occ.getMass(*entity) for entity in common if entity[0] == 3)
    if (not math.isclose(volume, original_volume, rel_tol=1e-6, abs_tol=1e-12)
            or not math.isclose(overlap, original_volume, rel_tol=1e-6, abs_tol=1e-12)):
        raise ValueError('layered rear extrusion differs from the exported air CAD')
    gmsh.model.occ.remove(volumes + common, recursive=True)
    gmsh.model.occ.synchronize()
    if gmsh.model.getEntities(3) != new_volumes:
        raise ValueError('layered rear extrusion left unexpected volumes')
    faces = gmsh.model.getBoundary(new_volumes, oriented=False)
    walls = [tag for dim, tag in faces if (dim, tag) != source[0]]
    if source[0] not in faces or not walls:
        raise ValueError('layered rear source and walls were not retained')
    report = {'method': 'source_face_extrusion_to_linear_tetrahedra',
              'mesher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'maximum_axial_spacing_m': spacing, 'actual_axial_spacing_m': depth / layers,
              'layers': layers, 'source_surface_tag': source[0][1],
              'original_cad_volume_m3': original_volume, 'extruded_cad_volume_m3': volume,
              'common_cad_volume_m3': overlap}
    return new_volumes, [source[0][1]], walls, report


def check_layered_workload(gmsh, report, maximum_tetrahedra):
    """Use the actual base triangulation before generating the volume layers."""
    gmsh.model.mesh.generate(2)
    types, elements, _ = gmsh.model.mesh.getElements(2, report['source_surface_tag'])
    if list(types) != [2] or not len(elements[0]):
        raise ValueError('layered rear source requires linear triangles')
    predicted = 3 * len(elements[0]) * report['layers']
    report['source_triangles'] = len(elements[0])
    report['predicted_tetrahedra'] = predicted
    if predicted > maximum_tetrahedra:
        raise ValueError('layered rear tetrahedral workload exceeds the mesh budget')
