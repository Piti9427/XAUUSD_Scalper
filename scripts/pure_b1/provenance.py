"""Hash the loaded module file. Never hash a path resolved from the process cwd."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def module_sha256(module) -> str:
    file_name = getattr(module, "__file__", None)
    if not file_name:
        raise ValueError(f"loaded module file unavailable: {getattr(module, '__name__', module)}")
    path = Path(file_name).resolve()
    if not path.is_file():
        raise ValueError(f"loaded module file unavailable: {path}")
    return sha256_file(path)
