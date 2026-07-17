#!/usr/bin/env python3
"""Preserve the exact 2022 legacy tree outside the active calculation path."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive" / "legacy-2022"
ORIGINAL = ARCHIVE / "original"
BASE_COMMIT = "669f6e2"
ACTIVE_DATA_PREFIXES = ("data/raw/", "data/snapshots/", "data/derived/")
ALLOWED_STAGED_FILES = {
    ".gitignore",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "scripts/archive_legacy.py",
    "tests/test_legacy_archive.py",
}
LEGACY_PATHS = tuple(
    """.ipynb_checkpoints/erhni_2016-checkpoint.ipynb
2016.csv
2017.csv
2018.csv
README.md
data/2015.csv
data/2015.csv:Zone.Identifier
data/2016.csv
data/2016.csv:Zone.Identifier
data/2017.csv
data/2017.csv:Zone.Identifier
data/2018.csv
data/2018.csv:Zone.Identifier
data/2019.csv
data/2019.csv:Zone.Identifier
data/API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv
data/API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv:Zone.Identifier
data/API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv
data/API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv:Zone.Identifier
data/API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv
data/API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv:Zone.Identifier
data/API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv
data/API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv:Zone.Identifier
data/API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv
data/API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv:Zone.Identifier
data/CPI_Data_DashboardExtract.xls
data/CPI_Data_DashboardExtract.xls:Zone.Identifier
data/CPI_Data_DashboardExtract.xlsx
data/CPI_Data_Price.csv
data/Metadata_Country_API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv
data/Metadata_Country_API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv:Zone.Identifier
data/Metadata_Country_API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv
data/Metadata_Country_API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv:Zone.Identifier
data/Metadata_Country_API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv
data/Metadata_Country_API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv:Zone.Identifier
data/Metadata_Country_API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv
data/Metadata_Country_API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv:Zone.Identifier
data/Metadata_Country_API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv
data/Metadata_Country_API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv:Zone.Identifier
data/Metadata_Indicator_API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv
data/Metadata_Indicator_API_EN.ATM.CO2E.KT_DS2_en_csv_v2_4151102.csv:Zone.Identifier
data/Metadata_Indicator_API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv
data/Metadata_Indicator_API_EN.ATM.METH.KT.CE_DS2_en_csv_v2_4157045.csv:Zone.Identifier
data/Metadata_Indicator_API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv
data/Metadata_Indicator_API_EN.ATM.NOXE.KT.CE_DS2_en_csv_v2_4157052.csv:Zone.Identifier
data/Metadata_Indicator_API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv
data/Metadata_Indicator_API_SP.DYN.LE00.IN_DS2_en_csv_v2_4150700.csv:Zone.Identifier
data/Metadata_Indicator_API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv
data/Metadata_Indicator_API_SP.POP.TOTL_DS2_en_csv_v2_4251154.csv:Zone.Identifier
data/aqli_global_data.csv
data/aqli_global_data.csv:Zone.Identifier
data/backup/2017.csv
data/backup/2018.csv
data/backup/2019.csv
data/data.csv
data/data.csv:Zone.Identifier
data/processed/2016.csv
data/processed/2016_test.csv
data/processed/2017.csv
data/processed/2018.csv
data/processed/merged_y.csv
erhni_2016.ipynb
erhni_2016.ipynb:Zone.Identifier
erhni_2016_old.ipynb
merged_y.csv""".splitlines()
)
README = """# Legacy 2022 forensic archive

Every item in `original/` is a byte-preserving forensic copy of the exact
legacy tree at Git commit `669f6e2`. These files are retained only for legacy
reproduction and reconciliation. They are outside the active calculation path
and must not be used as inputs to the reproducible pipeline.

`original-paths.txt` fixes the complete source path set; `sha256.txt` records
the SHA-256 digest of every archived byte sequence.
"""
ALLOWED_ARCHIVE_PATHS = frozenset(
    {
        "archive/legacy-2022/README.md",
        "archive/legacy-2022/original-paths.txt",
        "archive/legacy-2022/sha256.txt",
    }
    | {f"archive/legacy-2022/original/{path}" for path in LEGACY_PATHS}
)


def run_git(*args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=text,
        capture_output=True,
    )


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_legacy_paths() -> None:
    base_paths = tuple(run_git("ls-tree", "-r", "--name-only", BASE_COMMIT).stdout.splitlines())
    if LEGACY_PATHS != base_paths:
        raise RuntimeError("literal legacy path list does not equal the frozen base tree")
    if LEGACY_PATHS != tuple(sorted(LEGACY_PATHS)):
        raise RuntimeError("legacy path list is not deterministically sorted")
    for relative in LEGACY_PATHS:
        pure_path = PurePosixPath(relative)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise RuntimeError(f"legacy path escapes the repository: {relative}")
        if relative.startswith(ACTIVE_DATA_PREFIXES):
            raise RuntimeError(f"legacy path is already in an active data directory: {relative}")


def base_digest(relative: str) -> str:
    content = run_git("show", f"{BASE_COMMIT}:{relative}", text=False).stdout
    return hashlib.sha256(content).hexdigest()


def archive_legacy() -> None:
    validate_legacy_paths()
    digests: dict[str, str] = {}
    for relative in LEGACY_PATHS:
        source = ROOT / relative
        destination = ORIGINAL / relative
        if not source.is_file():
            raise RuntimeError(f"legacy source is missing or already moved: {relative}")
        if destination.exists():
            raise RuntimeError(f"archive destination already exists: {relative}")
        digest = sha256_path(source)
        if digest != base_digest(relative):
            raise RuntimeError(f"legacy source differs from the frozen base tree: {relative}")
        digests[relative] = digest

    for relative in LEGACY_PATHS:
        source = ROOT / relative
        destination = ORIGINAL / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        run_git("mv", "--", relative, str(destination.relative_to(ROOT)))
        if not destination.is_file() or sha256_path(destination) != digests[relative]:
            raise RuntimeError(f"legacy source changed during move: {relative}")

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "README.md").write_text(README, encoding="utf-8")
    (ARCHIVE / "original-paths.txt").write_text("\n".join(LEGACY_PATHS) + "\n", encoding="utf-8")
    (ARCHIVE / "sha256.txt").write_text(
        "".join(f"{digests[path]}  {path}\n" for path in LEGACY_PATHS),
        encoding="utf-8",
    )


def staged_reason(path: str) -> str | None:
    if (
        path.startswith((".venv/", ".pytest_cache/", ".ruff_cache/"))
        or "/__pycache__/" in path
        or path.endswith(".pyc")
        or path in {".coverage", ".DS_Store"}
        or path.startswith("htmlcov/")
    ):
        return "environment or cache path"
    if path.startswith(
        ("data/raw/external/", "data/derived/restricted/", "outputs/restricted/", "outputs/review/")
    ):
        return "ignored restricted path"
    if path in ALLOWED_STAGED_FILES or path in ALLOWED_ARCHIVE_PATHS:
        return None
    return "unclassified generated path"


def check_staged() -> int:
    staged = run_git("diff", "--cached", "--name-only", "--diff-filter=ACMR").stdout.splitlines()
    violations = [(path, staged_reason(path)) for path in staged]
    violations = [(path, reason) for path, reason in violations if reason is not None]
    if not violations:
        return 0
    print("staged paths violate the archive boundary:", file=sys.stderr)
    for path, reason in violations:
        print(f"- {path}: {reason}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-staged", action="store_true")
    args = parser.parse_args()
    if args.check_staged:
        return check_staged()
    archive_legacy()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"archive validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
