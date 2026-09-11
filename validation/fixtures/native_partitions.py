"""Run and verify independent frequency partitions of the frozen native benchmark."""
import argparse
import json
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import BoundaryLabRuntime, _read_json, _write_json, sha256, _termination_guard
from meh_studio.export_validation import validate_export
from meh_studio.optimisation import candidates, candidate_record, evaluate_candidate, relative_response, verified_assessment
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from validate_search_finalist import load_search, pressure, mesh_identity
from run_native_e2e import checked_source_revision, verify_source_revision, VALIDATION_PARTS

PARTS=VALIDATION_PARTS
LEVELS=('baseline','0','1','2')


def inputs(search,level,chunk):
    if level not in LEVELS or not 0<=chunk<PARTS:raise ValueError('unknown validation partition')
    controls,result,brief,base,winner,gain,frequencies,frozen,sizes=load_search(search)
    if brief.acoustic_objectives is not None:
        raise ValueError('fixed-gain partition benchmark does not support crossover searches; use sequential finalist validation')
    if level=='baseline':
        drivers=[DriverRevision.model_validate(d) for d in json.loads((search/'catalogue-snapshot.json').read_text())]
        winner=candidates(brief,base,drivers)[0];gain=1.;size=base.mesh_size_m
    else:size=sizes[int(level)]
    selected=tuple(float(f) for f in np.array_split(np.asarray(frequencies),PARTS)[chunk])
    if not selected:raise ValueError('empty validation partition')
    frozen=type(brief).model_validate(brief.model_dump()|{'side_gains':(gain,)})
    design=HornGeometry.model_validate(winner['design'].model_dump()|{'mesh_size_m':size})
    return controls,winner,frozen,size,selected,candidate_record(winner|{'design':design})


def file_hashes(root):
    return {p.relative_to(root).as_posix():sha256(p) for p in sorted(root.rglob('*')) if p.is_file() and p.name!='partition.json'}


def run_partition(search,root,runtime,level,chunk):
    controls,candidate,brief,size,frequencies,expected=inputs(search,level,chunk)
    repo=Path(__file__).resolve().parents[2];revision=checked_source_revision(repo)
    if revision!=_read_json(search.parent/'experiment.json')['source_commit']:raise ValueError('partition source differs from search')
    report={'status':'running','qualified':False,'physical_validation':False,'level':level,'chunk':chunk,
            'source_commit':revision,'input_sha256':controls,'frequencies_hz':frequencies,'side_gain':brief.side_gains[0],'mesh_size_m':size,'runtime':runtime.verify(),'runner_sha256':sha256(Path(__file__))}
    if report['runtime']!=_read_json(search/'search.json')['runtime']:raise ValueError('partition runtime differs from search')
    with _termination_guard(report) as activate:
        root.mkdir(parents=True,exist_ok=False)
        try:
            activate();_write_json(root/'partition.json',report)
            evaluate_candidate(candidate,root/'candidate',runtime,brief,mesh_size=size,frequencies=frequencies,timeout_s=7200)
            if _read_json(root/'candidate/candidate.json')!=expected:raise ValueError('partition candidate differs')
            if runtime.verify()!=report['runtime'] or load_search(search)[0]!=controls or sha256(Path(__file__))!=report['runner_sha256']:raise ValueError('partition inputs or runtime changed')
            verify_source_revision(repo,revision)
            report.update(status='complete',artifact_sha256=file_hashes(root))
        except BaseException as exc:
            report.update(status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc));raise
        finally:_write_json(root/'partition.json',report)


