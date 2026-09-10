"""Replay the selected candidate and its original evidence from a completed search."""
import json
from pathlib import Path
from .boundary_lab import _read_json, sha256
from .domain import DriverRevision
from .geometry import HornGeometry
from .optimisation import SearchBrief, candidates, candidate_record, verified_assessment


def load_completed_search(search):
    try:
        return _load_completed_search(search)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('incomplete or invalid completed search record') from exc


def _load_completed_search(search):
    search=Path(search).absolute()
    control_names=('search.json','brief.json','base-geometry.json','catalogue-snapshot.json')
    control_hashes={name:sha256(search/name) for name in control_names}
    result=_read_json(search/'search.json')
    if result['status']!='complete': raise ValueError('search must complete before finalist validation')
    expected={name:digest for name,digest in control_hashes.items() if name!='search.json'}
    if result.get('control_sha256')!=expected:
        raise ValueError('search controls do not match completed search; legacy runs require a fresh search')
    index=result['winner_index'];trials=result.get('trials',[])
    if type(index) is not int or not 0<=index<len(trials):raise ValueError('missing indexed winning trial')
    candidate_name=f"trial-{result['winner_index']:03d}/candidate.json"
    candidate_file=search/candidate_name
    if result.get('winner_candidate_sha256')!=sha256(candidate_file):
        raise ValueError('winning candidate differs from completed search')
    control_hashes[candidate_name]=result['winner_candidate_sha256']
    brief=SearchBrief.model_validate_json((search/'brief.json').read_text())
    base=HornGeometry.model_validate_json((search/'base-geometry.json').read_text())
    drivers=[DriverRevision.model_validate(d) for d in json.loads((search/'catalogue-snapshot.json').read_text())]
    winner=candidates(brief,base,drivers)[result['winner_index']]
    if candidate_record(winner)!=_read_json(candidate_file):
        raise ValueError('reconstructed winner differs from recorded candidate')
    trial=trials[index]
    if trial.get('status')!='complete' or trial.get('index')!=index or result['winner']!=trial:
        raise ValueError('winner record differs from indexed completed trial')
    score_name=f'trial-{index:03d}/score.json'
    if result.get('winner_score_sha256')!=sha256(search/score_name):raise ValueError('winning scored artifact differs')
    if {k:v for k,v in trial.items() if k not in ('index','status')}!=_read_json(search/score_name):
        raise ValueError('winning trial differs from its scored artifact')
    control_hashes[score_name]=result['winner_score_sha256']
    evaluation=search/f'trial-{index:03d}/evaluation'
    evaluation_name=f'trial-{index:03d}/evaluation/evaluation.json'
    if trial.get('evaluation_sha256')!=sha256(evaluation/'evaluation.json'):
        raise ValueError('winning evaluation differs from its scored artifact')
    assessment=verified_assessment(search/f'trial-{index:03d}/system/project.blab.json',evaluation)
    if assessment['controls']['evaluation.json']!=trial['evaluation_sha256']:
        raise ValueError('winning evaluation changed during replay')
    control_hashes[evaluation_name]=trial['evaluation_sha256']
    gain=trial['side_gain']
    return control_hashes,result,brief,base,winner,gain
