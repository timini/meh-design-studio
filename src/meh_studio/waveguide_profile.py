"""Bounded freeform cross sections shared by acoustic air and material CAD.

Controls are radial scales at eight azimuths (0,45,...315 degrees) and an
axial fraction. Smooth closed spline sections are lofted through those controls.
The throat remains a circular source interface. This is a design grammar, not
an acoustic approximation: the resulting full surface is meshed by the solver.
"""
from __future__ import annotations

import math
from typing import Annotated
from pydantic import Field, model_validator
from .domain import Record


class ProfileSection(Record):
    fraction: Annotated[float, Field(strict=True, gt=0, le=1)]
    radial_scales: tuple[Annotated[float, Field(strict=True, ge=.5, le=2)], ...]

    @model_validator(mode='after')
    def eight_controls(self):
        if len(self.radial_scales) != 8:
            raise ValueError('profile section requires eight azimuthal radial scales')
        return self


def validate_profile(sections):
    if not sections:
        return
    if not 2 <= len(sections) <= 8 or sections[-1].fraction != 1:
        raise ValueError('freeform profile requires 2–8 sections ending at the mouth')
    positions = [0.] + [section.fraction for section in sections]
    if any(b-a < .05 for a,b in zip(positions,positions[1:])):
        raise ValueError('profile sections must increase with at least 5 percent spacing')


def horn_solids(design):
    """Return unported air and its enclosing solid, in millimetres."""
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    length, throat, mouth, wall = [v*1000 for v in
        (design.length_m,design.throat_radius_m,design.mouth_radius_m,design.wall_m)]
    if not design.profile_sections:
        return (cq.Solid.makeCone(throat,mouth,length),
                cq.Solid.makeCone(throat+wall,mouth+wall,length))
    def loft(offset):
        wires = [cq.Wire.makeCircle(throat+offset,cq.Vector(0,0,0),cq.Vector(0,0,1))]
        for section in design.profile_sections:
            radius = throat+(mouth-throat)*section.fraction
            points = [cq.Vector((radius*scale+offset)*math.cos(i*math.pi/4),
                                (radius*scale+offset)*math.sin(i*math.pi/4),
                                length*section.fraction)
                      for i,scale in enumerate(section.radial_scales)]
            edge = (periodic_profile_edge(points) if design.profile_interpolation == 'periodic_cubic'
                    else cq.Edge.makeSpline(points,periodic=True))
            wires.append(cq.Wire.assembleEdges([edge]))
        return cq.Solid.makeLoft(wires,ruled=False)
    air, outer = loft(0), loft(wall)
    for solid in (air,outer):
        if not solid.isValid() or len(solid.Solids()) != 1 or solid.Volume() <= 0:
            raise ValueError('freeform loft produced an invalid solid')
    if air.cut(outer).Volume() > 1e-6:
        raise ValueError('freeform material envelope does not contain horn air')
    return air,outer


def mouth_face(design, air):
    faces = [face for face in air.Faces() if face.geomType()=='PLANE'
             and abs(face.Center().z-design.length_m*1000)<1e-5]
    if len(faces) != 1:
        raise ValueError('horn mouth must be one planar face')
    return faces[0]


def entry_support_radius(design, air, entry, axis):
    """Place freeform chambers outside the entire local horn envelope."""
    if not design.profile_sections:
        return design.throat_radius_m+(design.mouth_radius_m-design.throat_radius_m)*entry/design.length_m
    from .cad_runtime import load_cadquery
    cq=load_cadquery()
    margin=(design.front_radius_m+design.wall_m)*1000
    extent=air.BoundingBox()
    width=max(extent.xlen,extent.ylen)*2+100
    slab=cq.Workplane('XY').box(width,width,2*margin).translate((0,0,entry*1000)).val()
    local=air.intersect(slab)
    if local.Volume() <= 0:
        raise ValueError('entry has no horn air in its axial interval')
    box=local.BoundingBox()
    return (box.xmax if axis[0]>0 else -box.xmin if axis[0]<0
            else box.ymax if axis[1]>0 else -box.ymin)/1000


def cad_volume(design, shape):
    # Default non-adaptive BRepGProp integration is inaccurate on trimmed splines.
    return shape.Volume(tol=1e-9) if design.profile_sections else shape.Volume()


def imported_volume(design, default_volume, path):
    """Independently check the saved metre-scale OCC geometry with adaptive quadrature."""
    if not design.profile_sections:
        return default_volume
    import gmsh
    from .cad_runtime import load_cadquery
    cq=load_cadquery()
    gmsh.write(str(path))
    shape=cq.importers.importStep(str(path)).val()  # STEP units are converted to mm by OCCT.
    return cad_volume(design,shape)/1e9


def periodic_profile_edge(points):
    """Interpolate cyclic controls with a uniform periodic C2 cubic B-spline.

    At each uniform knot, (B[i-1] + 4 B[i] + B[i+1]) / 6 = P[i].
    Solving that cyclic system treats every azimuth identically, including the
    seam. The legacy GeomAPI interpolator gives its periodic junction only C1 continuity.
    """
    import numpy as np
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    from OCP.Geom import Geom_BSplineCurve
    from OCP.gp import gp_Pnt
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    values = np.asarray([point.toTuple() for point in points])
    n = len(values)
    system = 4 * np.eye(n) + np.roll(np.eye(n), 1, axis=1) + np.roll(np.eye(n), -1, axis=1)
    controls = np.linalg.solve(system, 6 * values)
    # OCCT's first periodic span evaluates poles 0/1/2: align t=0 with P[0].
    controls = np.roll(controls, 1, axis=0)
    poles = TColgp_Array1OfPnt(1, n)
    for i, point in enumerate(controls):
        poles.SetValue(i + 1, gp_Pnt(*point))
    knots = TColStd_Array1OfReal(1, n + 1)
    multiplicities = TColStd_Array1OfInteger(1, n + 1)
    for i in range(n + 1):
        knots.SetValue(i + 1, float(i))
        multiplicities.SetValue(i + 1, 1)
    curve = Geom_BSplineCurve(poles, knots, multiplicities, 3, True)
    return cq.Edge(BRepBuilderAPI_MakeEdge(curve).Edge())
