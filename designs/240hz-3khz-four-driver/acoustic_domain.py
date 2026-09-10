"""Export the R1 front air domain with ideal planar mounting-plane interfaces.

This is geometry preparation, not a commercial-driver model or acoustic solution.
Run next to generate.py, with repository CAD dependencies installed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
from generate import build, cylinder, LENGTH, THROAT, MOUTH, PORT, FACE


def export_front_domain(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'units': 'mm', 'acoustic_validation': False}
    try:
        body, _, mounts = build()
        air = cq.Solid.makeCone(THROAT, MOUTH, LENGTH).fuse(
            cylinder(THROAT, 8, (0, 0, -8)))
        # Same port cut as R1, terminated at the nominal driver mounting plane.
        duct = cylinder(PORT, 46, (0, 0, -42)).fuse(
            cq.Solid.makeCone(PORT, 37.3, 8, cq.Vector(0, 0, 4)))
        interfaces = [
            {'id': 'throat', 'center_mm': [0, 0, -8], 'outward_normal': [0, 0, -1], 'radius_mm': THROAT},
            {'id': 'mouth', 'center_mm': [0, 0, LENGTH], 'outward_normal': [0, 0, 1], 'radius_mm': MOUTH},
        ]
        for mount in mounts:
            air = air.fuse(duct.moved(mount['plane'].location))
            interfaces.append({'id': mount['name'], 'center_mm': [
                o + FACE*n for o, n in zip(mount['origin_mm'], mount['normal'])],
                'outward_normal': mount['normal'], 'radius_mm': 37.3})
        air = air.clean()
        if not air.isValid() or len(air.Solids()) != 1:
            raise ValueError('front air must be one valid connected solid')
        overlap = air.intersect(body).Volume()
        if overlap > max(1e-4, air.Volume()*1e-10):
            raise ValueError(f'front air intersects printed material: {overlap} mm3')
        # Identify all six intended planar interfaces independently from the boolean build.
        for interface in interfaces:
            expected = math.pi*interface['radius_mm']**2
            matches = [face for face in air.Faces() if face.geomType() == 'PLANE'
                       and math.dist(face.Center().toTuple(), interface['center_mm']) < 1e-5
                       and math.isclose(face.Area(), expected, rel_tol=1e-7)]
            if len(matches) != 1:
                raise ValueError(f"missing or ambiguous interface: {interface['id']}")
            normal = matches[0].normalAt().toTuple()
            if sum(a*b for a, b in zip(normal, interface['outward_normal'])) < .999999:
                raise ValueError(f"reversed interface: {interface['id']}")
            interface['area_mm2'] = matches[0].Area()
        path = output/'front-air.step'
        cq.exporters.export(air, str(path))
        # Reimport the persisted CAD: volume and unit checks must survive the file boundary.
        imported = cq.importers.importStep(str(path)).val()
        if not math.isclose(imported.Volume(), air.Volume(), rel_tol=1e-7):
            raise ValueError('STEP round-trip volume mismatch')
        report.update(status='complete', volume_mm3=air.Volume(),
                      material_overlap_mm3=overlap, interfaces=interfaces,
                      files=[{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
                      generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      mechanical_generator_sha256=hashlib.sha256(Path(__file__).with_name('generate.py').read_bytes()).hexdigest(),
                      limitations=[
                          'Ideal planar interfaces at mounting planes; actual cone profile/front cavity not measured',
                          'Interface area is aperture area, not catalogue effective piston Sd',
                          'Rear chambers and driver impedances are not included in this front-domain export',
                          'No FEM/BEM solve, convergence, radiation or acoustic performance claim'])
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        (output/'front-domain.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    print(json.dumps(export_front_domain(parser.parse_args().output), indent=2))
