"""CAD-verified even XY reduction, retaining the complete physical design.

Only equal mirror-partner excitation is represented. Surface completion and
physical coil multiplicity are separate quantities, inferred again from meshes
when the generated system is compiled.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .boundary_lab import _write_json, sha256
from .waveguide_profile import cad_volume, imported_volume, mouth_face


CAD_RELATIVE_TOLERANCE = 1e-6


def adaptive_area(face):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    properties = GProp_GProps()
    error = BRepGProp.SurfaceProperties_s(face.wrapped, properties, 1e-10, False)
    if not math.isfinite(error) or error > 1e-9:
        raise ValueError('trimmed source area integration did not converge')
    return properties.Mass() / 1e6


def mirror_difference(design, original, reflected):
    volume = cad_volume(design, original)
    error = (cad_volume(design, original.cut(reflected)) +
             cad_volume(design, reflected.cut(original))) / volume
    if not math.isfinite(error) or error > CAD_RELATIVE_TOLERANCE:
        raise ValueError('CAD does not satisfy requested XY mirror symmetry')
    return error


def quarter_solid(design, shape, fraction):
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    bounds = shape.BoundingBox()
    margin = 1.  # mm; clip only X/Y, never a physical end face.
    box = cq.Solid.makeBox(max(bounds.xmax, 0) + margin,
                          max(bounds.ymax, 0) + margin,
                          bounds.zlen + 2 * margin,
                          cq.Vector(0, 0, bounds.zmin - margin))
    result = shape.intersect(box).clean()
    if not result.isValid() or len(result.Solids()) != 1:
        raise ValueError('quarter CAD must be one valid connected solid')
    volume = cad_volume(design, result)
    if volume <= 0 or not math.isclose(volume / cad_volume(design, shape), fraction,
                                       rel_tol=CAD_RELATIVE_TOLERANCE):
        raise ValueError('quarter CAD volume differs from its physical fraction')
    bounds = result.BoundingBox()
    if bounds.xmin < -1e-6 or bounds.ymin < -1e-6:
        raise ValueError('quarter CAD extends outside the positive XY domain')
    return result


def quarter_envelope(design, body, front):
    checks = {plane: mirror_difference(design, body, body.mirror(plane))
              for plane in ('YZ', 'XZ')}
    reduced = quarter_solid(design, body, .25)
    cap = mouth_face(design, quarter_solid(design, front, .25))
    return reduced, cap, checks


def _source_descriptor(shape, point, axis, expected_area, role):
    centre = np.asarray(point) * 1000
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    matches = [face for face in shape.Faces() if face.geomType() == 'PLANE'
               and abs(np.dot(np.array(face.Center().toTuple()) - centre, axis)) < 1e-6
               and abs(np.dot(face.normalAt().toTuple(), axis)) > 1 - 1e-10]
    if len(matches) != 1:
        raise ValueError('quarter source plane must identify one CAD face')
    area = adaptive_area(matches[0])
    if not math.isclose(area, expected_area, rel_tol=CAD_RELATIVE_TOLERANCE):
        raise ValueError('quarter source area differs from its physical fraction')
    return {'center_m': [v / 1000 for v in matches[0].Center().toTuple()],
            'area_m2': area, 'role': role}


def _curved_source_descriptor(full, reduced, surface, projected_area, axis):
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    matches = [face for face in full.Faces()
               if math.dist([v / 1000 for v in face.Center().toTuple()], surface['center_m']) < 1e-7
               and math.isclose(adaptive_area(face), surface['area_m2'], rel_tol=CAD_RELATIVE_TOLERANCE)]
    if len(matches) != 1:
        raise ValueError('full curved source must identify one CAD face')
    bounds = full.BoundingBox()
    box = cq.Solid.makeBox(max(bounds.xmax, 0) + 1, max(bounds.ymax, 0) + 1,
                          bounds.zlen + 2, cq.Vector(0, 0, bounds.zmin - 1))
    # Merge the two trims when the retained half crosses the revolution seam,
    # matching the cleanup already applied to the quarter air solid.
    cut = matches[0].intersect(box).clean()
    if not cut.isValid() or len(cut.Faces()) != 1:
        raise ValueError('curved source partition must retain one connected face')
    from .diaphragm_geometry import descriptor
    value = descriptor(cut.Faces()[0])
    if not math.isclose(value['area_m2'], surface['area_m2'] / 2, rel_tol=CAD_RELATIVE_TOLERANCE):
        raise ValueError('curved source area differs from its physical half')
    matches = [face for face in reduced.Faces()
               if math.dist([v / 1000 for v in face.Center().toTuple()], value['center_m']) < 1e-7
               and math.isclose(adaptive_area(face), value['area_m2'], rel_tol=CAD_RELATIVE_TOLERANCE)]
    if len(matches) != 1:
        raise ValueError('curved source is not retained in quarter air CAD')
    return value | {'role': 'source', 'curved': True,
                    'projected_area_m2': projected_area, 'motion_axis': axis}


def _partition(output, geometry, design, directory):
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    paths = {name: output / 'air' / f'{name}.step' for name in geometry['air_volume_m3']}
    identities = {name: sha256(path) for name, path in paths.items()}
    full = {name: cq.importers.importStep(str(path)).val() for name, path in paths.items()}
    checks = {'front': {plane: mirror_difference(design, full['front'], full['front'].mirror(plane))
                        for plane in ('YZ', 'XZ')}}
    sources = {source['id']: source for source in geometry['sources']}
    retained = [name for name, _, _ in design.solver_entry_sites]
    reduced = {'front': quarter_solid(design, full['front'], .25)}
    for name in retained:
        # Canonical layout uses one pair on X, optionally a second pair on Y.
        plane, self_plane = ('XZ', 'YZ') if name.endswith('_y') else ('YZ', 'XZ')
        partner = name.replace('positive', 'negative')
        shape = full['rear_' + name]
        checks[name] = {'partner': mirror_difference(design, full['rear_' + partner], shape.mirror(plane)),
                        'self': mirror_difference(design, shape, shape.mirror(self_plane))}
        reduced['rear_' + name] = quarter_solid(design, shape, .5)
    descriptors = {name: {} for name in reduced}
    descriptors['front']['throat_source'] = _source_descriptor(
        reduced['front'], [0, 0, 0], [0, 0, 1], math.pi * design.throat_radius_m**2 / 4, 'source')
    descriptors['front']['mouth_interface'] = _source_descriptor(
        reduced['front'], [0, 0, design.length_m], [0, 0, 1],
        adaptive_area(mouth_face(design, full['front'])) / 4, 'radiation_interface')
    for name in retained:
        source = sources[name]
        for side, region in [('front', 'front'), ('rear', 'rear_' + name)]:
            if source.get(side + '_surface'):
                value = _curved_source_descriptor(full[region], reduced[region],
                    source[side + '_surface'], math.pi * source['radius_m']**2 / 2,
                    source['motion_axis'])
            else:
                value = _source_descriptor(reduced[region], source[side + '_center_m'],
                    source['motion_axis'], math.pi * source['radius_m']**2 / 2, 'source')
            descriptors[region][name + '_' + side + '_source'] = value
    cad_files = {}
    for name, shape in reduced.items():
        path = directory / f'{name}.step'
        cq.exporters.export(shape, str(path))
        cad_files[name] = {'path': path.relative_to(output).as_posix(), 'sha256': sha256(path),
                           'volume_m3': cad_volume(design, shape) / 1e9}
    if identities != {name: sha256(path) for name, path in paths.items()}:
        raise ValueError('full CAD changed during quarter partition')
    return {'mode': 'xy', 'relative_tolerance': CAD_RELATIVE_TOLERANCE, 'checks': checks,
            'full_cad_sha256': identities, 'cad_files': cad_files, 'boundaries': descriptors}


def mesh_quarter_geometry(output: Path, geometry, design):
    import gmsh
    from .geometry import (CURVATURE_ELEMENTS, SOURCE_AREA_RELATIVE_TOLERANCE,
                           estimated_curved_tetrahedra, source_area_checks)
    directory = output / 'analysis'
    directory.mkdir(exist_ok=False)
    report = {'schema_version': 1, 'status': 'running', 'units': 'm', 'solver_symmetry': 'xy',
              'design_hash': design.content_hash, 'accuracy': 'not_converged', 'regions': [],
              'workload_limit_tetrahedra_per_region': design.maximum_tetrahedra,
              'size_policy': {'maximum_m': design.mesh_size_m,
                  'minimum_m': min(design.mesh_size_m, math.pi * min(design.throat_radius_m,
                      design.port_radius_m, design.front_radius_m) / CURVATURE_ELEMENTS),
                  'curvature_elements_per_revolution': CURVATURE_ELEMENTS,
                  'source_area_relative_tolerance': SOURCE_AREA_RELATIVE_TOLERANCE}}
    try:
        partition = _partition(output, geometry, design, directory)
        _write_json(directory / 'partition.json', partition)
        report['partition_sha256'] = sha256(directory / 'partition.json')
        for region, boundaries in partition['boundaries'].items():
            item = partition['cad_files'][region]
            expected_volume = item['volume_m3']
            estimate = (estimated_curved_tetrahedra(design, region, geometry['air_volume_m3'][region]) / 4
                        if region == 'front' else estimated_curved_tetrahedra(design, region, expected_volume))
            if estimate > design.maximum_tetrahedra:
                raise ValueError('estimated tetrahedral workload exceeds this generator\'s mesh budget')
            gmsh.initialize()
            try:
                gmsh.option.setNumber('General.Terminal', 0)
                gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
                path = output / item['path']
                if sha256(path) != item['sha256']:
                    raise ValueError('quarter CAD changed before meshing')
                gmsh.model.occ.importShapes(str(path))
                gmsh.model.occ.synchronize()
                volumes = gmsh.model.getEntities(3)
                if len(volumes) != 1:
                    raise ValueError('quarter air region must import as one solid')
                volume = imported_volume(design, gmsh.model.occ.getMass(*volumes[0]), directory / f'{region}-imported.step')
                if not math.isclose(volume, expected_volume, rel_tol=1e-6, abs_tol=1e-12):
                    raise ValueError('quarter CAD-to-analysis volume or unit mismatch')
                selected = {name: [] for name in boundaries}
                walls = []
                for dim, tag in gmsh.model.getBoundary(volumes, oriented=False):
                    centre = gmsh.model.occ.getCenterOfMass(dim, tag)
                    matches = [name for name, descriptor in boundaries.items()
                               if (descriptor.get('curved') or gmsh.model.getType(dim, tag) == 'Plane')
                               and math.dist(centre, descriptor['center_m']) < 1e-7
                               and (not descriptor.get('curved') or math.isclose(
                                   gmsh.model.occ.getMass(dim, tag), descriptor['area_m2'], rel_tol=1e-6))]
                    if len(matches) > 1:
                        raise ValueError('ambiguous quarter source boundary')
                    (selected[matches[0]] if matches else walls).append(tag)
                if any(len(tags) != 1 for tags in selected.values()) or not walls:
                    raise ValueError('quarter source/interface face was not uniquely identified')
                layered = None
                if region != 'front' and design.rear_axial_mesh_size_m is not None:
                    from .rear_meshing import layered_rear_volume
                    source = next(s for s in geometry['sources'] if region == 'rear_' + s['id'])
                    name = next(iter(selected))
                    volumes, selected[name], walls, layered = layered_rear_volume(
                        gmsh, volumes, selected[name][0], source['motion_axis'],
                        design.rear_depth_m, design.rear_axial_mesh_size_m)
                gmsh.model.addPhysicalGroup(3, [volumes[0][1]], 1, name='air_' + region)
                groups = []
                for tag, (name, surfaces) in enumerate(selected.items(), start=10):
                    gmsh.model.addPhysicalGroup(2, surfaces, tag, name=name)
                    groups.append({'name': name, 'tag': tag, 'role': boundaries[name]['role']})
                gmsh.model.addPhysicalGroup(2, walls, 99, name='rigid_walls')
                groups.append({'name': 'rigid_walls', 'tag': 99, 'role': 'rigid_wall'})
                gmsh.option.setNumber('Mesh.MeshSizeMin', report['size_policy']['minimum_m'])
                gmsh.option.setNumber('Mesh.MeshSizeMax', design.mesh_size_m)
                gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', CURVATURE_ELEMENTS)
                gmsh.option.setNumber('Mesh.ElementOrder', 1)
                gmsh.option.setNumber('Mesh.MshFileVersion', 4.1)
                gmsh.option.setNumber('Mesh.Binary', 0)
                if layered is not None:
                    from .rear_meshing import check_layered_workload
                    check_layered_workload(gmsh, layered, design.maximum_tetrahedra)
                gmsh.model.mesh.generate(3)
                tets, _ = gmsh.model.mesh.getElementsByType(4)
                if not len(tets) or len(tets) > design.maximum_tetrahedra:
                    raise ValueError('quarter tetrahedral count is empty or exceeds mesh budget')
                qualities = gmsh.model.mesh.getElementQualities(tets)
                if min(qualities) <= 0:
                    raise ValueError('quarter mesh contains inverted or degenerate tetrahedra')
                path = directory / f'{region}.msh'
                gmsh.write(str(path))
                areas = source_area_checks(path, {name: math.sqrt(value.get('projected_area_m2', value['area_m2']) / math.pi)
                                                  for name, value in boundaries.items()},
                    axes={name: value['motion_axis'] for name, value in boundaries.items() if value.get('curved')},
                    surface_areas={name: value['area_m2'] for name, value in boundaries.items() if value.get('curved')})
                report['regions'].append({'id': region, 'estimated_tetrahedra': estimate,
                    'source_area_checks': areas, 'path': path.relative_to(output).as_posix(),
                    'sha256': sha256(path), 'volume_m3': volume, 'tetrahedra': len(tets),
                    'minimum_quality': float(min(qualities)), 'boundaries': groups})
                if layered is not None:
                    report['regions'][-1]['layered_rear_mesh'] = layered
            finally:
                gmsh.finalize()
        report['status'] = 'complete'
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _write_json(directory / 'mesh.json', report)
    return report
