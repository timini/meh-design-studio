"""Combine original endpoints with the additional interior sweep without rerunning."""
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
paths=[root.parent/'analysis-preparation/transfer-first.json',root/'transfer-dense-interior.json']
a,b=[json.loads(p.read_text()) for p in paths]
if a['status']!='complete' or b['status']!='complete':raise ValueError('incomplete source run')
for key in ('mesh_sha256','generator_sha256','source','termination','phasor'):
 if a[key]!=b[key]:raise ValueError('incompatible source runs: '+key)
rows=sorted([x for x in a['samples'] if x['frequency_hz'] in (240,3000)]+b['samples'],key=lambda x:x['frequency_hz'])
f=np.array([r['frequency_hz'] for r in rows]);v=np.array([abs(complex(*r['mouth_transfer_pa_s_m3'])) for r in rows])
if len(f)!=17 or len(set(f))!=17 or not np.all(v>0):raise ValueError('invalid sweep samples')
db=20*np.log10(v/v[0])
report={'status':'complete','qualified':False,'source_reports':[{'path':str(p.relative_to(root.parent)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
 'sampled_magnitude_span_db':float(np.ptp(db)),'sampled_minimum_hz':float(f[db.argmin()]),
 'quantity':'Magnitude of complex mouth-area mean pressure per prescribed total flow, relative to 240 Hz',
 'limitations':['Not far-field SPL or speaker frequency response','Local rho*c termination, rigid throat, no driver model',
                'Single mesh; sparse frequency sampling may miss narrower features'], 'samples':rows}
(root/'sweep-summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
fig,ax=plt.subplots(figsize=(9,5));ax.semilogx(f,db,'o-',color='#177d91')
ax.set(xlabel='Frequency (Hz)',ylabel='Mouth-mean transfer magnitude relative to 240 Hz (dB)',title='R1 prescribed-flow diagnostic • 15 mm mesh')
ax.grid(True,which='both',alpha=.25);ax.set_xticks([240,500,1000,1600,3000],labels=['240','500','1000','1600','3000'])
fig.text(.5,.025,'Approximate mouth termination • no actual driver model • not a far-field response',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.06,1,1));fig.savefig(root/'sweep.png',dpi=150)
