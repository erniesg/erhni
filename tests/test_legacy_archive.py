from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive" / "legacy-2022"
ORIGINAL = ARCHIVE / "original"
PATH_MANIFEST = ARCHIVE / "original-paths.txt"
HASH_MANIFEST = ARCHIVE / "sha256.txt"
SCRIPT = ROOT / "scripts" / "archive_legacy.py"
BASE_COMMIT = "669f6e2"
ACTIVE_DATA_PREFIXES = ("data/raw/", "data/snapshots/", "data/derived/")


def git(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def read_paths() -> list[str]:
    return [line for line in PATH_MANIFEST.read_text(encoding="utf-8").splitlines() if line]


def read_hashes() -> dict[str, str]:
    return {
        path: digest
        for digest, path in (
            line.split("  ", maxsplit=1)
            for line in HASH_MANIFEST.read_text(encoding="utf-8").splitlines()
            if line
        )
    }


def test_legacy_archive_is_an_exact_byte_preserving_copy_of_the_base_tree() -> None:
    expected_paths = git("ls-tree", "-r", "--name-only", BASE_COMMIT).stdout.splitlines()
    paths = read_paths()
    hashes = read_hashes()

    assert paths == expected_paths
    assert list(hashes) == expected_paths
    assert not any(path.startswith(ACTIVE_DATA_PREFIXES) for path in paths)

    for path in paths:
        archived = ORIGINAL / path
        assert archived.is_file(), path
        assert not (ROOT / path).exists(), path
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == hashes[path]


@pytest.mark.parametrize(
    "staged_path",
    [
        ".pytest_cache/blocked",
        "data/derived/restricted/blocked.csv",
        "outputs/generated.csv",
        "archive/legacy-2022/review-output.csv",
        "archive/legacy-2022/notes/review-output.csv",
        "archive/legacy-2022/original/unlisted.csv",
    ],
)
def test_check_staged_rejects_non_source_paths(staged_path: str, tmp_path: Path) -> None:
    if not SCRIPT.exists():
        pytest.skip("archive validator is not implemented yet")

    index = tmp_path / "index"
    env = os.environ | {"GIT_INDEX_FILE": str(index)}
    git("read-tree", "HEAD", env=env)
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=ROOT,
        input="blocked\n",
        text=True,
        check=True,
        capture_output=True,
    ).stdout.strip()
    git("update-index", "--add", "--cacheinfo", f"100644,{blob},{staged_path}", env=env)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check-staged"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert staged_path in result.stderr


def test_check_staged_accepts_only_the_exact_archive_inventory(tmp_path: Path) -> None:
    if not SCRIPT.exists():
        pytest.skip("archive validator is not implemented yet")

    index = tmp_path / "index"
    env = os.environ | {"GIT_INDEX_FILE": str(index)}
    git("read-tree", "HEAD", env=env)
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=ROOT,
        input="validator\n",
        text=True,
        check=True,
        capture_output=True,
    ).stdout.strip()
    allowed_paths = [
        "scripts/archive_legacy.py",
        "archive/legacy-2022/README.md",
        "archive/legacy-2022/original-paths.txt",
        "archive/legacy-2022/sha256.txt",
        *(f"archive/legacy-2022/original/{path}" for path in read_paths()),
    ]
    for path in allowed_paths:
        git(
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},{path}",
            env=env,
        )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check-staged"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
