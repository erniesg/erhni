from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from erhni.config import load_sources
from erhni.countries import (
    CountryMapError,
    collect_source_identities,
    load_country_map,
    load_regions,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def crosswalk():
    return load_country_map(ROOT / "config" / "country_map.csv")


@pytest.fixture(scope="module")
def raw_names():
    sources = load_sources(ROOT / "config" / "sources.toml")
    return collect_source_identities(
        sources,
        repository_root=ROOT,
        raw_dir=ROOT / "data" / "raw" / "external",
    )


def test_sensitive_territories_are_not_sovereign_aliases(crosswalk) -> None:
    assert crosswalk.resolve("whr", "North Cyprus").status == "exclude"
    assert crosswalk.resolve("whr", "North Cyprus").iso3 is None
    assert crosswalk.resolve("whr", "Somaliland region").status == "exclude"
    assert crosswalk.resolve("whr", "Somaliland region").iso3 is None


@pytest.mark.parametrize(
    ("source_name", "iso3"),
    [
        ("Ivory Coast", "CIV"),
        ("Trinidad and Tobago", "TTO"),
        ("Turkey", "TUR"),
        ("Vietnam", "VNM"),
    ],
)
def test_whr_aliases_are_explicit(crosswalk, source_name: str, iso3: str) -> None:
    decision = crosswalk.resolve("whr", source_name)
    assert decision.status == "include"
    assert decision.iso3 == iso3
    assert "explicit" in decision.reason.lower()


def test_the_two_congos_remain_distinct(crosswalk) -> None:
    assert crosswalk.resolve("whr", "Congo (Kinshasa)").iso3 == "COD"
    assert crosswalk.resolve("whr", "Congo (Brazzaville)").iso3 == "COG"


def test_taiwan_has_a_documented_explicit_decision(crosswalk) -> None:
    for source, source_name in (("whr", "Taiwan Province of China"), ("aqli", "TWN")):
        decision = crosswalk.resolve(source, source_name)
        assert decision.status in {"include", "exclude"}
        assert decision.reason
        assert "separately reported" in decision.reason.lower()


@pytest.mark.parametrize("source", ["aqli", "wdi"])
@pytest.mark.parametrize("iso3", ["CIV", "TTO", "TUR", "VNM", "COD", "COG"])
def test_source_codes_require_explicit_identity_decisions(
    crosswalk, source: str, iso3: str
) -> None:
    decision = crosswalk.resolve(source, iso3)
    assert decision.status == "include"
    assert decision.iso3 == iso3


def test_every_source_name_has_one_explicit_decision(raw_names, crosswalk) -> None:
    decisions = crosswalk.coverage(raw_names)
    assert decisions.missing == ()
    assert decisions.duplicate == ()


def test_country_map_rejects_duplicate_source_decisions(tmp_path: Path) -> None:
    path = tmp_path / "country_map.csv"
    pd.DataFrame(
        [
            ["whr", "Example", "EXA", "Example", "include", "reviewed"],
            ["whr", "Example", "EXA", "Example", "include", "reviewed"],
        ],
        columns=(
            "source",
            "source_name",
            "canonical_iso3",
            "display_name",
            "status",
            "reason",
        ),
    ).to_csv(path, index=False)

    with pytest.raises(CountryMapError, match="duplicate"):
        load_country_map(path)


def test_country_map_rejects_blank_decisions(tmp_path: Path) -> None:
    path = tmp_path / "country_map.csv"
    path.write_text(
        "source,source_name,canonical_iso3,display_name,status,reason\n"
        "whr,Example,EXA,Example,,\n",
        encoding="utf-8",
    )

    with pytest.raises(CountryMapError, match="blank|status"):
        load_country_map(path)


def test_country_map_rejects_aggregate_without_a_canonical_code(
    tmp_path: Path,
) -> None:
    path = tmp_path / "country_map.csv"
    path.write_text(
        "source,source_name,canonical_iso3,display_name,status,reason\n"
        "wdi,XD,,High income,aggregate,Reviewed aggregate identity\n",
        encoding="utf-8",
    )

    with pytest.raises(CountryMapError, match="blank ISO3"):
        load_country_map(path)


def test_regions_have_one_row_for_every_included_identity(crosswalk) -> None:
    regions = load_regions(ROOT / "config" / "regions.csv")
    included = {decision.iso3 for decision in crosswalk.decisions if decision.status == "include"}

    assert not regions["iso3"].duplicated().any()
    assert set(regions["iso3"]) == included
    assert regions[["source_region", "display_region"]].notna().all().all()
    assert regions[["source_region", "display_region"]].ne("").all().all()
