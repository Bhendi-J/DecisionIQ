"""Opt-in checks against the actual pinned contributor weights, never a mock fixture."""

import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from decisioniq.config import ROOT
from decisioniq.dashboard import store
from decisioniq.main import app
from services.phishing.predict import _load_bundle

pytestmark = pytest.mark.skipif(
    os.getenv("PHISHING_RUN_ARTIFACT_TESTS") != "1",
    reason="Enable PHISHING_RUN_ARTIFACT_TESTS=1 after installing the pinned contributor model",
)


def test_contributor_artifact_matches_pinned_weights():
    manifest = json.loads((ROOT / "services/phishing/model_manifest.json").read_text())
    path = ROOT / "services/phishing/models/phishing_distilbert/model.safetensors"
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == next(
            f["sha256"] for f in manifest["files"] if f["name"] == path.name
        )


def test_actual_email_model_is_connected_to_company_api(tmp_path, monkeypatch):
    import torch

    monkeypatch.setenv("DECISIONIQ_DB_PATH", str(tmp_path / "trained-api.sqlite3"))
    monkeypatch.setenv(
        "PHISHING_MODEL_PATH", str(ROOT / "services/phishing/models/phishing_distilbert")
    )
    _load_bundle.cache_clear()
    try:
        with TestClient(app) as client:
            account = client.post(
                "/api/auth/register",
                json={
                    "name": "Artifact check",
                    "email": "artifact@example.test",
                    "password": "Artifact-test-passphrase",
                    "company_name": "Artifact workspace",
                },
            ).json()
            client.headers["X-CSRF-Token"] = account["csrf_token"]
            assert client.get("/health").json()["models"]["phishing"]["status"] == "ready"
            assert client.get("/ready").status_code == 200
            assert client.get("/api/dashboard").json()["phishing_status"] == "ready"
            text = "Team meeting tomorrow at 10 AM. Please review the agenda before joining."
            tokenizer, model = _load_bundle()
            inputs = tokenizer(
                text, return_tensors="pt", truncation=True, padding=True, max_length=256
            )
            with torch.inference_mode():
                native = float(torch.softmax(model(**inputs).logits, dim=-1)[0][1])
            response = client.post("/api/security/email", json={"text": text})
            assert response.status_code == 200
            assert response.json()["phishing_probability"] == pytest.approx(native, abs=1e-6)
            saved = store.rows(
                "SELECT payload,result FROM events WHERE company_id=?", (account["company_id"],)
            )
            assert len(saved) == 1 and text not in saved[0]["payload"]
            assert (
                json.loads(saved[0]["result"])["phishing_probability"]
                == response.json()["phishing_probability"]
            )
    finally:
        _load_bundle.cache_clear()
