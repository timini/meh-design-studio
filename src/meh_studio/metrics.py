"""Versioned linear-response metrics. Inputs must already have declared RMS units.

These functions do not infer a solver's amplitude convention, qualify source data,
interpolate frequencies, or establish far-field/convergence validity.
"""
from __future__ import annotations

from typing import Annotated, Literal
import numpy as np
from pydantic import Field, model_validator

from .domain import Record

METRICS_VERSION = "linear-rms-v1"


class ScalarMetric(Record):
    metrics_version: Literal["linear-rms-v1"] = METRICS_VERSION
    value: float | None
    unit: Literal["dB"]
    reason: Literal["zero_pressure"] | None = None

    @model_validator(mode="after")
    def defined_or_explained(self):
        if (self.value is None) != (self.reason is not None):
            raise ValueError("undefined metrics require a reason; defined metrics cannot have one")
        if self.value is not None and not np.isfinite(self.value):
            raise ValueError("metric values must be finite")
        return self


def _finite(values, ndim, name, *, complex_values=False):
    raw = np.asarray(values)
    if not complex_values and np.iscomplexobj(raw):
        raise ValueError(f"{name} must be real")
    result = np.asarray(values, dtype=complex if complex_values else float)
    if result.ndim != ndim or not result.size or any(n == 0 for n in result.shape) or not np.isfinite(result).all():
        raise ValueError(f"{name} requires a nonempty finite {ndim}-dimensional array")
    return result


def _frequencies(values):
    result = _finite(values, 1, "frequencies")
    if np.any(result <= 0) or np.any(np.diff(result) <= 0):
        raise ValueError("frequencies must be positive and strictly increasing")
    return result


def _ids(values):
    if (not isinstance(values, tuple) or not values
            or any(not isinstance(s, str) or not s for s in values) or len(set(values)) != len(values)):
        raise ValueError("source IDs must be a nonempty unique tuple")
    return values


def _checked(values):
    if not np.isfinite(values).all():
        raise ValueError("metric calculation exceeded finite numerical range")
    return values


def sum_voltage_basis(basis_per_rms_volt, basis_ids: tuple[str, ...],
                      voltage_rms_v, voltage_ids: tuple[str, ...]):
    """Complex superposition; basis (frequency, source, target), voltage (frequency, source).

    The caller must divide native solver responses by the explicitly established
    basis voltage first. Matching frequency samples and terminations are required.
    Labelled voltage columns are reordered to the basis; missing/extra IDs fail.
    """
    basis = _finite(basis_per_rms_volt, 3, "basis", complex_values=True)
    voltage = _finite(voltage_rms_v, 2, "voltage", complex_values=True)
    _ids(basis_ids); _ids(voltage_ids)
    if (basis.shape[1] != len(basis_ids) or voltage.shape != (basis.shape[0], len(voltage_ids))
            or set(basis_ids) != set(voltage_ids)):
        raise ValueError("voltage basis dimensions or source IDs do not match")
    with np.errstate(over="ignore", invalid="ignore"):
        return _checked(np.einsum("fet,fe->ft", basis, voltage[:, [voltage_ids.index(i) for i in basis_ids]]))


def gain_delay_voltages(frequencies_hz, gains_rms_v, delays_s):
    """exp(-i omega t): positive delay multiplies voltage by exp(+i omega delay).

    Real signed gains (source,) include polarity. No crossover filter is inferred.
    """
    f = _frequencies(frequencies_hz)
    gains = _finite(gains_rms_v, 1, "gains")
    delay = _finite(delays_s, 1, "delays")
    if gains.shape != delay.shape or np.any(delay < 0):
        raise ValueError("one nonnegative delay per gain is required")
    with np.errstate(over="ignore", invalid="ignore"):
        phase = _checked(2 * np.pi * f[:, None] * delay)
        return _checked(gains * np.exp(1j * phase))


def electrical_power_rms(voltage_rms_v, current_rms_a):
    """Return signed channel power (F,D) and net input (F,), in watts.

    Currents are positive into the system. Regenerated channel power remains
    negative; it is not replaced with apparent power or silently clipped.
    """
    voltage = _finite(voltage_rms_v, 2, "voltage", complex_values=True)
    current = _finite(current_rms_a, 2, "current", complex_values=True)
    if voltage.shape != current.shape:
        raise ValueError("voltage and current shapes must match")
    with np.errstate(over="ignore", invalid="ignore"):
        channels = _checked(np.real(voltage * current.conj()))
        return channels, _checked(channels.sum(axis=1))


def pressure_levels_rms(pressure_rms_pa) -> tuple[ScalarMetric, ...]:
    """One-dimensional complex RMS pressures; dB re 20 microPa, no distance scaling.

    Exact zero is explicitly undefined in the finite dB report, never a floor.
    """
    pressure = _finite(pressure_rms_pa, 1, "pressure", complex_values=True)
    amplitude = _checked(abs(pressure))
    return tuple(ScalarMetric(value=float(20 * (np.log10(p) - np.log10(20e-6))), unit="dB")
                 if p > 0 else ScalarMetric(value=None, unit="dB", reason="zero_pressure") for p in amplitude)


class SphereQuadrature(Record):
    # NumPy documents leggauss as tested through degree 100.
    polar_order: Annotated[int, Field(strict=True, ge=2, le=100)] = 16
    azimuth_count: Annotated[int, Field(strict=True, ge=4, le=512)] = 64

    def coordinates_and_weights(self):
        """Unit xyz directions and solid-angle weights, sum 4*pi.

        Gauss-Legendre in z=cos(theta), uniform periodic azimuth without an
        endpoint duplicate. Ordering is polar-major, azimuth-minor.
        """
        z, w = np.polynomial.legendre.leggauss(self.polar_order)
        phi = np.arange(self.azimuth_count) * (2 * np.pi / self.azimuth_count)
        radial = np.sqrt(1 - z*z)
        directions = np.stack((radial[:,None]*np.cos(phi), radial[:,None]*np.sin(phi),
                               np.broadcast_to(z[:,None], (len(z),len(phi)))), axis=-1).reshape(-1,3)
        weights = np.repeat(w * (2*np.pi/self.azimuth_count), self.azimuth_count)
        return directions, weights

    def mean_square_pressure(self, pressure_rms_pa):
        """Full-sphere RMS pressure-squared mean (F,), not acoustic power.

        Samples must be taken at this grid's directions at one common radius.
        This API rejects partial arrays; it does not reconstruct missing angles.
        """
        pressure = _finite(pressure_rms_pa, 2, "sphere pressure", complex_values=True)
        _, weights = self.coordinates_and_weights()
        if pressure.shape[1] != len(weights):
            raise ValueError("pressure must cover the complete declared spherical grid")
        with np.errstate(over="ignore", invalid="ignore"):
            return _checked(np.einsum("fo,o->f", abs(pressure)**2, weights)/(4*np.pi))
