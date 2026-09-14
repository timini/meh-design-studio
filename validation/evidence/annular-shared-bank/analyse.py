from pathlib import Path
import hashlib,io,json,zipfile
import numpy as np
root=Path(__file__).resolve().parent.parent/'annular-mid-entry'
report=json.loads((root/'report.json').read_text()); archive=root/'evidence.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='35437cae99229d23b789383e3105bfd32200d9a5991a4dad0c4be0d5b7bb8d5f'
rows=[]
with zipfile.ZipFile(archive) as z:
 def read(n):
  data=z.read(n);assert hashlib.sha256(data).hexdigest()==report['archived_file_sha256'][n];return data
 for case in ('plain','annular'):
  p=f'annular-entry-native/{case}/evaluation/upstream/'
  domains=json.loads(read(p+'domains.json'))['domains']
  with np.load(io.BytesIO(read(p+'domains.npz')),allow_pickle=False) as a:
   pts=np.vstack([a[next(d for d in domains if d['id']==f'observation:{plane}-polar')['coordinates']['points_m']] for plane in ('horizontal','vertical')])
  rot=pts[:,[1,0,2]].copy();rot[:,0]*=-1
  dist=np.linalg.norm(rot[:,None]-pts[None,:],axis=2);mapping=dist.argmin(axis=1);assert dist.min(axis=1).max()<1e-10
  for i in range(3):
   meta=json.loads(read(p+f'frequencies/{i:06d}.json'));q={v['id']:v for v in meta['quantities']}
   ids=q['mechanical:diaphragm-velocity']['metadata']['component_ids']; mids=[j for j,k in enumerate(ids) if k!='component:throat']
   with np.load(io.BytesIO(read(p+f'frequencies/{i:06d}.npz')),allow_pickle=False) as a:
    pressure=np.concatenate([a[q[f'acoustic:pressure:{plane}-polar']['key']] for plane in ('horizontal','vertical')],axis=1)
   common=pressure[mids].sum(axis=0)
   norm=float(np.linalg.norm(common));err=float(np.linalg.norm(common-common[mapping])/norm)
   rows.append({'case':case,'frequency_hz':meta['freq_hz'],'common_mid_pressure_norm':norm,'common_mid_rotation_relative_error':err,'within_original_2pct_screen':err<=.02})
out={'scope':'Derived equal-voltage shared mid-bank diagnostic; no new solver execution or qualification','source_commit':report['application_source_commit'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'rows':rows,'qualified':False,'limitations':['Original per-basis rotational and refinement failures remain unchanged.','No changed acceptance gate; this auxiliary screen cannot qualify a candidate.']}
Path(__file__).with_name('report.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows))
