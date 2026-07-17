"""Small SHA-256 helpers used by source acquisition and evidence manifests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest for an in-memory payload."""

    return sha256(content).hexdigest()


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA-256 digest for a file without loading it at once."""

    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
