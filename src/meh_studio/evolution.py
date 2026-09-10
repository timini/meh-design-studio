"""Seeded (mu+1) evolutionary proposals driven by completed coupled simulations.

Every proposal can be reconstructed from controls and preceding trial outcomes.
Periodic random exploration competes on the same solver grid as elite mutations.
"""
from __future__ import annotations
import math
import random
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .domain import Positive, Record
from .geometry import HornGeometry

Parameter = Literal['length_m','mouth_radius_m','port_radius_m','port_length_m',
                    'front_depth_m','rear_depth_m','entry_fraction_0','entry_fraction_1','driver_axial_offset_m']


class EvolutionSettings(Record):
    elite_size: Annotated[int, Field(strict=True,ge=1,le=20)] = 3
    explore_every: Annotated[int, Field(strict=True,ge=2,le=20)] = 4
    mutation_fraction: Annotated[float, Field(strict=True,gt=0,le=1)] = .25
    sigma_fraction: Annotated[float, Field(strict=True,gt=0,le=.5)] = .12
    profile_scale_bounds: tuple[Positive, Positive] = (.65,1.5)
    geometry_bounds: dict[Parameter, tuple[Annotated[float,Field(strict=True)],Annotated[float,Field(strict=True)]]] = {}

    @model_validator(mode='after')
    def ordered_bounds(self):
        low,high=self.profile_scale_bounds
        if not .5 <= low < high <= 2:
            raise ValueError('profile mutation bounds must increase within [0.5,2]')
        for name,(low,high) in self.geometry_bounds.items():
            if name!='driver_axial_offset_m' and low<=0:
                raise ValueError('non-offset geometry bounds must be positive')
            if name=='driver_axial_offset_m' and not -.5<=low<high<=.5:
                raise ValueError('driver axial offset bounds must increase within ±0.5 m')
            if low>=high or (name.startswith('entry_fraction') and high>=1):
                raise ValueError('evolution bounds must increase; entry fractions must be below one')
        return self


class ProposalFailure(ValueError):
    def __init__(self,report):
        super().__init__('64 evolutionary proposals violated declared geometry constraints')
        self.report=report


def _reflect(value,low,high):
    width=high-low
    position=(value-low)%(2*width)
    return low+(position if position<=width else 2*width-position)


def validate_bounds(settings,design):
    for name,(low,high) in settings.geometry_bounds.items():
        if name.startswith('entry_fraction'):
            index=int(name[-1])
            if index>=len(design.entry_positions_m):continue
            value=design.entry_positions_m[index]/design.length_m
        else:value=getattr(design,name)
        if not low <= value <= high:
            raise ValueError(f'{name} is outside declared evolutionary bounds')
    low,high=settings.profile_scale_bounds
    if any(not low<=v<=high for section in design.profile_sections for v in section.radial_scales):
        raise ValueError('profile scales are outside declared evolutionary bounds')


def propose(brief, seed_pool, history, previous):
    """Return candidate and retained proposal diagnostics; never invoke a solver."""
    settings=brief.evolution
    index=len(history)
    if index==0:
        for candidate in seed_pool:validate_bounds(settings,candidate['design'])
        return seed_pool[0],{'method':'declared_baseline','parent_index':None,'rejected':[]}
    rng=random.Random(f'{brief.seed}:{index}:evolution-v1')
    eligible=sorted((i for i,t in enumerate(history) if t['status']=='complete'),
                    key=lambda i:(history[i]['objective'],i))[:settings.elite_size]
    explore=index%settings.explore_every==0 or not eligible
    parent=None if explore else rng.choice(eligible)
    selected=rng.choice(seed_pool) if explore else previous[parent]
    report={'method':'random_exploration' if explore else 'elite_mutation',
            'parent_index':parent,'rejected':[]}
    for attempt in range(64):
        # Some offspring explore a different catalogue source while retaining shape.
        source=rng.choice(seed_pool) if rng.random()<.2 else selected
        data=selected['design'].model_dump(mode='json')
        data['throat_radius_m']=source['design'].throat_radius_m
        data['front_radius_m']=source['design'].front_radius_m
        length=data['length_m']
        fractions=[v/length for v in data['entry_positions_m']]
        profile=data.get('profile_sections') or [
            {'fraction':fraction,'radial_scales':[1.]*8} for fraction in (.35,.7,1.)]
        genes=[('profile',i,j,*settings.profile_scale_bounds)
               for i in range(len(profile)) for j in range(8)]
        genes += [('geometry',name,None,*bounds) for name,bounds in sorted(settings.geometry_bounds.items())
                  if not name.startswith('entry_fraction') or int(name[-1])<len(fractions)]
        chosen=genes if explore else rng.sample(genes,max(1,math.ceil(settings.mutation_fraction*len(genes))))
        mutations=[]
        for kind,key,column,low,high in chosen:
            if kind=='profile':old=profile[key]['radial_scales'][column]
            elif key.startswith('entry_fraction'):old=fractions[int(key[-1])]
            else:old=data.get(key,getattr(selected['design'],key))
            value=rng.uniform(low,high) if explore else _reflect(old+rng.gauss(0,settings.sigma_fraction*(high-low)),low,high)
            if kind=='profile':profile[key]['radial_scales'][column]=value
            elif key.startswith('entry_fraction'):fractions[int(key[-1])]=value
            else:data[key]=value
            mutations.append({'kind':kind,'key':key,'column':column,'before':old,'after':value})
        data['entry_positions_m']=[fraction*data['length_m'] for fraction in fractions]
        data['profile_sections']=profile
        try:
            design=HornGeometry.model_validate(data)
            validate_bounds(settings,design)
            if any(c is not None and c['design']==design and c['sources']==source['sources'] for c in previous):
                raise ValueError('duplicate physical candidate')
            throat,side=source['drivers']
            cost=brief.prices[throat.id]+(design.driver_count-1)*brief.prices[side.id]
            candidate={'design':design,'sources':source['sources'],'cost':cost,'drivers':source['drivers']}
            if candidate['cost']>brief.max_driver_cost or design.driver_count>brief.max_drivers:
                raise ValueError('candidate exceeds cost/count constraints')
            report['mutations']=mutations
            return candidate,report
        except ValueError as exc:
            report['rejected'].append({'design':data,'reason':str(exc)})
    raise ProposalFailure(report)


def replay(brief,base,drivers,history,count=None):
    """Reconstruct proposal order for export, validation and recovery."""
    from .optimisation import candidates
    seeds=candidates(brief,base,drivers)
    previous=[];proposals=[]
    for i in range(len(history) if count is None else count):
        try:candidate,proposal=propose(brief,seeds,history[:i],previous)
        except ProposalFailure as exc:candidate,proposal=None,exc.report
        previous.append(candidate);proposals.append(proposal)
    return previous,proposals
