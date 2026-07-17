from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from erhni.config import ConfigError
from erhni.countries import load_country_map
from erhni.years import (
    build_public_exclusion_summary,
    normalize_all,
    normalize_whr,
    record_aqli_missing_fields,
    record_wdi_skipped_identities,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def miniature_crosswalk(tmp_path: Path):
    path = tmp_path / "country_map.csv"
    path.write_text(
        "source,source_name,canonical_iso3,display_name,status,reason\n"
        "whr,Alpha,AAA,Alpha,include,Reviewed direct identity\n"
        "whr,Excluded,,Excluded,exclude,No canonical sovereign identity\n"
        "aqli,AAA,AAA,Alpha,include,Reviewed direct identity\n"
        "wdi,XD,HIC,High income,aggregate,Source metadata aggregate\n",
        encoding="utf-8",
    )
    return load_country_map(path)


@pytest.fixture
def normalized(miniature_crosswalk):
    frame = pd.DataFrame(
        {
            "source_name": ["Alpha", "Alpha", "Alpha"],
            "year": [2016, 2017, 2018],
            "life_ladder": [5.125, 5.25, 5.375],
        }
    )
    return normalize_whr(frame, miniature_crosswalk)


def test_annual_inputs_are_not_imputed(normalized) -> None:
    assert set(normalized.year.unique()) == {2016, 2017, 2018}
    assert not normalized.imputed.any()


def test_normalized_rows_have_unique_country_year_keys(normalized) -> None:
    assert not normalized.duplicated(["iso3", "year"]).any()


def test_detailed_exclusions_preserve_every_dropped_key_and_reason(
    miniature_crosswalk,
) -> None:
    frame = pd.DataFrame(
        {
            "source_name": ["Alpha", "Excluded", "Excluded"],
            "year": [2016, 2016, 2017],
            "life_ladder": [5.0, 4.0, 4.1],
        }
    )
    exclusions: list[dict[str, object]] = []

    normalize_whr(frame, miniature_crosswalk, exclusions=exclusions)

    assert len(exclusions) == 2
    assert {(row["source_key"], row["year"]) for row in exclusions} == {
        ("Excluded", 2016),
        ("Excluded", 2017),
    }
    assert all(row["source"] == "whr" for row in exclusions)
    assert all(row["stage"] == "identity" for row in exclusions)
    assert all(row["reason"] == "No canonical sovereign identity" for row in exclusions)


def test_aqli_blank_annual_fields_receive_terminal_exclusion_evidence(
    miniature_crosswalk,
) -> None:
    raw = pd.DataFrame(
        {
            "id": ["AAA"],
            "who2016": [""],
            "who2017": ["0"],
            "who2018": ["1.25"],
        }
    )
    exclusions: list[dict[str, object]] = []

    record_aqli_missing_fields(
        raw,
        years=(2016, 2017, 2018),
        crosswalk=miniature_crosswalk,
        exclusions=exclusions,
    )

    assert exclusions == [
        {
            "source": "aqli",
            "source_key": "AAA",
            "year": 2016,
            "stage": "value",
            "reason": "Missing direct annual source value.",
        }
    ]


def test_wdi_rows_skipped_by_the_validated_parser_receive_identity_evidence(
    miniature_crosswalk,
) -> None:
    rows = [
        {
            "countryiso3code": "",
            "country": {"id": "XD", "value": "High income"},
            "date": "2016",
        }
    ]
    exclusions: list[dict[str, object]] = []

    record_wdi_skipped_identities(
        rows,
        indicator="SP.POP.TOTL",
        crosswalk=miniature_crosswalk,
        exclusions=exclusions,
    )

    assert exclusions == [
        {
            "source": "wdi",
            "source_key": "XD|SP.POP.TOTL",
            "year": 2016,
            "stage": "identity",
            "reason": "Source metadata aggregate",
        }
    ]


def test_public_exclusion_summary_is_one_suppressed_leaf_partition() -> None:
    rows = []
    for index in range(7):
        rows.append(
            {
                "source": "wdi",
                "source_key": f"aggregate-{index}",
                "year": 2016,
                "stage": "identity",
                "reason": "aggregate",
            }
        )
    for index in range(3):
        rows.append(
            {
                "source": "whr",
                "source_key": f"excluded-{index}",
                "year": 2017,
                "stage": "identity",
                "reason": "no sovereign identity",
            }
        )
    for index in range(2):
        rows.append(
            {
                "source": "aqli",
                "source_key": f"missing-{index}",
                "year": 2018,
                "stage": "value",
                "reason": "missing direct value",
            }
        )

    summary = build_public_exclusion_summary(pd.DataFrame(rows), threshold=5)

    assert list(summary.columns) == ["source", "stage", "reason_group", "count"]
    assert (summary["count"] >= 5).all()
    assert summary["count"].sum() == len(rows)
    assert not summary.duplicated(["source", "stage", "reason_group"]).any()
    assert not {"source_key", "year", "iso3", "reason"} & set(summary.columns)
    assert not summary.astype(str).apply(
        lambda column: column.str.contains("aggregate-0|excluded-0|missing-0").any()
    ).any()


def test_write_policy_fails_closed_for_misclassified_output(tmp_path: Path) -> None:
    bad_policy = tmp_path / "disclosure.toml"
    bad_policy.write_text(
        (ROOT / "config" / "disclosure.toml")
        .read_text(encoding="utf-8")
        .replace(
            'pattern = "data/derived/public/**"\ndisclosure_class = "public_aggregate"',
            'pattern = "data/derived/public/**"\ndisclosure_class = "restricted_derived"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="disclosure"):
        normalize_all(
            method_path=ROOT / "config" / "method.toml",
            sources_path=ROOT / "config" / "sources.toml",
            disclosure_path=bad_policy,
            country_map_path=ROOT / "config" / "country_map.csv",
            regions_path=ROOT / "config" / "regions.csv",
            raw_dir=ROOT / "data" / "raw" / "external",
            derived_dir=tmp_path / "derived",
        )


def test_write_policy_requires_the_planned_public_release_role(tmp_path: Path) -> None:
    bad_policy = tmp_path / "disclosure.toml"
    bad_policy.write_text(
        (ROOT / "config" / "disclosure.toml")
        .read_text(encoding="utf-8")
        .replace(
            'pattern = "data/derived/public/**"\nrelease_role = "public_aggregate"',
            'pattern = "data/derived/not-the-output/**"\nrelease_role = "public_aggregate"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="release role"):
        normalize_all(
            method_path=ROOT / "config" / "method.toml",
            sources_path=ROOT / "config" / "sources.toml",
            disclosure_path=bad_policy,
            country_map_path=ROOT / "config" / "country_map.csv",
            regions_path=ROOT / "config" / "regions.csv",
            raw_dir=ROOT / "data" / "raw" / "external",
            derived_dir=tmp_path / "derived",
        )


def test_real_sources_normalize_to_disclosure_controlled_outputs(tmp_path: Path) -> None:
    result = normalize_all(
        method_path=ROOT / "config" / "method.toml",
        sources_path=ROOT / "config" / "sources.toml",
        disclosure_path=ROOT / "config" / "disclosure.toml",
        country_map_path=ROOT / "config" / "country_map.csv",
        regions_path=ROOT / "config" / "regions.csv",
        raw_dir=ROOT / "data" / "raw" / "external",
        derived_dir=tmp_path / "derived",
    )

    expected = {
        "restricted/happiness_annual.csv",
        "public/wdi_annual.csv",
        "restricted/aqli_annual.csv",
        "restricted/source_exclusions.csv",
        "public/source_exclusion_summary.csv",
        "source_manifest.json",
    }
    assert {path.relative_to(tmp_path / "derived").as_posix() for path in result} == expected

    for relative in expected:
        path = tmp_path / "derived" / relative
        assert path.exists()
        assert b"\r\n" not in path.read_bytes()

    for relative in (
        "restricted/happiness_annual.csv",
        "public/wdi_annual.csv",
        "restricted/aqli_annual.csv",
    ):
        frame = pd.read_csv(tmp_path / "derived" / relative)
        assert not frame.duplicated(["iso3", "year"]).any()
        assert not frame["imputed"].any()

    wdi = pd.read_csv(tmp_path / "derived" / "public/wdi_annual.csv")
    assert set(wdi.loc[wdi["record_type"] == "world", "iso3"]) == {"WLD"}
    assert "WLD" not in set(wdi.loc[wdi["record_type"] == "country", "iso3"])

    detail = pd.read_csv(tmp_path / "derived" / "restricted/source_exclusions.csv")
    summary = pd.read_csv(tmp_path / "derived" / "public/source_exclusion_summary.csv")
    assert detail[["source", "source_key", "year", "stage", "reason"]].notna().all().all()
    assert (summary["count"] >= 5).all()
    assert summary["count"].sum() == len(detail)
    assert not {"source_key", "year", "iso3", "reason"} & set(summary.columns)
