import pytest
from meh_studio.domain import DriverRevision, Provenance, SourceModel


@pytest.fixture
def source():
    return SourceModel(re_ohm=6, le_h=0, bl_n_a=4, mmd_kg=0.01,
                       cms_m_n=0.001, rms_ns_m=1, sd_m2=0.003,
                       provenance=Provenance(kind="synthetic", source="independent test circuit",
                                             permission="private_import"))


@pytest.fixture
def driver(source):
    return DriverRevision(id="synthetic-test", revision=1, manufacturer="Test fixture only",
                          model="Not a commercial driver", outer_diameter_m=0.09,
                          cutout_diameter_m=0.075, depth_m=0.04,
                          provenance=source.provenance, source_model=source)
