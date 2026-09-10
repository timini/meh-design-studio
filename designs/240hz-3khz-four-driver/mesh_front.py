"""Mesh the R1 front domain with named ports; no acoustic solution is implied."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from meh_studio.geometry import source_area_checks


def mesh_front(source: Path, output: Path, size_m: float = .015):
    import gmsh
    import meshio
    import numpy as np

    if not math.isfinite(size_m) or not .005 <= size_m <= .025:
        raise ValueError('mesh size must be between 5 and 25 mm')
    if gmsh.isInitialized():
        raise ValueError('meshing requires an isolated Gmsh process')
    manifest = source/'front-domain.json'
    domain = json.loads(manifest.read_text())
    if domain['status'] != 'complete' or domain['units'] != 'mm':
        raise ValueError('requires a complete millimetre front-domain export')
    step = source/'front-air.step'
    expected = next(row['sha256'] for row in domain['files'] if row['path'] == step.name)
    if hashlib.sha256(step.read_bytes()).hexdigest() != expected:
        raise ValueError('front air CAD checksum mismatch')
    if {row['id'] for row in domain['interfaces']} != {'mouth','throat','mid_1','mid_2','mid_3','mid_4'} or len(domain['interfaces']) != 6:
        raise ValueError('requires exactly six R1 interfaces')
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'units': 'm', 'acoustic_validation': False,
              'accuracy': 'not_converged', 'maximum_mesh_size_m': size_m,
              'source_step_sha256': expected,
              'source_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    gmsh.initialize()
    try:
        # Volume-based estimate plus allowance for R1's curvature refinement.
        # This is a workload heuristic, not an upper bound on the mesher.
        estimate = 6*(domain['volume_mm3']/1e9)/size_m**3 + 250_000
        report['estimated_tetrahedra'] = estimate
        if estimate > 2_000_000:
            raise ValueError('estimated tetrahedral workload exceeds the mesh budget')
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
        gmsh.model.occ.importShapes(str(step.resolve()))
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise ValueError('front air must import as one volume')
        cad_volume = gmsh.model.occ.getMass(3, volumes[0][1])
        if not math.isclose(cad_volume, domain['volume_mm3']/1e9, rel_tol=1e-6):
            raise ValueError('CAD import volume/unit mismatch')
        surfaces = gmsh.model.getBoundary(volumes, oriented=False)
        used = set(); groups = []
        for tag, interface in enumerate(domain['interfaces'], 10):
            center = [v/1000 for v in interface['center_mm']]
            area = math.pi*(interface['radius_mm']/1000)**2
            matches = [s for dim,s in surfaces if gmsh.model.getType(dim,s) == 'Plane'
                       and math.dist(gmsh.model.occ.getCenterOfMass(dim,s), center) < 1e-7
                       and math.isclose(gmsh.model.occ.getMass(dim,s),area,rel_tol=1e-6)]
            if len(matches) != 1 or matches[0] in used:
                raise ValueError('missing or ambiguous interface '+interface['id'])
            used.add(matches[0])
            gmsh.model.addPhysicalGroup(2,matches,tag,name=interface['id'])
            groups.append({'name':interface['id'],'tag':tag,'outward_normal':interface['outward_normal']})
        walls = [s for _,s in surfaces if s not in used]
        if not walls:
            raise ValueError('no rigid wall surfaces')
        gmsh.model.addPhysicalGroup(2,walls,99,name='rigid_walls')
        groups.append({'name':'rigid_walls','tag':99,'role':'rigid_wall'})
        gmsh.model.addPhysicalGroup(3,[volumes[0][1]],1,name='front_air')
        gmsh.option.setNumber('Mesh.MeshSizeMin', min(size_m,.001))
        gmsh.option.setNumber('Mesh.MeshSizeMax', size_m)
        gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',48)
        gmsh.option.setNumber('Mesh.ElementOrder',1)
        gmsh.option.setNumber('Mesh.MshFileVersion',4.1)
        gmsh.model.mesh.generate(3)
        tetrahedra,_ = gmsh.model.mesh.getElementsByType(4)
        if not 0 < len(tetrahedra) <= 2_000_000:
            raise ValueError('tetrahedral count outside supported budget')
        quality = gmsh.model.mesh.getElementQualities(tetrahedra)
        if not np.all(np.isfinite(quality)) or min(quality) <= 0:
            raise ValueError('invalid tetrahedral quality')
        path = output/'front.msh'; gmsh.write(str(path))
        areas = source_area_checks(path,{i['id']:i['radius_mm']/1000 for i in domain['interfaces']})
        mesh = meshio.read(path); points = mesh.points[mesh.cells_dict['tetra']]
        signed = np.linalg.det(points[:,1:]-points[:,0,None,:])/6
        if not np.all(signed > 0):
            raise ValueError('saved mesh has inverted or degenerate tetrahedra')
        volume = float(signed.sum())
        if abs(volume/cad_volume-1) > .01:
            raise ValueError('saved mesh volume differs from CAD by more than one percent')
        report.update(status='complete',tetrahedra=len(tetrahedra),minimum_quality=float(min(quality)),
                      cad_volume_m3=cad_volume,mesh_volume_m3=volume,
                      relative_volume_error=abs(volume/cad_volume-1),source_area_checks=areas,boundaries=groups,
                      files=[{'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}],
                      limitations=['Single mesh resolution; no convergence claim','No source coupling, rear domains or FEM/BEM solve'])
    except BaseException as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        gmsh.finalize()
        (output/'mesh.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--size-m',type=float,default=.015)
    args=parser.parse_args()
    print(json.dumps(mesh_front(args.source,args.output,args.size_m),indent=2))
