"""Independent linear reference equations, not a three-dimensional horn solver.

Convention: RMS complex amplitudes, exp(-i omega t), SI units.
Mechanical loads are force/velocity impedances, including transformed acoustic
loads. No radiation or dry-to-air-loaded mass correction is added implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .domain import SourceModel


def cavity_modes(lengths_m: tuple[float, float, float], max_hz: float,
                 sound_speed_m_s: float = 343.0) -> list[dict]:
    """Exact nonzero eigenfrequencies of an ideal rigid rectangular cavity."""
    if len(lengths_m) != 3 or not all(math.isfinite(x) and x > 0 for x in lengths_m):
        raise ValueError("three positive finite cavity lengths are required")
    if not all(math.isfinite(x) and x > 0 for x in (max_hz, sound_speed_m_s)):
        raise ValueError("frequency and sound speed must be positive and finite")
    extents = [2 * (max_hz / sound_speed_m_s) * length for length in lengths_m]
    if any(not math.isfinite(x) or x > 1_000_000 for x in extents):
        raise ValueError("reference request exceeds the mode enumeration budget")
    # Enumerate conservatively; a rounded-down integer extent must not drop a mode.
    limits = [math.ceil(x) for x in extents]
    if math.prod(n + 1 for n in limits) > 1_000_000:
        raise ValueError("reference request exceeds one million candidate modes")
    modes = []
    for nx in range(limits[0] + 1):
        for ny in range(limits[1] + 1):
            for nz in range(limits[2] + 1):
                if (nx, ny, nz) == (0, 0, 0):
                    continue
                f = sound_speed_m_s / 2 * math.hypot(
                    *(n / length for n, length in zip((nx, ny, nz), lengths_m)))
                if f <= math.nextafter(max_hz, math.inf):
                    modes.append({"indices": [nx, ny, nz], "frequency_hz": f})
    return sorted(modes, key=lambda m: (m["frequency_hz"], m["indices"]))


@dataclass(frozen=True)
class CircuitResponse:
    current_a: np.ndarray
    velocity_m_s: np.ndarray
    electrical_input_w: np.ndarray
    coil_loss_w: np.ndarray
    mechanical_loss_w: np.ndarray
    load_power_w: np.ndarray


def solve_driver_circuit(sources: tuple[SourceModel, ...], frequencies_hz,
                         voltage_rms_v, mechanical_load=None) -> CircuitResponse:
    """Solve coupled linear electromechanical equations for prescribed voltages.

    Shapes: frequency (F,), voltage (F,D), mechanical load (F,D,D).
    A zero-voltage source remains connected and mechanically reactive.
    Open-circuit terminations require a different circuit formulation.
    """
    f = np.asarray(frequencies_hz, dtype=float)
    v = np.asarray(voltage_rms_v, dtype=complex)
    d = len(sources)
    if not d or f.ndim != 1 or not len(f) or not np.all(np.isfinite(f)) or np.any(f <= 0):
        raise ValueError("nonempty positive finite frequency vector and sources required")
    if np.any(np.diff(f) <= 0):
        raise ValueError("frequencies must be strictly increasing")
    if v.shape != (len(f), d) or not np.all(np.isfinite(v)):
        raise ValueError("voltage must be finite with shape (frequency, driver)")
    zload = (np.zeros((len(f), d, d), dtype=complex) if mechanical_load is None
             else np.asarray(mechanical_load, dtype=complex))
    if zload.shape != (len(f), d, d) or not np.all(np.isfinite(zload)):
        raise ValueError("mechanical load must be finite with shape (frequency, driver, driver)")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            w = 2 * np.pi * f[:, None]
            re = np.array([s.re_ohm for s in sources])
            bl = np.array([s.bl_n_a for s in sources])
            rms = np.array([s.rms_ns_m for s in sources])
            ze = re - 1j * w * np.array([s.le_h for s in sources])
            zm = rms - 1j * (w * np.array([s.mmd_kg for s in sources])
                             - 1 / (w * np.array([s.cms_m_n for s in sources])))
            matrix = zload.copy()
            matrix[:, np.arange(d), np.arange(d)] += zm + bl**2 / ze
            velocity = np.linalg.solve(matrix, (bl * v / ze)[..., None])[..., 0]
            current = (v - bl * velocity) / ze
            if not np.all(np.isfinite(velocity)) or not np.all(np.isfinite(current)):
                raise ValueError("circuit solution is non-finite")
            force = np.einsum("fij,fj->fi", zload, velocity)
            result = CircuitResponse(
                current_a=current, velocity_m_s=velocity,
                electrical_input_w=np.real(v * current.conj()).sum(axis=1),
                coil_loss_w=(re * abs(current)**2).sum(axis=1),
                mechanical_loss_w=(rms * abs(velocity)**2).sum(axis=1),
                load_power_w=np.real(force * velocity.conj()).sum(axis=1),
            )
            for values in (result.electrical_input_w, result.coil_loss_w,
                           result.mechanical_loss_w, result.load_power_w):
                if not np.all(np.isfinite(values)):
                    raise ValueError("circuit power result is non-finite")
            return result
    except FloatingPointError as exc:
        raise ValueError("circuit calculation exceeded finite numerical range") from exc
