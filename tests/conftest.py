from functools import lru_cache

import pytest

from decisioniq.dashboard import store
from decisioniq.dashboard.auth import password_hash
from fastapi.testclient import TestClient

from decisioniq.main import app
from services.phishing.predict import _load_bundle


@lru_cache
def test_password_hash():
    return password_hash("Testing-only-passphrase-2026")


def authenticate(test_client, email="admin@example.com", admin=True):
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?)",
            (
                store.uid(),
                email,
                "Test administrator",
                test_password_hash(),
                int(admin),
                store.stamp(),
            ),
        )
    response = test_client.post(
        "/api/auth/login", json={"email": email, "password": "Testing-only-passphrase-2026"}
    )
    assert response.status_code == 200, response.text
    test_client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISIONIQ_DB_PATH", str(tmp_path / "dashboard.sqlite3"))
    # Tests remain reproducible if the developer has a private model installed.
    monkeypatch.setenv("PHISHING_MODEL_PATH", str(tmp_path / "missing-model"))
    _load_bundle.cache_clear()
    with TestClient(app) as test_client:
        authenticate(test_client)
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
