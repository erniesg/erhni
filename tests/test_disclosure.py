from __future__ import annotations

from pathlib import Path

import pytest

from erhni.config import ConfigError
from erhni.disclosure import (
    classify_path,
    load_disclosure,
    release_role_for_path,
    validate_staged_path,
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("data/raw/external/whr_2022_data_for_table_2_1.xls", "restricted_source"),
        ("data/raw/external/aqli_2025_gadm0.csv", "restricted_source"),
        ("data/snapshots/wdi/SP.POP.TOTL.json", "public_snapshot"),
        ("data/snapshots/edgar/pm25.csv", "public_snapshot"),
        ("data/derived/restricted/happiness_annual.csv", "restricted_derived"),
        ("data/derived/restricted/aqli_annual.csv", "restricted_derived"),
        ("data/derived/restricted/exclusions.csv", "restricted_derived"),
        ("outputs/restricted/country_year.csv", "restricted_derived"),
        ("outputs/restricted/rankings.csv", "restricted_derived"),
        ("outputs/restricted/sensitivities.csv", "restricted_derived"),
        ("outputs/restricted/rank_comparison.csv", "restricted_derived"),
        ("outputs/review/figures/country_rankings.svg", "review_only"),
        ("outputs/review/tables/country_rankings.csv", "review_only"),
        ("data/derived/public/global_summary.csv", "public_aggregate"),
        ("outputs/public/global_summary.csv", "public_aggregate"),
        ("data/derived/source_manifest.json", "public_aggregate"),
    ],
)
def test_every_planned_data_artifact_has_one_disclosure_class(
    disclosure, path: str, expected: str
) -> None:
    assert classify_path(disclosure, path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/erhni/config.py", "public_code"),
        ("tests/test_config.py", "public_code"),
        ("scripts/archive_legacy.py", "public_code"),
        ("config/method.toml", "public_config"),
        ("docs/method.md", "public_documentation"),
        ("data/derived/source_manifest.json", "public_evidence"),
        ("data/snapshots/wdi/SP.POP.TOTL.json", "public_snapshot"),
        ("outputs/public/global_summary.csv", "public_aggregate"),
    ],
)
def test_every_staged_path_has_exactly_one_release_role(
    disclosure, path: str, expected: str
) -> None:
    assert release_role_for_path(disclosure, path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/external/whr_2022_data_for_table_2_1.xls",
        "data/derived/restricted/happiness_annual.csv",
        "outputs/review/tables/country_rankings.csv",
        "outputs/generated.csv",
    ],
)
def test_restricted_review_and_unknown_paths_cannot_be_staged(disclosure, path: str) -> None:
    with pytest.raises(ConfigError):
        validate_staged_path(disclosure, path)


def test_source_manifest_is_public_aggregate_evidence(disclosure) -> None:
    path = "data/derived/source_manifest.json"
    assert release_role_for_path(disclosure, path) == "public_evidence"
    assert classify_path(disclosure, path) == "public_aggregate"
    assert validate_staged_path(disclosure, path) == "public_evidence"


def test_source_manifest_fails_closed_if_its_disclosure_rule_is_removed(tmp_path) -> None:
    policy_path = tmp_path / "disclosure.toml"
    manifest_rule = """[[disclosure_rule]]
pattern = "data/derived/source_manifest.json"
disclosure_class = "public_aggregate"

"""
    policy_path.write_text(
        Path("config/disclosure.toml").read_text(encoding="utf-8").replace(manifest_rule, ""),
        encoding="utf-8",
    )
    policy = load_disclosure(policy_path)
    path = "data/derived/source_manifest.json"

    with pytest.raises(ConfigError, match="disclosure"):
        classify_path(policy, path)
    with pytest.raises(ConfigError, match="disclosure"):
        release_role_for_path(policy, path)
    with pytest.raises(ConfigError, match="disclosure"):
        validate_staged_path(policy, path)


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/external/whr_2022_data_for_table_2_1.xls",
        "data/derived/restricted/happiness_annual.csv",
        "outputs/review/tables/country_rankings.csv",
    ],
)
def test_release_role_api_rejects_nonpublic_scientific_classes_even_if_policy_maps_them(
    tmp_path, path: str
) -> None:
    policy_path = tmp_path / "disclosure.toml"
    policy_path.write_text(
        Path("config/disclosure.toml").read_text(encoding="utf-8")
        + f"""
[[release_role_rule]]
pattern = \"{path.rsplit('/', 1)[0]}/**\"
release_role = \"public_evidence\"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="non-public disclosure"):
        release_role_for_path(load_disclosure(policy_path), path)


def test_disclosure_is_fail_closed_for_unclassified_artifacts(disclosure) -> None:
    with pytest.raises(ConfigError, match="disclosure"):
        classify_path(disclosure, "data/derived/unclassified.csv")
    with pytest.raises(ConfigError, match="release role"):
        release_role_for_path(disclosure, "paper/draft.docx")
