import pytest
from fastapi.testclient import TestClient

from decisioniq.main import app
from services.phishing.predict import _load_bundle


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Tests remain reproducible if the developer has a private model installed.
    monkeypatch.setenv("PHISHING_MODEL_PATH", str(tmp_path / "missing-model"))
    _load_bundle.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    _load_bundle.cache_clear()


@pytest.fixture
def login():
    return {
        "login_hour": 3,
        "failed_attempts": 8,
        "new_device": 1,
        "login_frequency": 1,
        "location_difference": 1,
    }
