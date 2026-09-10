"""Declared material-cost estimates from the actual candidate CAD volumes."""
import math
from typing import Annotated
from pydantic import Field
from .domain import Record, Positive, Nonnegative


class BuildBudget(Record):
    maximum_total_cost: Positive
    material_density_kg_m3: Positive
    material_cost_per_kg: Positive
    process_allowance_factor: Annotated[float, Field(strict=True, ge=1, allow_inf_nan=False)] = 1.2
    other_cost_allowance: Nonnegative = 0.


def estimate_build_cost(budget, geometry, driver_cost):
    volumes=geometry.get('material_volume_m3',{})
    if geometry.get('status')!='complete' or not volumes or any(
            type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in volumes.values()):
        raise ValueError('build cost requires positive complete CAD material volumes')
    volume=sum(volumes.values())
    mass=volume*budget.material_density_kg_m3
    purchase_mass=mass*budget.process_allowance_factor
    material_cost=purchase_mass*budget.material_cost_per_kg
    total=driver_cost+material_cost+budget.other_cost_allowance
    if not all(math.isfinite(v) for v in (volume,mass,purchase_mass,material_cost,total)):
        raise ValueError('build cost overflow')
    return {'basis':'CAD_material_volume_with_declared_allowances','driver_cost':driver_cost,
            'material_volume_m3':volume,'solid_material_mass_kg':mass,
            'allowed_material_mass_kg':purchase_mass,'material_cost':material_cost,
            'other_cost_allowance':budget.other_cost_allowance,'estimated_total_cost':total,
            'maximum_total_cost':budget.maximum_total_cost,'within_budget':total<=budget.maximum_total_cost,
            'slicer_verified':False,'price_provenance':'declared_search_brief',
            'limitations':['Nominal solid material and process allowance; no slicer or fabrication qualification',
                           'Only listed CAD parts, drivers and declared other allowance are costed']}


def cost_adjusted_score(score,brief,candidate,geometry):
    result=dict(score)
    fraction=candidate['cost']/brief.max_driver_cost
    if brief.build_budget is not None:
        estimate=estimate_build_cost(brief.build_budget,geometry,candidate['cost'])
        if not estimate['within_budget']:
            raise ValueError('candidate exceeds declared total build budget')
        result['build_cost']=estimate
        fraction=estimate['estimated_total_cost']/brief.build_budget.maximum_total_cost
    result['objective']=result.get('acoustic_objective',result['ripple_db'])+brief.cost_weight_db*fraction
    return result
