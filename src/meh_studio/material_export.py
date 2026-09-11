"""Use an absolute linear tolerance for both printable triangle formats."""
import hashlib
from pathlib import Path
import numpy as np


def export_material_meshes(shape, stl, threemf, tolerance_m):
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    from OCP.BRepTools import BRepTools
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    import meshio
    from cadquery.occ_impl.exporters.threemf import ThreeMFWriter

    requested_mm = tolerance_m * 1000
    attempts = []
    for refinement in range(5):
        deflection = requested_mm / 2**refinement
        angular = .1 / 2**refinement
        BRepTools.Clean_s(shape.wrapped)
        mesher = BRepMesh_IncrementalMesh(shape.wrapped, deflection, False, angular, False)
        confirmed = BRepTools.Triangulation_s(shape.wrapped, requested_mm)
        roundoff = None
        if confirmed:
            vertices, triangles = shape.tessellate(requested_mm, .1)
            original = np.array([v.toTuple() for v in vertices], dtype=float)
            # Both formats use exactly the binary STL coordinate representation.
            coordinates = original.astype(np.float32).astype(float)
            roundoff = float(np.linalg.norm(coordinates - original, axis=1).max())
            confirmed = (roundoff < requested_mm and BRepTools.Triangulation_s(
                shape.wrapped, requested_mm - roundoff))
        attempts.append({'absolute_deflection_mm': deflection,
                         'angular_deflection_rad': angular,
                         'mesher_status': mesher.GetStatusFlags(),
                         'coordinate_roundoff_mm': roundoff,
                         'requested_tolerance_confirmed': bool(confirmed)})
        if confirmed:
            break
    else:
        raise ValueError('absolute material tessellation did not meet the requested tolerance')
    points, inverse = np.unique(coordinates, axis=0, return_inverse=True)
    faces = inverse[np.asarray(triangles)]
    collapsed = ((faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2])
                 | (faces[:, 2] == faces[:, 0]))
    # Revolution poles can contain an empty triangle with repeated coordinates.
    # Remove only those zero-area facets; no proximity welding or hole filling.
    # The caller still requires closed oriented edges and the original CAD volume.
    faces = faces[~collapsed]
    meshio.write(stl, meshio.Mesh(points, [('triangle', faces)]), file_format='stl', binary=True)

    class CheckedMeshWriter(ThreeMFWriter):
        def __init__(self):
            self.unit = 'millimeter'
            self.tessellations = [([cq.Vector(*point) for point in points],
                                  [tuple(map(int, face)) for face in faces])]

    CheckedMeshWriter().write3mf(threemf)
    return {'linear_tolerance_m': tolerance_m, 'relative': False,
            'angular_tolerance_rad': .1, 'attempts': attempts,
            'removed_collapsed_triangles': int(collapsed.sum()),
            'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
