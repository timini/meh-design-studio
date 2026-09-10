"""Retain the third-level result at the predeclared single frequency."""
from pathlib import Path
import hashlib,json,math
root=Path(__file__).resolve().parent
names=['third-mesh-plan.json','transfer-10mm.json','transfer-7p5mm.json','mesh-10mm.json','mesh-7p5mm.json']
plan,coarse,fine,cm,fm=[json.loads((root/n).read_text()) for n in names]
for run,mesh in ((coarse,cm),(fine,fm)):
 if run['status']!='complete' or mesh['status']!='complete':raise ValueError('incomplete source evidence')
 if run['mesh_sha256']!=mesh['files'][0]['sha256']:raise ValueError('mesh identity mismatch')
for k in ('generator_sha256','source','termination','phasor'):
 if coarse[k]!=fine[k]:raise ValueError('different source/solver model')
if [s['frequency_hz'] for s in fine['samples']]!=plan['frequencies_hz']:raise ValueError('frequency plan mismatch')
a=next(s for s in coarse['samples'] if s['frequency_hz']==3000)
b=fine['samples'][0];a=complex(*a['mouth_transfer_pa_s_m3']);b=complex(*b['mouth_transfer_pa_s_m3'])
mag=abs(20*math.log10(abs(b)/abs(a)));error=abs(b-a)/abs(a)
r={'status':'complete','screen_passed':mag<=plan['maximum_magnitude_difference_db'] and error<=plan['maximum_relative_complex_difference'],
   'qualified':False,'frequency_hz':3000,'magnitude_difference_db':mag,'relative_complex_difference':error,
   'limits':{k:plan[k] for k in ('maximum_magnitude_difference_db','maximum_relative_complex_difference')},
   'source_files':[{'path':n,'sha256':hashlib.sha256((root/n).read_bytes()).hexdigest()} for n in names],
   'interpretation':'Original 10% complex gate retained. Magnitude stability is insufficient to establish phase stability; no band convergence or physical accuracy claim.'}
(root/'third-mesh-comparison.json').write_text(json.dumps(r,indent=2,allow_nan=False))
print(json.dumps(r,indent=2))
