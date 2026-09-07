import math

import numpy as np
import pytest

from meh_studio.references import cavity_modes, solve_driver_circuit


def test_cube_modes_include_degeneracy_and_exclude_static_mode():
    modes = cavity_modes((1, 1, 1), 250, 340)
    assert len(modes) == 6
    assert [m["frequency_hz"] for m in modes[:3]] == [170]*3
    assert all(m["frequency_hz"] == pytest.approx(170*math.sqrt(2)) for m in modes[3:])
    assert {tuple(m["indices"]) for m in modes[:3]} == {(1, 0, 0), (0, 1, 0), (0, 0, 1)}


def test_non_cubic_fundamental_and_length_scaling():
    a = cavity_modes((0.47, 0.33, 0.22), 1000)
    b = cavity_modes((0.94, 0.66, 0.44), 500)
    assert a[0]["frequency_hz"] == pytest.approx(343 / 0.94)
    assert [m["indices"] for m in a] == [m["indices"] for m in b]
    np.testing.assert_allclose([m["frequency_hz"] for m in a],
                               2*np.array([m["frequency_hz"] for m in b]))


@pytest.mark.parametrize("lengths, maximum", [((0, 1, 1), 100), ((1, 1, 1), -1),
    ((1, 1, 1), float("nan")), ((1, 1, 1), 1e9), ((1, 1), 100), ((1e308, 1, 1), 1e308)])
def test_invalid_reference_request(lengths, maximum):
    with pytest.raises(ValueError):
        cavity_modes(lengths, maximum)


def test_resonance_has_known_real_electrical_impedance(source):
    # At mechanical resonance, Le=0 and Zm=Rms; Zinput = Re + Bl^2/Rms = 22 ohm.
    fs = 1 / (2 * math.pi * math.sqrt(source.mmd_kg * source.cms_m_n))
    result = solve_driver_circuit((source,), [fs], [[2.2]])
    np.testing.assert_allclose(result.current_a, [[0.1]], atol=1e-14)
    np.testing.assert_allclose(result.velocity_m_s, [[0.4]], atol=1e-14)
    np.testing.assert_allclose(result.electrical_input_w, [0.22])
    np.testing.assert_allclose(result.coil_loss_w, [0.06])
    np.testing.assert_allclose(result.mechanical_loss_w, [0.16])


def test_mutual_load_moves_zero_voltage_driver_and_conserves_power(source):
    frequency = [40, 100, 1000]
    # Positive definite real resistance matrix plus reciprocal reactive loading.
    loads = np.tile([[2 - 3j, 0.5 - 1j], [0.5 - 1j, 2 - 3j]], (3, 1, 1))
    result = solve_driver_circuit((source, source), frequency, [[1, 0]]*3, loads)
    assert np.all(abs(result.velocity_m_s[:, 1]) > 0)
    assert np.all(abs(result.current_a[:, 1]) > 0)
    np.testing.assert_allclose(result.electrical_input_w,
                               result.coil_loss_w + result.mechanical_loss_w + result.load_power_w,
                               rtol=1e-12, atol=1e-14)
    reverse = solve_driver_circuit((source, source), frequency, [[0, 1]]*3, loads)
    np.testing.assert_allclose(result.velocity_m_s[:, 1], reverse.velocity_m_s[:, 0])


def test_voltage_scaling_complex_superposition_and_no_load(source):
    f = [20, 80, 500]
    a = solve_driver_circuit((source,), f, [[1]]*3)
    b = solve_driver_circuit((source,), f, [[2j]]*3)
    c = solve_driver_circuit((source,), f, [[1+2j]]*3)
    np.testing.assert_allclose(c.velocity_m_s, a.velocity_m_s+b.velocity_m_s)
    np.testing.assert_allclose(b.electrical_input_w, 4*a.electrical_input_w)
    np.testing.assert_allclose(a.load_power_w, 0)


@pytest.mark.parametrize("f,v,load", [([0], [[1]], None), ([100, 20], [[1], [1]], None),
    ([100], [1], None), ([100], [[float("nan")]], None), ([100], [[1]], [[[float("inf")]]])])
def test_bad_circuit_inputs_rejected(source, f, v, load):
    with pytest.raises(ValueError):
        solve_driver_circuit((source,), f, v, load)
