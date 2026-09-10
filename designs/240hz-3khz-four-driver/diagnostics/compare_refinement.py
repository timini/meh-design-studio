"""Evaluate the predeclared two-level screen without changing its acceptance limits."""
from pathlib import Path
import hashlib,json,math
root=Path(__file__).resolve().parent
paths=[root/'refinement-plan.json',root/'sweep-summary.json',root/'transfer-10mm.json',root/'mesh-10mm.json']
plan,coarse,fine,mesh=[json.loads(p.read_text()) for p in paths]
if fine['status']!='complete' or mesh['status']!='complete':raise ValueError('incomplete refinement')
if fine['mesh_sha256']!=mesh['files'][0]['sha256']:raise ValueError('fine mesh identity mismatch')
first=json.loads((root.parent/'analysis-preparation/transfer-first.json').read_text())
for k in ('generator_sha256','source','termination','phasor'):
 if first[k]!=fine[k]:raise ValueError('incompatible refinement model '+k)
by_frequency={s['frequency_hz']:s for s in coarse['samples']}
# The original plan explicitly makes its rounded list descriptive only and
# selects the three retained samples nearest 1.6 kHz, plus the 3 kHz endpoint.
planned=sorted(sorted(by_frequency,key=lambda f:abs(f-1600.))[:3]+[3000.])
actual=[s['frequency_hz'] for s in fine['samples']]
if len(planned)!=4 or len(set(planned))!=4 or sorted(actual)!=planned:
 raise ValueError('refinement must contain all four exact frequencies selected by the original plan')
rows=[]
for sample in fine['samples']:
 a=complex(*by_frequency[sample['frequency_hz']]['mouth_transfer_pa_s_m3'])
 b=complex(*sample['mouth_transfer_pa_s_m3'])
 magnitude=abs(20*math.log10(abs(b)/abs(a)))
 error=abs(b-a)/abs(a)
 rows.append({'frequency_hz':sample['frequency_hz'],'magnitude_difference_db':magnitude,
              'relative_complex_difference':error,'passed':magnitude<=plan['maximum_magnitude_difference_db'] and error<=plan['maximum_relative_complex_difference']})
report={'status':'complete','screen_passed':all(r['passed'] for r in rows),'qualified':False,
        'resolved_plan_frequencies_hz':planned,
        'limits':{k:plan[k] for k in ['maximum_magnitude_difference_db','maximum_relative_complex_difference']},
        'source_files':[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
        'samples':rows,'interpretation':'Two-level sensitivity screen only. Failure prevents a mesh-stability claim; a passed screen would not establish physical accuracy.'}
(root/'refinement-comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
print(json.dumps(report,indent=2))
