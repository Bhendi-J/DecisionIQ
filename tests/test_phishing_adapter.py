"""Exercise the real local Transformers loader with a tiny untrained test model.

This fixture validates integration only; it is never a deployed phishing model.
"""

import pytest

from services.phishing.predict import _load_bundle


def test_local_transformer_inference_and_truncation(client, monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    path = tmp_path / "test-model"
    path.mkdir()
    vocab = path / "vocab.txt"
    vocab.write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nhello\n")
    tokenizer = transformers.BertTokenizer(vocab_file=str(vocab))
    tokenizer.save_pretrained(path)
    config = transformers.DistilBertConfig(
        vocab_size=len(tokenizer),
        n_layers=1,
        n_heads=2,
        dim=8,
        hidden_dim=16,
        num_labels=2,
        id2label={0: "legitimate", 1: "phishing"},
    )
    model = transformers.DistilBertForSequenceClassification(config)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.classifier.bias.copy_(torch.tensor([0.0, 2.0]))
    model.save_pretrained(path)
    monkeypatch.setenv("PHISHING_MODEL_PATH", str(path))
    _load_bundle.cache_clear()
    response = client.post("/phishing/predict", json={"text": "hello " * 300})
    assert response.status_code == 200
    result = response.json()
    assert result["is_phishing"] is True
    assert result["phishing_probability"] == pytest.approx(0.880797, abs=1e-6)
    assert result["risk_score"] == 88
    assert result["truncated"] is True
    assert client.get("/ready").status_code == 200
    combined = client.post("/assess", json={"finance": {}, "email": {"text": "hello"}}).json()
    assert combined["security_score"] == result["phishing_probability"]
    assert combined["security_coverage"] == "complete"
