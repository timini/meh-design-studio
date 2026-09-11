"""Sampled on-axis acoustic handover, grouped by excitation channel.

Each channel contribution retains the full mutually coupled driver response.
These are pressure contributions, not independent diaphragm powers.
"""
import numpy as np


def validate_handover_grid(frequencies, mid_start_hz, window):
    low,high=window
    if not mid_start_hz<low<high:
        raise ValueError('acoustic handover bounds must increase above the mid high-pass')
    if any(value not in frequencies for value in (mid_start_hz,low,high)):
        raise ValueError('acoustic handover requires explicit mid-start and both handover-boundary frequency samples')


def acoustic_handover(frequencies, mid_pressure, hf_pressure, mid_start_hz, window):
    """Require mid dominance through the lower bound and HF from the upper bound."""
    f=np.asarray(frequencies,dtype=float)
    mid=np.asarray(mid_pressure,dtype=complex);hf=np.asarray(hf_pressure,dtype=complex)
    if (f.ndim!=1 or not len(f) or mid.shape!=f.shape or hf.shape!=f.shape
            or not np.isfinite(f).all() or np.any(f<=0) or np.any(np.diff(f)<=0)
            or not np.isfinite(mid).all() or not np.isfinite(hf).all()):
        raise ValueError('finite increasing frequencies and matching channel pressure vectors required')
    validate_handover_grid(f,mid_start_hz,window)
    low,high=window;mid_mask=(f>=mid_start_hz)&(f<=low);hf_mask=f>=high
    a,b=abs(mid),abs(hf)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('channel pressure magnitude must remain finite')
    # Test actual amplitudes. The finite dB display floor must not make nulls pass.
    mid_pass=(a>=b)&(a>0);hf_pass=(b>=a)&(b>0)
    floor=np.finfo(float).tiny
    ratio=np.clip(20*(np.log10(np.maximum(a,floor))-np.log10(np.maximum(b,floor))),-120.,120.)
    return {'passed':bool(mid_pass[mid_mask].all() and hf_pass[hf_mask].all()),
        'definition':'on-axis pressure grouped by excitation channel, including mutually induced driver motion',
        'mid_dominant_through_hz':low,'hf_dominant_from_hz':high,
        'frequencies_hz':f.tolist(),'mid_over_hf_db':ratio.tolist(),
        'ratio_display_clip_db':120.,'mid_channel_null':(a==0).tolist(),'hf_channel_null':(b==0).tolist(),
        'mid_dominance_failed_hz':f[mid_mask&~mid_pass].tolist(),
        'hf_dominance_failed_hz':f[hf_mask&~hf_pass].tolist(),
        'exact_crossover_frequency_inferred':False,'off_axis_handover_validated':False}
