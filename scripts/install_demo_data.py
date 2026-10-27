"""Retrieve checksum-verified public demo CSVs into ignored local directories."""

import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from decisioniq.config import ROOT


def install():
    manifest = json.loads((ROOT / "services/runtime_assets.json").read_text())
    for entry in manifest["files"]:
        target = ROOT / entry["path"]
        if not target.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Invalid demo asset path")
        if target.is_file():
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest == entry["sha256"] and target.stat().st_size == entry["size"]:
                continue
            raise ValueError(
                f"Different local data already exists at {target}; existing data preserved"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/{manifest['repository']}/{manifest['revision']}/{entry['path']}"
        request = Request(url, headers={"User-Agent": "ForeSight-demo-installer/1.0"})
        staged = None
        try:
            with (
                urlopen(request, timeout=60) as response,
                tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream,
            ):
                staged = Path(stream.name)
                digest, total = hashlib.sha256(), 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > entry["size"]:
                        raise ValueError("Unexpected demo data size")
                    digest.update(chunk)
                    stream.write(chunk)
            if total != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError("Demo data verification failed")
            staged.replace(target)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
    print("Public demo data verified locally; data files are excluded from Git.")


if __name__ == "__main__":
    try:
        install()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Demo setup failed: {exc}") from None
