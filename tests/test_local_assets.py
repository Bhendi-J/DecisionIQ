"""A source-only checkout must not require committed datasets or publish local assets."""

import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from decisioniq.main import app
from decisioniq.dashboard import store
from scripts import install_demo_data
from services.finance.app.services.finance_service import FinanceService


def test_empty_installation_starts_without_demo_csvs(tmp_path, monkeypatch):
    monkeypatch.setenv("DECISIONIQ_DB_PATH", str(tmp_path / "empty.sqlite3"))
    monkeypatch.setenv("FORESIGHT_DEMO_SALES_PATH", str(tmp_path / "missing.csv"))
    with TestClient(app) as client:
        assert store.rows("SELECT id FROM companies") == []
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Private owner",
                "email": "empty@example.test",
                "password": "Private-test-passphrase",
                "company_name": "Private company",
            },
        )
        assert response.status_code == 201
        dashboard = client.get("/api/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["historical"] == []
        assert dashboard.json()["company"]["source_kind"] == "upload"
        assert store.configured_path("DECISIONIQ_DB_PATH", "").stat().st_mode & 0o777 == 0o600


def test_legacy_finance_uses_saved_model_history_without_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_HISTORY_PATH", str(tmp_path / "missing.csv"))
    service = FinanceService()
    assert len(service.history) == len(service.forecaster.model.history)
    assert list(service.history.columns) == ["ds", "y"]
    assert len(service.get_forecast(30).future) == 30


def test_demo_assets_verify_bytes_and_preserve_different_local_data(tmp_path, monkeypatch):
    content = b"first,second\n1,2\n"
    asset = {
        "path": "services/finance/data/demo_sales.csv",
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    manifest = tmp_path / "services/runtime_assets.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"repository": "example/repo", "revision": "a" * 40, "files": [asset]})
    )
    monkeypatch.setattr(install_demo_data, "ROOT", tmp_path)
    monkeypatch.setattr(
        install_demo_data, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"x" * len(content))
    )
    with pytest.raises(ValueError, match="verification"):
        install_demo_data.install()
    target = tmp_path / asset["path"]
    assert not target.exists()
    monkeypatch.setattr(install_demo_data, "urlopen", lambda *_args, **_kwargs: io.BytesIO(content))
    install_demo_data.install()
    assert target.read_bytes() == content
    monkeypatch.setattr(
        install_demo_data,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("Cached data must not be downloaded"),
    )
    install_demo_data.install()
    target.write_bytes(b"local observations")
    with pytest.raises(ValueError, match="existing data preserved"):
        install_demo_data.install()
    assert target.read_bytes() == b"local observations"
