# Material-aware search budgets

An optional `build_budget` in the search brief constrains the estimated cost of
the actual generated CAD plus drivers and declared allowances:

```json
{
  "maximum_total_cost": 300.0,
  "material_density_kg_m3": 1270.0,
  "material_cost_per_kg": 16.0,
  "process_allowance_factor": 1.2,
  "other_cost_allowance": 55.0
}
```

All costs use the brief's currency. These are planning assumptions, not quotes.
Here the other allowance covers hardware, sealing, damping, delivery and printing
electricity. Amplifiers, measurement equipment and labour require an explicit
allowance if included in the user's budget.

The estimate sums material volumes from the actual CAD parts, multiplies by
density, process allowance and material price, then adds drivers and the other
allowance. Over-budget candidates retain their CAD and `build-cost.json` but are
rejected before meshing or solving. Successful candidates use estimated total cost
as the cost contribution to fitness, normalised by the total budget. Recovery
recomputes this from the bound geometry; winner export independently verifies and
includes it in the bill of materials. The separate maximum driver-cost constraint
still applies.

Without `build_budget`, existing driver-only fitness, serialization and exports
remain unchanged. A material estimate is not a slicer prediction: unmodelled
mountings, enclosure parts, supports, failures and print settings may change
consumption. No manufacturing or physical qualification is inferred.
