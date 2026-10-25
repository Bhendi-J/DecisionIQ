import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else ROOT / path
