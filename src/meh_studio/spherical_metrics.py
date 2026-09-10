"""Whole-sphere pressure metrics on the pinned solver's Fibonacci sample grid."""
from __future__ import annotations
from typing import Annotated
import numpy as np
from pydantic import Field
from .domain import Positive, Record


class SphericalObjectives(Record):
    angle_precision_deg: Annotated[float,Field(strict=True,ge=2.5,le=15)] = 10.
    control_from_hz: Positive = 1000.
    rear_attenuation_db: Annotated[float,Field(strict=True,ge=6,le=60)] = 30.


def fibonacci_directions(count):
    if type(count) is not int or not 100<=count<=10000:
        raise ValueError('sphere sampling requires 100–10000 points')
    i=np.arange(count,dtype=float);z=1-2*(i+.5)/count
    radius=np.sqrt(1-z*z);phi=np.pi*(3-np.sqrt(5))*i
    return np.column_stack((radius*np.cos(phi),radius*np.sin(phi),z))


def sphere_geometry(points, horizontal_coverage_deg, vertical_coverage_deg, rear_attenuation_db):
    points=np.asarray(points,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():
        raise ValueError('finite complete sphere coordinates required')
    radius=np.linalg.norm(points,axis=1);directions=fibonacci_directions(len(points))
    if np.any(radius<=0) or not np.allclose(radius,radius[0],rtol=1e-6,atol=1e-9):
        raise ValueError('sphere points must share a positive radius about the origin')
    if not np.allclose(points/radius[:,None],directions,rtol=1e-6,atol=1e-9):
        raise ValueError('sphere coordinates differ from the complete pinned Fibonacci grid')
    if not all(np.isfinite(c) and 20<=c<=180 for c in (horizontal_coverage_deg,vertical_coverage_deg)):
        raise ValueError('bounded horizontal and vertical coverage required')
    if not np.isfinite(rear_attenuation_db) or not 6<=rear_attenuation_db<=60:
        raise ValueError('rear attenuation must be within 6–60 dB')
    horizontal=np.rad2deg(np.arctan2(directions[:,0],directions[:,2]))
    vertical=np.rad2deg(np.arctan2(directions[:,1],directions[:,2]))
    target=np.maximum(-rear_attenuation_db,-6*((horizontal/(horizontal_coverage_deg/2))**2+
                                            (vertical/(vertical_coverage_deg/2))**2))
    target[directions[:,2]<=0]=-rear_attenuation_db
    return target,float(radius[0]),4*np.pi/len(points)


def sphere_error(pressure, axial_pressure, frequencies_hz, points, objectives,
                 horizontal_coverage_deg, vertical_coverage_deg):
    pressure=np.asarray(pressure,dtype=complex);axial=np.asarray(axial_pressure,dtype=complex)
    f=np.asarray(frequencies_hz,dtype=float)
    target,radius,weight=sphere_geometry(points,horizontal_coverage_deg,vertical_coverage_deg,
                                        objectives.rear_attenuation_db)
    if len(target)!=round(41253/objectives.angle_precision_deg**2):
        raise ValueError('sphere sample count differs from declared angular precision')
    if (f.ndim!=1 or not len(f) or not np.isfinite(f).all() or np.any(f<=0) or np.any(np.diff(f)<=0)
            or pressure.shape!=(len(f),len(target)) or axial.shape!=(len(f),)
            or not np.isfinite(pressure).all() or not np.isfinite(axial).all() or np.any(abs(axial)==0)):
        raise ValueError('finite frequency-aligned sphere pressure and nonnull axial reference required')
    selected=f>=objectives.control_from_hz
    if not np.any(selected):raise ValueError('sphere coverage control band has no frequency samples')
    relative=abs(pressure)/abs(axial[:,None])
    relative_db=20*np.log10(np.maximum(relative,1e-6))
    # Equal solid-angle quadrature is approximate on the Fibonacci grid.
    # Sum weights explicitly so a partial sphere cannot become a normalised mean.
    mean_square=(relative**2).sum(axis=1)*weight/(4*np.pi)
    if not np.isfinite(mean_square).all() or np.any(mean_square<=0):
        raise ValueError('whole-sphere mean-square pressure must be positive and finite')
    per_frequency=np.sqrt(((relative_db-target)**2).sum(axis=1)*weight/(4*np.pi))
    return {'sampling':'complete_pinned_fibonacci_equal_solid_angle',
        'sample_count':len(target),'radius_m':radius,'solid_angle_weight_sr':weight,
        'control_from_hz':objectives.control_from_hz,'scored_frequencies_hz':f[selected].tolist(),
        'rms_target_error_db':float(np.sqrt(np.mean(per_frequency[selected]**2))),
        'per_frequency_rms_target_error_db':per_frequency.tolist(),
        'sphere_mean_square_pressure_relative_to_axis':mean_square.tolist(),
        'on_axis_to_sphere_mean_db':(-10*np.log10(mean_square)).tolist(),
        'target':'forward elliptical angular -6 dB envelope, clipped to declared rear attenuation',
        'rear_attenuation_db':objectives.rear_attenuation_db,'angular_convergence_validated':False,
        'radiated_power_or_efficiency_qualified':False}


def denser_validation_brief(brief):
    """Hold DSP fixed while requesting four times as many sphere observations."""
    if brief.acoustic_objectives is None or brief.acoustic_objectives.sphere is None:
        return brief
    angle=brief.acoustic_objectives.sphere.angle_precision_deg/2
    if angle<2.5:
        raise ValueError('denser finalist sphere grid exceeds supported 2.5 degree minimum')
    data=brief.model_dump(mode='json')
    data['acoustic_objectives']['sphere']['angle_precision_deg']=angle
    return type(brief).model_validate(data)
