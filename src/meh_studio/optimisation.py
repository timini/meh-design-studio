"""Bounded experimental search using real generated FEM/BEM voltage bases.

This evaluates relative response flatness. It does not infer RMS sensitivity,
physical source qualification, manufacturing readiness or global optimality.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
import random
import shutil
from typing import Annotated

import numpy as np
from pydantic import Field, model_validator

from .boundary_lab import BoundaryLabRuntime, SolveRequest, _read_json, _write_json, _contained, sha256, inspect_result, _termination_guard
from .catalogue import Catalogue
from .domain import Record, Positive
from .generated_system import HornSources
from .geometry import HornGeometry, export_geometry, mesh_geometry
from .radiating_system import compile_radiating_system
from .validation import validate_electrical_basis


class SearchBrief(Record):
    frequencies_hz: tuple[Positive, ...]
    throat_ids: tuple[str, ...]
    side_ids: tuple[str, ...]
    prices: dict[str, Positive]
    currency: str = 'GBP'
    max_driver_cost: Positive
    max_drivers: Annotated[int, Field(strict=True, ge=3, le=5)] = 5
    lengths_m: tuple[Positive, ...]
    mouth_radii_m: tuple[Positive, ...]
    entry_fractions: tuple[tuple[Positive, ...], ...]
    side_gains: tuple[Positive, ...] = (.5, 1., 2.)
    trial_budget: Annotated[int, Field(strict=True, ge=1, le=100)] = 4
    seed: Annotated[int, Field(strict=True, ge=0)] = 2026
    exterior_mesh_size_m: Annotated[float, Field(ge=.01, le=.05)] = .02
    cost_weight_db: Annotated[float, Field(ge=0, allow_inf_nan=False)] = .5

    @model_validator(mode='after')
    def bounded(self):
        SolveRequest(frequencies_hz=self.frequencies_hz)
        if len(self.frequencies_hz) < 3 or len(self.frequencies_hz) > 100:
            raise ValueError('experimental search requires 3–100 frequency samples')
        groups = (self.throat_ids,self.side_ids,self.lengths_m,self.mouth_radii_m,self.entry_fractions,self.side_gains)
        if any(not group or len(group)>20 or len(set(group))!=len(group) for group in groups):
            raise ValueError('search choices must be nonempty, unique and bounded to 20 each')
        if math.prod(map(len,groups[:-1])) > 10000:
            raise ValueError('candidate grid exceeds 10000 combinations')
        if any(len(row) not in (1,2) or any(v>=1 for v in row) for row in self.entry_fractions):
            raise ValueError('one or two entry fractions strictly between zero and one required')
        if not set(self.throat_ids+self.side_ids).issubset(self.prices):
            raise ValueError('each selected driver needs a price in the declared currency')
        return self


def candidates(brief, base, drivers):
    selected=set(brief.throat_ids+brief.side_ids)
    records={}
    for driver in drivers:
        if driver.id not in selected: continue
        previous=records.get(driver.id)
        if previous is not None and previous.revision==driver.revision and previous!=driver:
            raise ValueError('conflicting selected driver revisions')
        if previous is None or driver.revision>previous.revision:
            records[driver.id]=driver
    if not set(brief.throat_ids+brief.side_ids).issubset(records):
        raise ValueError('selected driver absent from catalogue')
    rows = []
    for throat,side,length,mouth,entries in itertools.product(brief.throat_ids,brief.side_ids,
            brief.lengths_m,brief.mouth_radii_m,brief.entry_fractions):
        count = 1+2*len(entries)
        cost = brief.prices[throat]+(count-1)*brief.prices[side]
        if count>brief.max_drivers or cost>brief.max_driver_cost: continue
        t,s = records[throat],records[side]
        if t.source_model is None or s.source_model is None:
            raise ValueError('selected drivers require explicit source circuits')
        try:
            design = HornGeometry.model_validate(base.model_dump() | {'length_m':length,
                'mouth_radius_m':mouth,'entry_positions_m':tuple(length*z for z in entries),
                'throat_radius_m':math.sqrt(t.source_model.sd_m2/math.pi),
                'front_radius_m':math.sqrt(s.source_model.sd_m2/math.pi)})
        except ValueError:
            continue
        sources=HornSources(throat=t.source_model,side=s.source_model)
        rows.append({'design':design,'sources':sources,'cost':cost,'drivers':(t,s)})
    if not rows: raise ValueError('no feasible candidates within geometry/count/cost bounds')
    # First feasible declared choice is the baseline; all remaining choices have
    # a deterministic seeded order and identical solve budgets.
    tail=rows[1:];random.Random(brief.seed).shuffle(tail)
    return ([rows[0]]+tail)[:brief.trial_budget]


def verified_assessment(project, evaluation):
    saved=_read_json(evaluation/'evaluation.json')
    controls={name:sha256(evaluation/name) for name in ('evaluation.json','request.json','preflight.json')}
    if (saved.get('status')!='complete' or saved.get('project_sha256')!=sha256(project)
            or saved.get('request_sha256')!=controls['request.json']
            or saved.get('preflight_sha256')!=controls['preflight.json']):
        raise ValueError('evaluation control identity mismatch')
    request=SolveRequest.model_validate_json((evaluation/'request.json').read_text())
    result=inspect_result(evaluation/'upstream',request,saved['runtime']['backend'],project_path=project)
    if result!=saved['result']: raise ValueError('evaluation artifact identity mismatch')
    try:
        checks=validate_electrical_basis(project,evaluation)
    except ValueError as exc:
        if str(exc)!='electrical consistency at 1e-8 requires complex128 response storage': raise
        checks={'passed':False,'status':'unsupported_storage_precision','reason':str(exc),
                'acoustic_accuracy_validated':False}
    return {'controls':controls,'result':result,'checks':checks}


def relative_response(pressure):
    values=np.asarray(pressure,dtype=complex)
    if values.ndim!=1 or not values.size or not np.isfinite(values).all():
        raise ValueError('finite pressure vector required')
    magnitude=np.abs(values)
    if np.any(magnitude==0): raise ValueError('relative response is undefined at an exact pressure null')
    return 20*(np.log10(magnitude)-np.log10(magnitude.max()))


def response_score(project, evaluation, gains):
    assessment=verified_assessment(project,evaluation)
    checks=assessment["checks"]
    root=evaluation/'upstream'
    manifest=_read_json(root/'manifest.json')
    domains=_read_json(_contained(root,manifest['domains_metadata_file']))['domains']
    with np.load(_contained(root,manifest['domains_file']),allow_pickle=False) as archive:
        domain=next(d for d in domains if d['id']=='observation:horizontal-polar')
        angles=archive[domain['coordinates']['angle_deg']]
        axial=np.flatnonzero(angles==0)
    if len(axial)!=1: raise ValueError('one explicit on-axis observation required')
    ports=manifest['excitation_port_ids']
    system=_read_json(project)['physical_system']
    port_components={p['id']:p['component_id'] for p in system['excitation_ports']}
    if set(port_components)!=set(ports): raise ValueError('voltage basis identity mismatch')
    throat=[i for i,p in enumerate(ports) if port_components[p]=='component:throat']
    if len(throat)!=1: raise ValueError('one throat source required')
    bases=[]
    for row in manifest['results']:
        metadata=_read_json(_contained(root,row['metadata_file']))
        q=next(q for q in metadata['quantities'] if q['id']=='acoustic:pressure:horizontal-polar')
        with np.load(_contained(root,row['arrays_file']),allow_pickle=False) as archive:
            data=archive[q['key']]
            if data.shape != (len(ports),len(angles)): raise ValueError('unsupported polar basis shape')
            bases.append(data[:,int(axial[0])])
    basis=np.asarray(bases)
    options=[]
    for gain in gains:
        weights=np.full(len(ports),gain);weights[throat[0]]=1
        pressure=basis@weights
        try: relative_db=relative_response(pressure)
        except ValueError: continue
        options.append({'ripple_db':float(np.ptp(relative_db)),'side_gain':gain,
                        'relative_response_db':relative_db.tolist()})
    if not options: raise ValueError('all candidate responses contain null/nonfinite pressure')
    if verified_assessment(project,evaluation)!=assessment:
        raise ValueError('evaluation changed while scoring')
    return min(options,key=lambda row:(row['ripple_db'],row['side_gain'])) | {'electrical_validation':checks}


def candidate_record(candidate):
    return {'design':candidate['design'].model_dump(mode='json'),
        'sources':candidate['sources'].model_dump(mode='json'),'driver_cost':candidate['cost'],
        'driver_revisions':[d.model_dump(mode='json') for d in candidate['drivers']]}


def evaluate_candidate(candidate, root, runtime, brief, *, mesh_size=None, frequencies=None, timeout_s=1800):
    design=candidate['design']
    if mesh_size is not None:
        design=HornGeometry.model_validate(design.model_dump()|{'mesh_size_m':mesh_size})
    root.mkdir(parents=True,exist_ok=False)
    _write_json(root/'candidate.json',candidate_record(candidate|{'design':design}))
    export_geometry(design,root/'geometry');mesh_geometry(root/'geometry')
    compile_radiating_system(root/'geometry',candidate['sources'],root/'system',runtime,
                             exterior_mesh_size_m=brief.exterior_mesh_size_m)
    request=SolveRequest(frequencies_hz=frequencies or brief.frequencies_hz,
        include_project_observations=True,retain=('fem_nodal_pressure','bem_boundary_traces'))
    runtime.solve(root/'system/project.blab.json',request,root/'evaluation',timeout_s=timeout_s)
    score=response_score(root/'system/project.blab.json',root/'evaluation',brief.side_gains)
    score['objective']=score['ripple_db']+brief.cost_weight_db*candidate['cost']/brief.max_driver_cost
    score.update(driver_count=design.driver_count,driver_cost=candidate['cost'],
                 evaluation_sha256=sha256(root/'evaluation/evaluation.json'))
    _write_json(root/'score.json',score)
    return score


def optimise(brief, base, catalogue_path, runtime, output):
    report={'status':'running'}
    with _termination_guard(report) as activate:
        return _optimise(brief,base,catalogue_path,runtime,output,report,activate)


def _optimise(brief, base, catalogue_path, runtime, output, report, activate):
    output=Path(output).absolute()
    with Catalogue(catalogue_path,readonly=True) as catalogue: drivers=catalogue.list()
    pool=candidates(brief,base,drivers)
    runtime_identity=runtime.verify()
    output.mkdir(parents=True,exist_ok=False)
    report.update({'schema_version':1,'status':'running','kind':'experimental_fem_bem_search',
        'qualified':False,'physical_validation':False,'runtime':runtime_identity,'trials':[],
        'limitations':['Synthetic/unqualified sources may be used only for pipeline experiments',
            'Relative on-axis ripple objective, not calibrated sensitivity or efficiency',
            'Driver-only prices exclude amplifier, material, printing and assembly',
            'Straight conical family; finite sampled grid is not a global optimum']})
    try:
        activate()
        _write_json(output/'brief.json',brief.model_dump(mode='json'))
        _write_json(output/'base-geometry.json',base.model_dump(mode='json'))
        _write_json(output/'catalogue-snapshot.json',[d.model_dump(mode='json') for d in drivers])
        report['control_sha256']={name:sha256(output/name) for name in
            ('brief.json','base-geometry.json','catalogue-snapshot.json')}
        for i,candidate in enumerate(pool):
            trial={'index':i,'status':'running'};report['trials'].append(trial)
            _write_json(output/'search.json',report)
            if runtime.verify()!=runtime_identity: raise ValueError('search runtime changed')
            try:
                score=evaluate_candidate(candidate,output/f'trial-{i:03d}',runtime,brief)
                trial.update(status='complete',**score)
            except Exception as exc:
                trial.update(status='failed',error=f'{type(exc).__name__}: {exc}')
            _write_json(output/'search.json',report)
        if runtime.verify()!=runtime_identity: raise ValueError('search runtime changed')
        if any(sha256(output/name)!=digest for name,digest in report['control_sha256'].items()):
            raise ValueError('search controls changed during execution')
        successful=[t for t in report['trials'] if t['status']=='complete']
        if not successful: raise ValueError('no candidate completed a real coupled evaluation')
        winner=min(successful,key=lambda t:(t['objective'],t['index']))
        report.update(status='complete',winner_index=winner['index'],winner=winner,
            winner_candidate_sha256=sha256(output/f"trial-{winner['index']:03d}"/'candidate.json'),
            numerical_consistency_passed=winner['electrical_validation']['passed'])
        # Preserve a complete generated geometry export; its existing report
        # states geometric checks and explicitly excludes print qualification.
        shutil.copytree(output/f"trial-{winner['index']:03d}"/'geometry',output/'winner-geometry')
    except BaseException as exc:
        status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed'
        report.update(status=status,error=f'{type(exc).__name__}: {exc}')
        for trial in report['trials']:
            if trial['status']=='running':trial.update(status=status,error=str(exc))
        raise
    finally:
        _write_json(output/'search.json',report)
    return report