def read_partition(search,root,level,chunk):
    controls,candidate,brief,size,frequencies,expected=inputs(search,level,chunk)
    digest=sha256(root/'partition.json');record=_read_json(root/'partition.json')
    if record.get('status')!='complete' or record.get('runner_sha256')!=sha256(Path(__file__)) or record.get('artifact_sha256')!=file_hashes(root):raise ValueError('partition artifacts differ or are incomplete')
    required={'source_commit':_read_json(search.parent/'experiment.json')['source_commit'],'level':level,'chunk':chunk,'input_sha256':controls,'frequencies_hz':list(frequencies),'side_gain':brief.side_gains[0],'mesh_size_m':size}
    if any(record.get(k)!=v for k,v in required.items()):raise ValueError('partition does not match frozen inputs')
    path=root/'candidate';project=path/'system/project.blab.json';evaluation=path/'evaluation'
    if _read_json(path/'candidate.json')!=expected:raise ValueError('recorded partition candidate differs')
    assessment=verified_assessment(project,evaluation)
    evaluated=_read_json(evaluation/'evaluation.json')
    if _read_json(path/'geometry/geometry.json')['design']!=expected['design']:raise ValueError('generated geometry differs from frozen candidate')
    if _read_json(path/'system/compilation.json')['runtime']!=record['runtime']:raise ValueError('compilation runtime differs')
    if evaluated['runtime']!=record['runtime']:raise ValueError('partition evaluation runtime differs')
    request=_read_json(evaluation/'request.json')
    if request['frequencies_hz']!=list(frequencies):raise ValueError('partition evaluation frequencies differ')
    values=pressure(project,evaluation,brief.side_gains[0])
    if len(values)!=len(frequencies):raise ValueError('partition pressure length differs')
    mesh=mesh_identity(path)
    manifest=_read_json(evaluation/'upstream/manifest.json')
    inventory=sorted((m['id'],m['purpose'],m['sha256']) for m in manifest['meshes'])
    row={'level':level,'chunk':chunk,'frequencies_hz':list(frequencies),'pressure_real':values.real.tolist(),'pressure_imag':values.imag.tolist(),
         'runtime':record['runtime'],'mesh_identity':mesh,'mesh_inventory':inventory,'electrical_validation':assessment['checks'],
         'export_checks':validate_export(path/'geometry'),'partition_sha256':digest}
    if sha256(root/'partition.json')!=digest or file_hashes(root)!=record['artifact_sha256']:raise ValueError('partition changed while reading')
    return row


def combine(rows,frequencies,runtime):
    """Combine raw pressure only after checking complete coverage and fixed meshes."""
    if len(rows)!=len(LEVELS)*PARTS:raise ValueError('all validation partitions are required')
    responses={};records={};seen=set()
    for row in rows:
        key=(row['level'],row['chunk'])
        if key in seen or row['level'] not in LEVELS or row['chunk'] not in range(PARTS):raise ValueError('duplicate or unexpected partition')
        seen.add(key)
        expected=np.array_split(np.asarray(frequencies),PARTS)[row['chunk']].tolist()
        if len(row['pressure_real'])!=len(expected) or len(row['pressure_imag'])!=len(expected):raise ValueError('partition pressure length differs')
        if row['frequencies_hz']!=expected or row['runtime']!=runtime:raise ValueError('partition frequencies or runtime differ')
    for level in LEVELS:
        group=sorted((r for r in rows if r['level']==level),key=lambda r:r['chunk'])
        if len(group)!=PARTS:raise ValueError('missing level partition')
        if any(r['mesh_inventory']!=group[0]['mesh_inventory'] or r['mesh_identity']!=group[0]['mesh_identity'] for r in group):
            raise ValueError('mesh changed between frequency partitions')
        values=np.concatenate([np.asarray(r['pressure_real'])+1j*np.asarray(r['pressure_imag']) for r in group])
        if len(values)!=len(frequencies):raise ValueError('combined pressure length differs')
        relative=relative_response(values);responses[level]=values
        records[level]={'score':{'ripple_db':float(np.ptp(relative)),'relative_response_db':relative.tolist()},
                        'mesh_identity':group[0]['mesh_identity'],'export_checks':[r['export_checks'] for r in group],
                        'electrical_consistency_passed':all(r['electrical_validation']['passed'] for r in group),
                        'pressure_real':values.real.tolist(),'pressure_imag':values.imag.tolist()}
    reference=records['0']['mesh_identity']
    for level in ('1','2'):
        if any(records[level]['mesh_identity'][k]!=reference[k] for k in ('cad_geometry_sha256','exterior_mesh_size_m','compiler_runtime')):
            raise ValueError('CAD or meshing runtime changed across refinement levels')
    changes=[]
    for before,after in (('0','1'),('1','2')):
        a,b=responses[before],responses[after]
        changes.append({'maximum_magnitude_change_db':float(abs(20*np.log10(abs(b)/abs(a))).max()),
                        'maximum_phase_change_deg':float(abs(np.angle(b*a.conj(),deg=True)).max())})
    return records,changes


