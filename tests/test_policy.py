import pytest

from norma_qaoa.config import EngineConfig
from norma_qaoa.errors import BackendNotAllowedError
from norma_qaoa.policy import assert_backend_allowed
from norma_qaoa.schema import validate_request


class FakeBackend:
    def __init__(self, kind):
        self.kind = kind
        self.name = f"fake_{kind}"
        self.device_name = "fake"


@pytest.fixture
def req(toy_raw):
    return validate_request(toy_raw)


def test_local_simulator_allowed(req):
    assert_backend_allowed(FakeBackend("local_simulator"), req, EngineConfig())


def test_hardware_always_refused(req):
    for cfg in (EngineConfig(), EngineConfig(allow_external_transfer=True)):
        with pytest.raises(BackendNotAllowedError, match="QPU"):
            assert_backend_allowed(FakeBackend("hardware_qpu"), req, cfg)


def test_cloud_emulator_needs_transfer_approval(req):
    with pytest.raises(BackendNotAllowedError, match="external"):
        assert_backend_allowed(FakeBackend("cloud_emulator"), req, EngineConfig())
    assert_backend_allowed(FakeBackend("cloud_emulator"), req, EngineConfig(allow_external_transfer=True))


def test_unknown_kind_refused(req):
    with pytest.raises(BackendNotAllowedError):
        assert_backend_allowed(FakeBackend("gpu_magic"), req, EngineConfig())


def test_allow_qpu_request_refused_even_if_validation_bypassed(req):
    bad = req.model_copy(update={"execution": req.execution.model_copy(update={"allow_qpu": True})})
    with pytest.raises(BackendNotAllowedError):
        assert_backend_allowed(FakeBackend("local_simulator"), bad, EngineConfig())
