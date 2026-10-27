"""Verify atomic, checksum-checked artifact installation without network downloads."""

import hashlib
import json

import pytest

from scripts import install_phishing_model as installer


@pytest.fixture
def release(tmp_path, monkeypatch):
    data = b'{"model_type":"distilbert"}'
    entry = {"name": "config.json", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"revision": "a" * 40, "files": [entry]}))
    monkeypatch.setattr(installer, "MANIFEST", manifest)
    monkeypatch.delenv("PHISHING_MODEL_PATH", raising=False)
    return tmp_path / "installed", data, entry


def test_verified_install_is_atomic_and_repeated_launch_is_offline(release, monkeypatch):
    target, data, _ = release

    def retrieve(manifest, entry, path):
        assert not target.exists()
        path.write_bytes(data)

    monkeypatch.setattr(installer, "retrieve", retrieve)
    assert installer.install(target) == target
    assert (target / "config.json").read_bytes() == data
    assert (target / "provenance.json").is_file()
    monkeypatch.setattr(
        installer, "retrieve", lambda *_: pytest.fail("Already installed models must not download")
    )
    installer.install(target)


def test_wrong_checksum_never_publishes_an_incomplete_model(release, monkeypatch):
    target, _, entry = release
    monkeypatch.setattr(installer, "git_lfs_cache", lambda *_: None)
    import io

    monkeypatch.setattr(
        installer, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"x" * entry["size"])
    )
    manifest = json.loads(installer.MANIFEST.read_text())
    manifest.update(repository="example/repo", revision="a" * 40, source_path="model")
    installer.MANIFEST.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Checksum"):
        installer.install(target)
    assert not target.exists()


def test_existing_different_artifacts_are_preserved(release):
    target, _, _ = release
    target.mkdir()
    path = target / "config.json"
    path.write_text("custom model")
    with pytest.raises(ValueError, match="different or incomplete"):
        installer.install(target)
    assert path.read_text() == "custom model"


def test_lfs_pointer_cannot_be_mistaken_for_weight_bytes(tmp_path):
    path = tmp_path / "model.safetensors"
    path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1000\n")
    assert not installer.matches(path, {"size": 1000, "sha256": "abc"})
