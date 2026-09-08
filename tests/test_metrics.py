import json
import numpy as np
import pytest

from meh_studio.metrics import (SphereQuadrature, ScalarMetric, electrical_power_rms,
    gain_delay_voltages, pressure_levels_rms, sum_voltage_basis)
from meh_studio.references import solve_driver_circuit


def test_complex_sum_handles_interference_and_labelled_order():
    basis = np.array([[[1, 1j], [1, -1j]]])
    assert np.allclose(sum_voltage_basis(basis, ('a','b'), [[1,-1]], ('b','a')), [[0,-2j]])
    assert np.allclose(sum_voltage_basis(basis, ('a','b'), [[1,1]], ('a','b')), [[2,0]])
    with pytest.raises(ValueError): sum_voltage_basis(basis,('a','b'),[[1,1]],('a','c'))


def test_delayed_negative_time_phasor_matches_time_domain():
    f = np.array([100.,1000.])
    delay = np.array([.0002,.0007])
    gains = np.array([2.,-3.])
    v = gain_delay_voltages(f,gains,delay)
    t = .00037
    assert np.allclose(np.real(v*np.exp(-2j*np.pi*f[:,None]*t)),
                       gains*np.cos(2*np.pi*f[:,None]*(t-delay)))


def test_real_power_including_reactive_and_regenerating_channels():
    channels, total = electrical_power_rms([[2,2,2]],[[1,1j,-.5]])
    assert np.allclose(channels, [[2,0,-1]]) and total[0] == 1


def test_rms_power_matches_independent_time_average():
    v, i = np.array([[2+3j, -1+2j]]), np.array([[1-4j, 3+2j]])
    phase = np.linspace(0,2*np.pi,10000,endpoint=False)
    instantaneous = (np.sqrt(2)*np.real(v[0]*np.exp(-1j*phase[:,None])) *
                     np.sqrt(2)*np.real(i[0]*np.exp(-1j*phase[:,None])))
    channels,total = electrical_power_rms(v,i)
    assert np.allclose(channels[0],instantaneous.mean(axis=0))
    assert total[0] == pytest.approx(instantaneous.sum(axis=1).mean())


def test_spl_reference_doubling_null_and_json():
    levels = pressure_levels_rms([20e-6,1,2,0])
    assert levels[0].value == 0
    assert levels[1].value == pytest.approx(93.9794000867)
    assert levels[2].value - levels[1].value == pytest.approx(6.0205999133)
    assert levels[3].value is None and levels[3].reason == 'zero_pressure'
    assert json.loads(levels[3].canonical_json())['value'] is None
    with pytest.raises(ValueError): ScalarMetric(value=None,unit='dB')


def test_sphere_monopole_dipole_and_polynomial_integrals():
    grid = SphereQuadrature(polar_order=4,azimuth_count=12)
    xyz,w = grid.coordinates_and_weights()
    assert np.allclose(np.linalg.norm(xyz,axis=1),1)
    assert w.sum() == pytest.approx(4*np.pi)
    assert grid.mean_square_pressure(np.ones((1,len(w))))[0] == pytest.approx(1)
    # Rotated dipoles all integrate to 1/3; quadrupole z^2 integrates to 1/5.
    for direction in ([1,0,0],[0,1,0],[0,0,1],np.ones(3)/np.sqrt(3)):
        assert grid.mean_square_pressure((xyz@direction)[None,:])[0] == pytest.approx(1/3)
    assert grid.mean_square_pressure((xyz[:,2]**2)[None,:])[0] == pytest.approx(1/5)
    with pytest.raises(ValueError,match='complete'): grid.mean_square_pressure([[1,2]])


@pytest.mark.parametrize('values',[[],[np.nan],[np.inf]])
def test_invalid_pressure_rejected(values):
    with pytest.raises(ValueError): pressure_levels_rms(values)


def test_invalid_shapes_parameters_and_overflow():
    with pytest.raises(ValueError): electrical_power_rms([[1]],[[1,2]])
    with pytest.raises(ValueError): electrical_power_rms([[1e308]],[[1e308]])
    with pytest.raises(ValueError): gain_delay_voltages([1,1],[1],[0])
    with pytest.raises(ValueError): gain_delay_voltages([1],[1],[-1])
    with pytest.raises(ValueError): gain_delay_voltages([1e308],[1],[1e308])
    with pytest.raises(ValueError): SphereQuadrature(polar_order=101)
    with pytest.raises(ValueError): sum_voltage_basis([[[1],[1]]],('a','a'),[[1,1]],('a','b'))
    with pytest.raises(ValueError): SphereQuadrature().mean_square_pressure(np.full((1,1024),1e308))


def test_synthesised_coupled_circuit_matches_direct_excitation(source):
    f = [40,100,1000]
    loads = np.tile([[2-3j,.5-1j],[.5-1j,2-3j]],(3,1,1))
    sources = (source,source)
    responses = [solve_driver_circuit(sources,f,np.tile(row,(3,1)),loads)
                 for row in np.eye(2)]
    voltage = gain_delay_voltages(f,[2,-1],[0,.0004])
    direct = solve_driver_circuit(sources,f,voltage,loads)
    for name in ('current_a','velocity_m_s'):
        basis = np.stack([getattr(r,name) for r in responses],axis=1)
        combined = sum_voltage_basis(basis,('a','b'),voltage,('a','b'))
        assert np.allclose(combined,getattr(direct,name),rtol=1e-12,atol=1e-14)
    _,power = electrical_power_rms(voltage,direct.current_a)
    assert np.allclose(power,direct.coil_loss_w+direct.mechanical_loss_w+direct.load_power_w)


@pytest.mark.parametrize('value,reason',[(-1,None),(None,'zero_pressure'),(0,None)])
def test_scalar_record_only_supports_implemented_decibel_metrics(value,reason):
    with pytest.raises(ValueError):
        ScalarMetric(value=value,unit='Pa^2',reason=reason)