def assemble(search,parts,output,runtime):
    controls,result,brief,base,winner,gain,frequencies,frozen,sizes=load_search(search)
    original=_read_json(search.parent/'experiment.json')
    repo=Path(__file__).resolve().parents[2];revision=checked_source_revision(repo)
    if revision!=original['source_commit']:raise ValueError('assembly source differs from search')
    if original['status']!='search_complete':raise ValueError('a completed reference/search stage is required')
    for name,digest in original['stage_sha256'].items():
        if sha256(search.parent/name)!=digest:raise ValueError('reference/search evidence changed')
    identity=runtime.verify()
    if identity!=original['runtime'] or identity!=result['runtime']:raise ValueError('assembly runtime differs from native search')
    report=original|{'status':'running','stage':'assemble_partitions','partition_count':len(LEVELS)*PARTS,'assembly_runner_sha256':sha256(Path(__file__))}
    with _termination_guard(report) as activate:
        output.mkdir(parents=True,exist_ok=False)
        try:
            activate();_write_json(output/'experiment.json',report)
            rows=[read_partition(search,parts/f'{level}-{chunk}',level,chunk) for level in LEVELS for chunk in range(PARTS)]
            records,changes=combine(rows,frequencies,identity)
            passed=all(c['maximum_magnitude_change_db']<=.5 and c['maximum_phase_change_deg']<=5 for c in changes)
            levels=[records[str(i)]|{'mesh_size_m':sizes[i]} for i in range(3)]
            electrical=all(row['electrical_consistency_passed'] for row in levels)
            validation={'status':'complete' if passed else 'failed','qualified':False,'physical_validation':False,
                'frequencies_hz':frequencies,'fixed_side_gain':gain,'input_sha256':controls,'runtime':identity,
                'levels':levels,'successive_changes':changes,'refinement_passed':passed,'electrical_consistency_passed':electrical,
                'magnitude_change_limit_db':.5,'phase_change_limit_deg':5.,
                'partitions':rows,'limitations':['Finite frequency grid; no continuous-band guarantee','Interior and conforming mouth refined; rigid exterior target fixed','Independent frequency solves use identical mesh hashes within each level','Synthetic drivers; no physical or print qualification']}
            (output/'finalist-validation').mkdir();(output/'baseline-validation').mkdir()
            _write_json(output/'finalist-validation/validation.json',validation)
            _write_json(output/'baseline-validation/score.json',records['baseline']['score'])
            baseline=_read_json(search.parent/'baseline-search-grid.json')
            heldout=[i for i,f in enumerate(frequencies) if f not in brief.frequencies_hz]
            values={'winner_index':result['winner_index'],'baseline_search_ripple_db':baseline['ripple_db'],
                'winner_search_ripple_db':result['winner']['ripple_db'],'baseline_validation_ripple_db':records['baseline']['score']['ripple_db'],
                'winner_validation_coarse_ripple_db':levels[0]['score']['ripple_db'],
                'baseline_heldout_ripple_db':float(np.ptp(np.asarray(records['baseline']['score']['relative_response_db'])[heldout])),
                'winner_heldout_ripple_db':float(np.ptp(np.asarray(levels[0]['score']['relative_response_db'])[heldout])),
                'refinement_passed':passed,'coupled_electrical_consistency_passed':electrical}
            report['results']=values
            if not passed:raise ValueError('finalist mesh stability gate failed')
            if values['baseline_heldout_ripple_db']-values['winner_heldout_ripple_db']<1:raise ValueError('held-out improvement is below 1 dB')
            if load_search(search)[0]!=controls or runtime.verify()!=identity or sha256(Path(__file__))!=report['assembly_runner_sha256']:raise ValueError('assembly inputs or runtime changed')
            for row in rows:
                part=parts/f"{row['level']}-{row['chunk']}"
                if sha256(part/'partition.json')!=row['partition_sha256'] or file_hashes(part)!=_read_json(part/'partition.json')['artifact_sha256']:
                    raise ValueError('partition changed during assembly')
            verify_source_revision(repo,revision)
            report.update(status='complete',stage='complete')
        except BaseException as exc:
            report.update(status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc));raise
        finally:_write_json(output/'experiment.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['run','assemble'])
    parser.add_argument('search',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--parts',type=Path);parser.add_argument('--level',choices=LEVELS);parser.add_argument('--chunk',type=int)
    for name in ('checkout','python','julia'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--backend',choices=['beat_cpu','beat_cuda','beat_rocm','coupled_reference'],help='must match the search; defaults to its backend')
    parser.add_argument('--julia-threads',type=int,help='must match the search; defaults to its thread setting')
    args=parser.parse_args()
    original=_read_json(args.search/'search.json')['runtime']
    threads=args.julia_threads if args.julia_threads is not None else original.get('julia_threads','upstream_default')
    if threads=='upstream_default':threads=None
    runtime=BoundaryLabRuntime(args.checkout,args.python,args.julia,args.backend or original['backend'],julia_threads=threads)
    if args.mode=='run':run_partition(args.search,args.output,runtime,args.level,args.chunk)
    else:assemble(args.search,args.parts,args.output,runtime)


if __name__=='__main__':main()
