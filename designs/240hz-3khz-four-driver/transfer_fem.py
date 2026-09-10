"""Prescribed-flow front-domain FEM with a plane-wave mouth termination.

This diagnostic omits exterior radiation and actual driver electromechanics.
Phasors use exp(+i omega t), inward source volume flow and RMS amplitudes.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import meshio
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve


def assemble(mesh):
    points = mesh.points
    tet = mesh.cells_dict['tetra']
    if not 0 < len(tet) <= 2_000_000 or not np.all(np.isfinite(points)):
        raise ValueError('invalid or oversized volume mesh')
    vertices = points[tet]
    affine = np.concatenate((np.ones((*vertices.shape[:2],1)),vertices),axis=2)
    determinant = np.linalg.det(affine)
    if not np.all(determinant > 0):
        raise ValueError('inverted or degenerate tetrahedra')
    volume = determinant/6
    gradients = np.linalg.inv(affine)[:,1:,:]
    stiffness = volume[:,None,None]*np.einsum('tki,tkj->tij',gradients,gradients)
    mass = volume[:,None,None]*(np.ones((4,4))+np.eye(4))/20
    rows = np.repeat(tet,4,axis=1).ravel()
    cols = np.tile(tet,(1,4)).ravel()
    shape = (len(points),len(points))
    K = coo_matrix((stiffness.ravel(),(rows,cols)),shape=shape).tocsc()
    M = coo_matrix((mass.ravel(),(rows,cols)),shape=shape).tocsc()
    boundaries = {}
    for name,(tag,dimension) in mesh.field_data.items():
        if dimension != 2: continue
        faces = np.concatenate([cell.data[np.asarray(tags)==tag] for cell,tags in
            zip(mesh.cells,mesh.cell_data['gmsh:physical']) if cell.type=='triangle'])
        xyz = points[faces]
        area = np.linalg.norm(np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0]),axis=1)/2
        weights = np.bincount(faces.ravel(),weights=np.repeat(area/3,3),minlength=len(points))
        bmass = area[:,None,None]*(np.ones((3,3))+np.eye(3))/12
        B = coo_matrix((bmass.ravel(),(np.repeat(faces,3,axis=1).ravel(),np.tile(faces,(1,3)).ravel())),shape=shape).tocsc()
        boundaries[name] = (weights,B)
    return K,M,boundaries


def response(operators, frequency, flows, mouth='mouth', rho=1.21, sound_speed=343.):
    K,M,boundaries = operators
    if not math.isfinite(frequency) or frequency <= 0: raise ValueError('positive frequency required')
    omega = 2*math.pi*frequency; k=omega/sound_speed
    forcing = np.zeros(K.shape[0],dtype=complex)
    for name,flow in flows.items():
        weights,_ = boundaries[name]
        forcing += 1j*omega*rho*flow*weights/weights.sum()
    matrix = K-k*k*M+1j*k*boundaries[mouth][1]
    pressure = spsolve(matrix,forcing)
    residual = float(np.linalg.norm(matrix@pressure-forcing)/max(np.linalg.norm(forcing),1e-30))
    if not np.all(np.isfinite(pressure)) or residual > 1e-7:
        raise ValueError('FEM linear solve failed its residual gate')
    means = {name:complex(weights@pressure/weights.sum()) for name,(weights,_) in boundaries.items()}
    return means,residual


def run(source,output,frequencies):
    manifest=source/'mesh.json';report=json.loads(manifest.read_text());path=source/'front.msh'
    if report['status']!='complete' or report['units']!='m':raise ValueError('requires complete metre mesh')
    expected=next(f['sha256'] for f in report['files'] if f['path']=='front.msh')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('mesh checksum mismatch')
    if not frequencies or any(not math.isfinite(f) or not 100<=f<=5000 for f in frequencies):raise ValueError('frequency range is 100–5000 Hz')
    output.mkdir(parents=True,exist_ok=False)
    result={'status':'running','qualified':False,'termination':'plane_wave_tube_impedance_rho_c',
            'source':'four equal prescribed inward flows, total 0.0001 m3/s RMS; throat rigid',
            'mesh_sha256':expected,'mesh_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'phasor':'exp(+i omega t)','samples':[],
            'limitations':['No exterior radiation or far-field SPL','No actual driver impedances, rear loads, cone profiles or crossover',
                           'Single mesh; not converged','Transfer diagnostic, not a 240–3000 Hz speaker qualification']}
    start=time.monotonic()
    try:
        mesh=meshio.read(path)
        expected_groups={b['name']:(b['tag'],2) for b in report['boundaries']};expected_groups['front_air']=(1,3)
        if {name:tuple(map(int,values)) for name,values in mesh.field_data.items()}!=expected_groups:raise ValueError('mesh boundary manifest mismatch')
        operators=assemble(mesh)
        for frequency in frequencies:
            means,residual=response(operators,frequency,{f'mid_{i}':.000025 for i in range(1,5)})
            result['samples'].append({'frequency_hz':frequency,'mouth_mean_pressure_pa':[means['mouth'].real,means['mouth'].imag],
                                      'mouth_transfer_pa_s_m3':[means['mouth'].real/.0001,means['mouth'].imag/.0001],
                                      'relative_residual':residual})
            (output/'transfer.json').write_text(json.dumps(result,indent=2,allow_nan=False))
        result['status']='complete'
    except BaseException as exc:
        result.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        result['elapsed_seconds']=time.monotonic()-start
        (output/'transfer.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frequencies',type=float,nargs='+',default=[240,500,1000,2000,3000]);args=parser.parse_args()
    print(json.dumps(run(args.source,args.output,args.frequencies),indent=2))
