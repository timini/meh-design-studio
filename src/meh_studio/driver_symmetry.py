"""Infer physical driver multiplicities from verified moving-surface meshes.

A cut through one driver completes its surface; an image of an uncut driver
adds a physical coil. These factors have different roles in electrical power.
"""
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path

import meshio
import numpy as np

from .boundary_lab import sha256


def _patch_cuts(points, triangles, axes):
    """Find symmetry cuts separately on every edge-connected surface patch."""
    if (not len(triangles) or triangles.ndim != 2 or triangles.shape[1] != 3
            or triangles.min() < 0 or triangles.max() >= len(points)):
        raise ValueError('moving surfaces require valid linear triangle connectivity')
    xyz = points[triangles]
    if not np.isfinite(xyz).all() or np.any(np.linalg.norm(
            np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0]), axis=1) == 0):
        raise ValueError('moving surfaces contain non-finite or degenerate triangles')
    edges = np.concatenate([triangles[:, pair] for pair in ([0, 1], [1, 2], [2, 0])])
    owners = np.tile(np.arange(len(triangles)), 3)
    keys, inverse, counts = np.unique(np.sort(edges, axis=1), axis=0,
                                      return_inverse=True, return_counts=True)
    if np.any(counts > 2):
        raise ValueError('moving surface has nonmanifold edges')
    order = np.argsort(inverse)
    starts = np.cumsum(counts) - counts
    parent = np.arange(len(triangles))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for start in starts[counts == 2]:
        a, b = owners[order[start:start + 2]]
        parent[find(a)] = find(b)
    roots = np.array([find(i) for i in range(len(triangles))])
    border = counts == 1
    border_roots = roots[owners[order[starts[border]]]]
    for patch in np.unique(roots):
        vertices = points[np.unique(triangles[roots == patch])]
        tolerance = max(1e-9, float(np.linalg.norm(np.ptp(vertices, axis=0))) * 1e-7)
        perimeter = points[keys[border][border_roots == patch]]
        cut = []
        for axis in axes:
            coordinate = vertices[:, axis]
            if coordinate.min() < -tolerance:
                raise ValueError('moving surface extends outside the positive symmetry domain')
            if np.max(np.abs(coordinate)) <= tolerance:
                raise ValueError('moving surface wholly on a symmetry plane has ambiguous multiplicity')
            if len(perimeter) and np.any(np.max(np.abs(perimeter[:, :, axis]), axis=1) <= tolerance):
                cut.append(axis)
        yield tuple(cut)


def driver_symmetry_from_meshes(project, manifest):
    """Bind native orbit/completion metadata to the hashed source geometry."""
    mode = project.get('symmetry', 'off')
    if mode not in ('off', 'x', 'xy'):
        raise ValueError('electrical validation requires off, x or xy symmetry')
    axes = {'off': (), 'x': (0,), 'xy': (0, 1)}[mode]
    system = project['physical_system']
    if not axes:
        return {c['id']: {'physical_driver_orbit_count': 1, 'surface_completion_factor': 1,
                          'fractional_symmetry_axes': []} for c in system['components']}
    boundaries = {b['id']: b for b in system['boundaries']}
    resources = {m['id']: m for m in system['meshes']}
    evidence = {m['id']: m for m in manifest['meshes']}
    cache, result = {}, {}
    for component in system['components']:
        selected = component['boundary_ids']
        if not selected or len(set(selected)) != len(selected):
            raise ValueError('each symmetric driver requires distinct moving boundaries')
        groups = defaultdict(list)
        for bid in selected:
            boundary = boundaries[bid]
            if boundary['kind'] != 'moving' or boundary['group'].get('dimension', 2) != 2:
                raise ValueError('driver multiplicity requires moving surface groups')
            groups[boundary['group']['mesh_id']].append(boundary['group'])
        cuts = set()
        for mid, selections in groups.items():
            if mid not in cache:
                path = Path(evidence[mid]['file'])
                if sha256(path) != evidence[mid]['sha256']:
                    raise ValueError('moving-surface mesh identity mismatch')
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    mesh = meshio.read(path)
                if sha256(path) != evidence[mid]['sha256']:
                    raise ValueError('moving-surface mesh changed during inspection')
                resource = resources[mid]
                points = mesh.points * resource.get('scale_to_m', 1.) + np.array(
                    resource.get('translation_m', [0., 0., 0.]))
                cache[mid] = mesh, points
            mesh, points = cache[mid]
            tags = set()
            for group in selections:
                tag = group.get('tag')
                if group.get('name') is not None:
                    field = np.asarray(mesh.field_data.get(group['name'], []))
                    if field.shape != (2,) or field.dtype.kind not in 'iu' or field[1] != 2:
                        raise ValueError('moving-surface name must identify a physical surface')
                    if tag is not None and tag != int(field[0]):
                        raise ValueError('moving-surface name and tag disagree')
                    tag = int(field[0])
                if type(tag) is not int or tag <= 0:
                    raise ValueError('moving surface requires a positive physical tag')
                tags.add(tag)
            physical = mesh.cell_data.get('gmsh:physical', [])
            if len(physical) != len(mesh.cells):
                raise ValueError('moving-surface physical tags are incomplete')
            triangles, used = [], set()
            for block, values in zip(mesh.cells, physical, strict=True):
                if np.asarray(values).shape != (len(block.data),):
                    raise ValueError('moving-surface tags do not match connectivity')
                mask = np.isin(values, list(tags))
                if block.dim != 2 or not mask.any():
                    continue
                if block.type != 'triangle':
                    raise ValueError('symmetry inference requires linear moving-surface triangles')
                triangles.append(block.data[mask])
                used.update(map(int, np.asarray(values)[mask]))
            if used != tags:
                raise ValueError('a selected moving-surface group has no triangles')
            cuts.update(_patch_cuts(points, np.vstack(triangles), axes))
        if len(cuts) != 1:
            raise ValueError('disconnected driver patches have inconsistent symmetry cuts')
        cut = next(iter(cuts))
        completion = 2 ** len(cut)
        result[component['id']] = {'physical_driver_orbit_count': 2 ** len(axes) // completion,
                                    'surface_completion_factor': completion,
                                    'fractional_symmetry_axes': ['xy'[i] for i in cut]}
    return result
