"""Explicit axisymmetric rigid diaphragms, in CAD millimetres.

The supplied heights are Bezier controls at uniformly spaced radii, not a
manufacturer cone model inferred from effective piston area or T/S parameters.
"""
import math


def profile_solid(radius_mm, heights_m):
    """Volume between the reference disk and its single curved source face."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    points = [cq.Vector(radius_mm * i / (len(heights_m) - 1), 0, h * 1000)
              for i, h in enumerate(heights_m)]
    origin = cq.Vector(0, 0, 0)
    wire = cq.Wire.assembleEdges([
        cq.Edge.makeLine(origin, points[-1]), cq.Edge.makeBezier(points),
        cq.Edge.makeLine(points[0], origin)])
    solid = cq.Solid.revolve(wire, [], 360, origin, cq.Vector(0, 0, 1))
    degree = len(heights_m) - 1
    exact = (2 * math.pi * radius_mm**2 * 1000
             * sum((i + 1) * h for i, h in enumerate(heights_m))
             / ((degree + 1) * (degree + 2)))
    if (not solid.isValid() or len(solid.Solids()) != 1
            or not math.isclose(solid.Volume(), exact, rel_tol=1e-7)):
        raise ValueError('diaphragm profile CAD differs from its analytic volume')
    return solid


def orient(shape, centre_m, axis):
    """Map the local positive Z motion axis into assembly coordinates."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    direction = cq.Vector(*axis).normalized()
    z = cq.Vector(0, 0, 1)
    cross = z.cross(direction)
    dot = max(-1., min(1., z.dot(direction)))
    if cross.Length > 1e-12:
        shape = shape.rotate((0, 0, 0), cross.toTuple(), math.degrees(math.acos(dot)))
    elif dot < 0:
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    return shape.translate(tuple(v * 1000 for v in centre_m))


def swept_profile(profile, radius_mm, depth_mm):
    """Air between a source and an axially translated copy of that surface."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    cylinder = cq.Solid.makeCylinder(radius_mm, depth_mm)
    result = cylinder.fuse(profile.translate((0, 0, depth_mm))).cut(profile).clean()
    if (not result.isValid() or len(result.Solids()) != 1
            or not math.isclose(result.Volume(), math.pi * radius_mm**2 * depth_mm,
                                rel_tol=1e-7)):
        raise ValueError('swept diaphragm CAD differs from its projected-area volume')
    return result


def source_face(profile):
    faces = [face for face in profile.Faces() if face.geomType() != 'PLANE']
    if len(faces) != 1:
        raise ValueError('diaphragm profile must produce exactly one curved source face')
    return faces[0]


def descriptor(face):
    """Geometric identity retained through STEP import; no tessellation fitting."""
    from .reduced_geometry import adaptive_area
    return {'center_m': [v / 1000 for v in face.Center().toTuple()],
            'area_m2': adaptive_area(face)}


def diaphragm_gap(design, source):
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    radius = source['radius_m'] * 1000
    if design.diaphragm_profile_m:
        profile = profile_solid(radius, design.diaphragm_profile_m)
        gap = swept_profile(profile, radius, design.wall_m * 1000)
        return orient(gap, source['front_center_m'], source['motion_axis'])
    return cq.Solid.makeCylinder(radius, design.wall_m * 1000,
        cq.Vector(*[v * 1000 for v in source['front_center_m']]),
        cq.Vector(*source['motion_axis']))
