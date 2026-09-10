"""Independent closed-form comparison with no gain, delay or phase fitting."""
from pathlib import Path
import json,argparse
import numpy as np
from meh_studio.boundary_lab import SolveRequest,inspect_result,sha256,_contained
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('fixture',type=Path);parser.add_argument('evaluation',type=Path);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
project=(args.fixture/'project.blab.json').absolute();evaluation=args.evaluation.absolute();reference=project.parent/'reference.json';root=evaluation/'upstream'
controls={str(p):sha256(p) for p in (project,reference,evaluation/'evaluation.json',evaluation/'request.json',evaluation/'preflight.json',Path(__file__))}
r=json.loads(reference.read_text());p=json.loads(project.read_text());saved=json.loads((evaluation/'evaluation.json').read_text());request=SolveRequest.model_validate_json((evaluation/'request.json').read_text())
if saved['status']!='complete' or saved['project_sha256']!=sha256(project) or saved['request_sha256']!=sha256(evaluation/'request.json') or saved['preflight_sha256']!=sha256(evaluation/'preflight.json'):raise ValueError('evaluation controls mismatch')
if p['physical_system']['metadata']['analytic_reference_sha256']!=sha256(reference):raise ValueError('reference not bound to project')
result=inspect_result(root,request,saved['runtime']['backend'],project_path=project)
if result!=saved['result']:raise ValueError('native result identity mismatch')
manifest=json.loads((root/'manifest.json').read_text());domains=json.loads(_contained(root,manifest['domains_metadata_file']).read_text())['domains']
if manifest['phasor_convention']!=r['phasor_convention'] or manifest['frequencies_hz']!=r['frequencies_hz'] or manifest['excitation_port_ids']!=['excitation:sphere']:raise ValueError('comparison basis mismatch')
with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as data:
 coordinates={d['id']:data[d['coordinates']['points_m']] for d in domains if d['kind']=='polar_observation'}
rows=[]
for item in manifest['results']:
 f=item['freq_hz'];k=2*np.pi*f/r['sound_speed_m_s'];a=r['radius_m'];rho=r['density_kg_m3'];c=r['sound_speed_m_s'];v=r['velocity_coefficient_m_per_s']
 meta=json.loads((root/item['metadata_file']).read_text());values=[]
 with np.load(root/item['arrays_file'],allow_pickle=False) as data:
  for q in meta['quantities']:
   if q['quantity']!='exterior_pressure':continue
   if q['axes']!=['excitation','observation']:raise ValueError('unsupported axes')
   distance=np.linalg.norm(coordinates[q['target_id']],axis=1)
   if np.any(distance<=a):raise ValueError('observation inside sphere')
   exact=rho*c*(-1j*k*a)/(1-1j*k*a)*(a/distance)*np.exp(1j*k*(distance-a))*v
   calculated=data[q['key']][0]
   values.append({'quantity_id':q['id'],'maximum_relative_complex_error':float(np.max(abs(calculated-exact)/abs(exact))),
    'maximum_magnitude_error_db':float(np.max(abs(20*np.log10(abs(calculated)/abs(exact))))),
    'maximum_phase_error_deg':float(np.max(abs(np.angle(calculated*exact.conj(),deg=True)))),'sample_count':len(distance)})
 if len(values)!=2:raise ValueError('expected both polar cuts')
 rows.append({'frequency_hz':f,'polars':values,'passed':all(x['maximum_relative_complex_error']<=r['maximum_relative_complex_error'] for x in values)})
if controls!={str(Path(p)):sha256(Path(p)) for p in controls} or inspect_result(root,request,saved['runtime']['backend'],project_path=project)!=result:raise ValueError('evidence changed during comparison')
report={'schema_version':1,'evidence':'analytic_exterior_pulsating_sphere','passed':all(row['passed'] for row in rows),'maximum_relative_complex_error_limit':r['maximum_relative_complex_error'],'control_sha256':controls,'result_inspection':result,'rows':rows,'physical_validation':False,'limitations':['Prescribed unit normal-velocity reference; not a voltage-driven commercial source','Independent analytical exterior test, not a coupled horn validation','Finite mesh and four frequencies; no gain/phase/delay fitting','No RMS or loudspeaker SPL qualification']}
with args.output.open('x') as stream:stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'passed':report['passed'],'rows':rows},indent=2))
