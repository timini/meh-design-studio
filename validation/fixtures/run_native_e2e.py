"""Run original references, real horn search and frozen validation in a fresh directory."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from meh_studio.boundary_lab import BoundaryLabRuntime, SolveRequest, _write_json, _termination_guard, sha256
from meh_studio.catalogue import Catalogue
from meh_studio.domain import DriverRevision
from meh_studio.geometry import HornGeometry
from meh_studio.optimisation import SearchBrief, candidates, optimise, evaluate_candidate, response_score
from validate_search_finalist import validate, validation_frequencies


VALIDATION_PARTS=17


def checked_source_revision(repo):
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=repo,text=True).strip():
        raise ValueError('native evidence requires a clean source checkout')
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()


def verify_source_revision(repo,revision):
    current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    changed=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=repo).returncode
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--','src','validation/fixtures'],cwd=repo,text=True).strip()
    if current!=revision or changed or untracked:raise ValueError('project source changed during experiment')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--brief',type=Path)
    parser.add_argument('--geometry',type=Path)
    parser.add_argument('--search-only',action='store_true',help='Preserve the reference and search for partitioned CI validation')
    parser.add_argument('--checkout',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--julia',type=Path,required=True)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2];output=args.output.absolute()
    brief=SearchBrief.model_validate_json((args.brief or repo/'examples/synthetic-dense-search-brief.json').read_text())
    frequencies=validation_frequencies(brief.frequencies_hz)
    if args.search_only and len(frequencies)<VALIDATION_PARTS:
        raise ValueError(f'partitioned validation requires at least {VALIDATION_PARTS} validation frequencies')
    base=HornGeometry.model_validate_json((args.geometry or repo/'examples/three-driver-geometry.json').read_text())
    runtime=BoundaryLabRuntime(args.checkout,args.python,args.julia,julia_threads=1)
    identity=runtime.verify()
    source_commit=checked_source_revision(repo)
    runner_digest=sha256(Path(__file__))
    report={'schema_version':1,'status':'running','qualified':False,'physical_validation':False,
            'source_commit':source_commit,'runner_sha256':runner_digest,'runtime':identity,
            'acceptance_limits':{'tube_relative_error':.005,'refinement_magnitude_db':.5,'refinement_phase_deg':5,'minimum_heldout_ripple_improvement_db':1.0},
            'limitations':['Synthetic drivers and prices','No efficiency, continuous-band or physical qualification',
                           'Complex64 coupled electrical consistency remains unsupported']}
    with _termination_guard(report) as activate:
        output.mkdir(parents=True,exist_ok=False)
        try:
            activate()
            def stage(name):
                report['stage']=name;_write_json(output/'experiment.json',report)
                print(name,flush=True)
            stage('independent_reference')
            fixture=repo/'validation/fixtures'
            subprocess.run([sys.executable,str(fixture/'generate_plane_wave_tube.py'),str(output/'analytic-tube')],check=True)
            request=SolveRequest.model_validate_json((repo/'examples/solver-smoke-request.json').read_text())
            runtime.solve(output/'analytic-tube/project.blab.json',request,output/'analytic-evaluation',timeout_s=1800)
            comparison=json.loads(subprocess.check_output([sys.executable,str(fixture/'compare_plane_wave_tube.py'),
                str(output/'analytic-tube'),str(output/'analytic-evaluation')],text=True))
            _write_json(output/'analytic-comparison.json',comparison)
            if (not comparison['consistency']['passed'] or any(max(row['velocity_relative_error'],row['current_relative_error'])>.005 for row in comparison['rows'])):
                raise ValueError('independent tube accuracy gate failed')
            stage('catalogue_and_search')
            drivers=[DriverRevision.model_validate(d) for d in json.loads((repo/'examples/synthetic-search-drivers.json').read_text())]
            with Catalogue.create(output/'drivers.sqlite') as catalogue:
                for driver in drivers:catalogue.add(driver)
            search=optimise(brief,base,output/'drivers.sqlite',runtime,output/'search',solver_stage_timeout_s=7200)
            baseline=response_score(output/'search/trial-000/system/project.blab.json',output/'search/trial-000/evaluation',(1.,))
            _write_json(output/'baseline-search-grid.json',baseline)
            report['stage_sha256']={name:sha256(output/name) for name in ('analytic-comparison.json','baseline-search-grid.json','search/search.json')}
            if args.search_only:
                verify_source_revision(repo,source_commit)
                if runtime.verify()!=identity or sha256(Path(__file__))!=runner_digest:raise ValueError('search-stage runtime or runner changed')
                report.update(status='search_complete',stage='search_complete')
                return
            stage('baseline_validation_grid')
            baseline_brief=SearchBrief.model_validate(brief.model_dump()|{'side_gains':(1.,)})
            baseline_dense=evaluate_candidate(candidates(brief,base,drivers)[0],output/'baseline-validation',runtime,
                baseline_brief,frequencies=frequencies,timeout_s=7200)
            stage('frozen_finalist_validation')
            finalist=validate(output/'search',output/'finalist-validation',runtime)
            heldout=[i for i,f in enumerate(frequencies) if f not in brief.frequencies_hz]
            coarse=finalist['levels'][0]['score']
            report['results']={'winner_index':search['winner_index'],
                'baseline_search_ripple_db':baseline['ripple_db'],'winner_search_ripple_db':search['winner']['ripple_db'],
                'baseline_validation_ripple_db':baseline_dense['ripple_db'],'winner_validation_coarse_ripple_db':coarse['ripple_db'],
                'baseline_heldout_ripple_db':float(np.ptp(np.asarray(baseline_dense['relative_response_db'])[heldout])),
                'winner_heldout_ripple_db':float(np.ptp(np.asarray(coarse['relative_response_db'])[heldout])),
                'refinement_passed':finalist['refinement_passed'],
                'coupled_electrical_consistency_passed':finalist['electrical_consistency_passed']}
            verify_source_revision(repo,source_commit)
            if runtime.verify()!=identity or sha256(Path(__file__))!=runner_digest:
                raise ValueError('experiment runtime or runner changed')
            improvement=report['results']['baseline_heldout_ripple_db']-report['results']['winner_heldout_ripple_db']
            if improvement<1.0:raise ValueError('held-out ripple improvement is below the declared 1 dB gate')
            if not finalist['refinement_passed']:raise ValueError('finalist mesh stability gate failed')
            report.update(status='complete',stage='complete')
        except BaseException as exc:
            report.update(status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',error=f'{type(exc).__name__}: {exc}')
            raise
        finally:_write_json(output/'experiment.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
