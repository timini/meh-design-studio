from pathlib import Path
import hashlib,io,json,zipfile
import numpy as np
root=Path(__file__).resolve().parent.parent
handles=[]
def reader(folder):
 report=json.loads((root/folder/'report.json').read_text());members={}
 for p in (root/folder).glob('*.zip'):
  digest=hashlib.sha256(p.read_bytes()).hexdigest()
  expected=next(x['sha256'] for x in report['archives'] if x['file']==p.name)
  assert digest==expected
  z=zipfile.ZipFile(p);handles.append(z)
  for n in z.namelist():assert n not in members;members[n]=z
 def read(n):
  b=members[n].read(n);assert hashlib.sha256(b).hexdigest()==report['archived_file_sha256'][n];return b
 return read
coarse=reader('annular-mid-entry');fine=reader('annular-mid-refinement')
def field(read,p,index):
 ds=json.loads(read(p+'domains.json'))['domains'];m=json.loads(read(p+f'frequencies/{index:06d}.json'));q={x['id']:x for x in m['quantities']}
 ids=q['mechanical:diaphragm-velocity']['metadata']['component_ids'];mid=[i for i,x in enumerate(ids) if x!='component:throat']
 with np.load(io.BytesIO(read(p+'domains.npz')),allow_pickle=False) as a:
  pts=np.vstack([a[next(d for d in ds if d['id']==f'observation:{plane}-polar')['coordinates']['points_m']] for plane in ('horizontal','vertical')])
 with np.load(io.BytesIO(read(p+f'frequencies/{index:06d}.npz')),allow_pickle=False) as a:
  field=np.concatenate([a[q[f'acoustic:pressure:{plane}-polar']['key']][mid].sum(axis=0) for plane in ('horizontal','vertical')])
 return pts,field,m['freq_hz'],ids
x,a,f,ids=field(coarse,'annular-entry-native/annular/evaluation/upstream/',2)
y,b,g,jds=field(fine,'annular-entry-refinement-resumed/refined/evaluation/upstream/',0)
assert f==g==4000 and ids==jds;np.testing.assert_array_equal(x,y)
rot=y[:,[1,0,2]].copy();rot[:,0]*=-1;dist=np.linalg.norm(rot[:,None]-y[None,:],axis=2);mapping=dist.argmin(axis=1);assert dist.min(axis=1).max()<1e-10
out={'frequency_hz':f,'common_mid_coarse_norm':float(np.linalg.norm(a)),'common_mid_refined_norm':float(np.linalg.norm(b)),'relative_complex_refinement_error':float(np.linalg.norm(b-a)/np.linalg.norm(a)),'refined_common_mid_rotation_error':float(np.linalg.norm(b-b[mapping])/np.linalg.norm(b)),'qualified':False,'scope':'Auxiliary equal-voltage shared-bank reanalysis; original failures and acceptance gates unchanged'}
Path(__file__).with_name('refinement-report.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
for z in handles:z.close()
