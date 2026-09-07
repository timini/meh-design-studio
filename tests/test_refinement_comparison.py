import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('refinement',Path(__file__).resolve().parents[1]/'validation/fixtures/compare_exterior_refinement.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_comparison_preserves_gain_and_phase_changes():
    result=module.compare(np.array([[1.,2.]],dtype=complex),np.array([[1.,2.]])*2*np.exp(1j*np.pi/4))
    assert result['maximum_absolute_magnitude_change_db'] == pytest.approx(20*np.log10(2))
    assert result['maximum_absolute_phase_change_deg'] == pytest.approx(45)
    assert result['relative_matrix_norm_change'] == pytest.approx(np.sqrt(5-2*np.sqrt(2)))


def test_null_policy_retains_weak_sources_and_reports_excluded_samples():
    before=np.array([[1.,0.],[1e-8,0.]],dtype=complex)
    after=before*np.array([[1],[2]])
    result=module.compare(before,after)
    assert result['compared_samples'] == 2
    assert result['excluded_null_samples'] == 2
    assert result['maximum_absolute_magnitude_change_db'] == pytest.approx(20*np.log10(2))
    null=module.compare(before,np.zeros_like(before))
    assert null['compared_samples'] == 0
    assert null['maximum_absolute_phase_change_deg'] is None
