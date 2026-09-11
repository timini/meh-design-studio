import json
import numpy as np
import pytest
from meh_studio.domain import SourceModel
from meh_studio.generated_system import HornSources
from meh_studio.references import solve_driver_circuit


def test_legacy_source_bytes_and_identity_are_unchanged(source):
    import hashlib
    before = source.model_dump()
    assert 'ideal_outlet_area_m2' not in before
    canonical = json.dumps(before, sort_keys=True, separators=(',', ':'), allow_nan=False)
    explicit = SourceModel.model_validate(before | {'ideal_outlet_area_m2': None})
    assert explicit.canonical_json() == canonical
    assert explicit.content_hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_transform_preserves_current_volume_flow_and_power_under_mutual_load(source):
    # Compare independent physical-diaphragm equations with the outlet-coordinate
    # equations. One driven port and one induced port share a reciprocal load.
    physical = SourceModel.model_validate(source.model_dump() | {
        'ideal_outlet_area_m2': source.sd_m2 / 3})
    parameters = physical.outlet_piston_parameters()
    outlet = SourceModel.model_validate(source.model_dump() | {
        'bl_n_a': parameters['bl_n_per_a'], 'mmd_kg': parameters['mmd_kg'],
        'cms_m_n': parameters['cms_m_per_n'], 'rms_ns_m': parameters['rms_n_s_per_m'],
        'sd_m2': physical.outlet_area_m2})
    frequency = [350., 1200., 3000., 7500.]
    z_outlet = np.tile([[4.-2j, 1.-.5j], [1.-.5j, 3.-1j]], (4, 1, 1))
    ratios = np.array([3., 1.])
    z_physical = z_outlet * ratios[None, :, None] * ratios[None, None, :]
    voltage = [[1., 0.]] * 4
    a = solve_driver_circuit((physical, source), frequency, voltage, z_physical)
    b = solve_driver_circuit((outlet, source), frequency, voltage, z_outlet)
    np.testing.assert_allclose(a.current_a, b.current_a, rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(a.velocity_m_s * ratios, b.velocity_m_s, rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(a.velocity_m_s[:, 0] * physical.sd_m2,
                               b.velocity_m_s[:, 0] * physical.outlet_area_m2, rtol=1e-12)
    for field in ('electrical_input_w', 'coil_loss_w', 'mechanical_loss_w', 'load_power_w'):
        np.testing.assert_allclose(getattr(a, field), getattr(b, field), rtol=1e-12, atol=1e-14)
    assert np.all(abs(b.current_a[:, 1]) > 0)
    assert physical.mmd_kg == source.mmd_kg  # Physical record was not rewritten.


@pytest.mark.parametrize('area', [0., -1., float('nan'), float('inf'), 1e-300, 1e300])
def test_invalid_or_unrepresentable_outlet_area_fails(source, area):
    with pytest.raises(ValueError):
        SourceModel.model_validate(source.model_dump() | {'ideal_outlet_area_m2': area})


def test_mid_front_rear_geometry_cannot_silently_become_two_transformers(source):
    transformed = SourceModel.model_validate(source.model_dump() | {'ideal_outlet_area_m2': .001})
    with pytest.raises(ValueError, match='only for the throat'):
        HornSources(throat=source, side=transformed)
