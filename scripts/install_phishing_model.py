"""Install the pinned contributor model with size and SHA-256 verification."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from decisioniq.config import ROOT, configured_path

MANIFEST = ROOT / "services/phishing/model_manifest.json"
DEFAULT_PATH = ROOT / "services/phishing/models/phishing_distilbert"


def matches(path, entry):
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return digest == entry["sha256"]


def git_lfs_cache(entry):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    digest = entry["sha256"]
    candidate = git_dir / "lfs/objects" / digest[:2] / digest[2:4] / digest
    return candidate if matches(candidate, entry) else None


def artifact_url(manifest, entry):
    base = (
        "https://media.githubusercontent.com/media"
        if entry["name"].endswith(".safetensors")
        else "https://raw.githubusercontent.com"
    )
    return f"{base}/{manifest['repository']}/{manifest['revision']}/{manifest['source_path']}/{entry['name']}"


def retrieve(manifest, entry, target):
    cached = git_lfs_cache(entry)
    if cached:
        shutil.copyfile(cached, target)
    else:
        request = Request(
            artifact_url(manifest, entry), headers={"User-Agent": "ForeSight-model-installer/1.0"}
        )
        with urlopen(request, timeout=120) as response, target.open("wb") as stream:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > entry["size"]:
                    raise ValueError(f"Unexpected size for {entry['name']}; installation stopped")
                stream.write(chunk)
    if not matches(target, entry):
        raise ValueError(
            f"Checksum/size verification failed for {entry['name']}; no model installed"
        )


def install(target=None):
    target = Path(target) if target else configured_path("PHISHING_MODEL_PATH", str(DEFAULT_PATH))
    if target.resolve() != DEFAULT_PATH.resolve() and os.getenv("PHISHING_MODEL_PATH"):
        if not (target / "config.json").is_file():
            raise ValueError(
                "PHISHING_MODEL_PATH must point to your extracted, complete saved model directory"
            )
        print(
            "Using the operator-supplied local phishing model; the contributor export is not downloaded."
        )
        return target
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["files"]
    if any(Path(item["name"]).name != item["name"] for item in entries):
        raise ValueError("Model manifest contains an invalid filename")
    if target.exists():
        if not all(matches(target / item["name"], item) for item in entries):
            raise ValueError(
                "The default model directory contains a different or incomplete export. "
                "Preserve it elsewhere and set PHISHING_MODEL_PATH for a custom model, "
                "or remove the incomplete directory before installing the pinned release."
            )
        (target / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Verified phishing model {manifest['revision'][:7]} (already installed).")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    # Nothing becomes visible to inference until every file has passed verification.
    with tempfile.TemporaryDirectory(prefix=".phishing-install-", dir=target.parent) as staging:
        staging = Path(staging)
        for entry in entries:
            print(f"Installing {entry['name']} ({entry['size']:,} bytes)…", flush=True)
            retrieve(manifest, entry, staging / entry["name"])
        (staging / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # Another installer may have completed while this one downloaded the files.
        if target.exists():
            if not all(matches(target / item["name"], item) for item in entries):
                raise ValueError(
                    "Model directory changed during installation; existing files preserved"
                )
        else:
            staging.rename(target)
    print(f"Installed verified phishing model {manifest['revision'][:7]}.")
    return target


def main():
    try:
        install()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Phishing model setup failed: {exc}") from None


if __name__ == "__main__":
    main()
