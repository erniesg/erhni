from __future__ import annotations

from pathlib import Path

import pytest

from erhni.config import ConfigError, load_method, load_sources


def test_primary_method_pins_universes(method) -> None:
    assert method.years == (2016, 2017, 2018)
    assert method.burden_universe == "aqli_full_wdi_population"
    assert method.allocation_denominator == "wdi_wld"
    assert method.happiness_weight_universe == "balanced_analysis_panel"
    assert method.ranking_universe == "balanced_complete_case"
    assert method.max_abs_wld_reconciliation_share == 0.05


def test_primary_weight_is_net_and_gross_is_only_a_sensitivity(method) -> None:
    assert method.headline_weight == "population_weighted_net_happiness"
    assert method.neutral_point == 5.0
    assert method.gross_penalty_sensitivity is True
    assert method.nonpositive_weight == "error"


def test_ghg_family_is_explicit_and_has_no_fallback(method) -> None:
    assert method.primary_ghg_family == "edgar_ar5_excl_lulucf"
    assert method.ghg_total_indicator == "EN.GHG.ALL.MT.CE.AR5"
    assert method.ghg_fallback_family is None


def test_source_locks_pin_retrievals_hashes_and_durable_destinations(sources) -> None:
    expected = {
        "whr_2022_table_2_1": (
            "https://web.archive.org/web/20220715181822id_/https://happiness-report.s3.amazonaws.com/2022/DataForTable2.1.xls",
            "f118e7f606f091b978edc674242b491b79ee37bea6cb2b5243f805f5f39ccfa4",
            "data/raw/external/whr_2022_data_for_table_2_1.xls",
        ),
        "aqli_2025_gadm0": (
            "https://cdn.sanity.io/files/3o8tp68r/production/4d1bc319df6657d5ced2fdfc38604e0da13cc812.csv",
            "65bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73",
            "data/raw/external/aqli_2025_gadm0.csv",
        ),
        "wdi_population": (
            "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?date=2016:2018&format=json&per_page=20000",
            "37c342714703650a21a159153626e42f114005220d77e60eeff835c70b95bd66",
            "data/snapshots/wdi/SP.POP.TOTL.json",
        ),
        "wdi_life_expectancy": (
            "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN?date=2016:2018&format=json&per_page=20000",
            "5bf9cb1fab1a58a5eef347da0fe0356fb80ff1539171deebc41455f8ecf47693",
            "data/snapshots/wdi/SP.DYN.LE00.IN.json",
        ),
        "wdi_ghg_total": (
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.ALL.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "68207c08d82f19942abb8a4437449079a4d46a645d4136ccb7698ab983d79b58",
            "data/snapshots/wdi/EN.GHG.ALL.MT.CE.AR5.json",
        ),
        "wdi_ghg_co2": (
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "a97b7839bc570ff012478ca1db8661c4ae4ca502ee4d8188a86ea922eed0f8d0",
            "data/snapshots/wdi/EN.GHG.CO2.MT.CE.AR5.json",
        ),
        "wdi_ghg_ch4": (
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "5a5dbd12458e21022f3264faa43349dd94a061a68fb552889f5c6d806605eae4",
            "data/snapshots/wdi/EN.GHG.CH4.MT.CE.AR5.json",
        ),
        "wdi_ghg_n2o": (
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "e862b242cccfc9b78ba92c2f2341e5da888061d00629ab74ab5d347202ee2b79",
            "data/snapshots/wdi/EN.GHG.N2O.MT.CE.AR5.json",
        ),
        "wdi_country_metadata": (
            "https://api.worldbank.org/v2/country?format=json&per_page=400",
            "d29d57f8adf954c5e2a1520a02fb2c7b45575d8db3bd327a9dff47d66914231c",
            "data/snapshots/wdi/country.metadata.json",
        ),
        "wdi_archive_total_ghg": (
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.GHGT.KT.CE?downloadformat=csv",
            "ba749f90dc55b7373c3b7b7eab0cd7c8eb5dac9a070c6a746225c90f94271ba8",
            "data/snapshots/wdi_archive/EN.ATM.GHGT.KT.CE.zip",
        ),
        "wdi_archive_ch4": (
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.METH.KT.CE?downloadformat=csv",
            "c1bf878a5bad6151bde1258e5f4c25fddfa9a5862180927c6e25e2127d2fbb54",
            "data/snapshots/wdi_archive/EN.ATM.METH.KT.CE.zip",
        ),
        "wdi_archive_n2o": (
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.NOXE.KT.CE?downloadformat=csv",
            "d9aec51af3b04beeeb0389e218eb43b18f1a526d4d42bc3325726ffd866efad9",
            "data/snapshots/wdi_archive/EN.ATM.NOXE.KT.CE.zip",
        ),
    }
    assert {
        key: (lock.url, lock.sha256, lock.relative_path.as_posix())
        for key, lock in sources.locks.items()
        if key in expected
    } == expected
    assert sources.whr.provenance_url == (
        "https://web.archive.org/web/20220715181822id_/https://worldhappiness.report/ed/2022/"
    )
    assert sources.whr.archive_capture == "2022-07-15T18:18:22Z"
    assert sources.aqli.source_updated_at == "2025-08-19T13:13:14Z"
    assert sources.wdi_lastupdated == "2026-07-13"


def test_wdi_indicator_metadata_hashes_are_locked(sources) -> None:
    expected = {
        "wdi_population_metadata": "2f8491efc00bf2c0995112ff8e87aba69e5e9d22d0880b22f7e3a4ec757ba05c",
        "wdi_life_expectancy_metadata": "a39cb6fddfbbb953053690366243dffe77a266c4deae79c46ce5a06da9f5fc31",
        "wdi_ghg_total_metadata": "cc3dc0cec5b9a6bd3874cfc8c3e4f0e7ee5232f8726927d9784b6abdcc8e3ed8",
        "wdi_ghg_co2_metadata": "b589d061bd920762db1bc986fd2e8f75cb25aeb940509907a1906fd40484e839",
        "wdi_ghg_ch4_metadata": "708193dc91019e5dee1d8c426a67fca4967ca2fedac12598ab64730e4037375e",
        "wdi_ghg_n2o_metadata": "c4d6c1792a8a4ce42271b0237e08af0a1362de841965cad4a7f6a7131e0adf8e",
    }
    assert {key: sources.locks[key].sha256 for key in expected} == expected
    for key in expected:
        assert sources.locks[key].url == (
            "https://api.worldbank.org/v2/indicator/"
            f"{sources.locks[key].expected_indicator}?format=json"
        )


def test_wdi_source_ids_keep_successor_and_archive_families_distinct(sources) -> None:
    assert sources.lock("wdi_ghg_total").expected_source_id == "2"
    assert sources.lock("wdi_archive_total_ghg").expected_source_id == "57"
    assert sources.lock("wdi_ghg_total").expected_indicator == "EN.GHG.ALL.MT.CE.AR5"
    assert sources.lock("wdi_archive_total_ghg").expected_indicator == "EN.ATM.GHGT.KT.CE"
    assert sources.fallback_families == {}


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        ('burden = "unknown"', "burden"),
        ('fallback_family = "wdi_archive_ds57"', "fallback"),
        ('total_indicator = "EN.ATM.GHGT.KT.CE"', "retired"),
        ("absolute_tolerance = 0.0", "tolerance"),
    ],
)
def test_invalid_method_pin_fails_closed(
    tmp_path: Path, replacement: str, match: str
) -> None:
    path = Path("config/method.toml")
    content = path.read_text(encoding="utf-8")
    needle = {
        'burden = "unknown"': 'burden = "aqli_full_wdi_population"',
        'fallback_family = "wdi_archive_ds57"': 'fallback_family = "none"',
        'total_indicator = "EN.ATM.GHGT.KT.CE"': 'total_indicator = "EN.GHG.ALL.MT.CE.AR5"',
        "absolute_tolerance = 0.0": "absolute_tolerance = 1e-9",
    }[replacement]
    candidate = tmp_path / "method.toml"
    candidate.write_text(content.replace(needle, replacement), encoding="utf-8")

    with pytest.raises(ConfigError, match=match):
        load_method(candidate)


def test_non_five_aqli_benchmark_fails_closed(tmp_path: Path) -> None:
    content = Path("config/sources.toml").read_text(encoding="utf-8")
    candidate = tmp_path / "sources.toml"
    candidate.write_text(content.replace("benchmark = 5.0", "benchmark = 4.0"), encoding="utf-8")

    with pytest.raises(ConfigError, match="benchmark"):
        load_sources(candidate)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        ("scale = 10.0", "scale = 9.0"),
        ("max_abs_wld_reconciliation_share = 0.05", "max_abs_wld_reconciliation_share = 0.04"),
        ("gross_penalty_weight = true", "gross_penalty_weight = false"),
        (
            "fixed_penalty_weights = [0.05, 0.10, 0.25, 0.50, 0.765, 1.00]",
            "fixed_penalty_weights = [0.10, 0.05, 0.25, 0.50, 0.765, 1.00]",
        ),
        ("neutral_points = [4.0, 4.5, 5.0, 5.1]", "neutral_points = [4.0, 4.5, 5.1]"),
        ("aqli_rounding_half_width = 0.05", "aqli_rounding_half_width = 0.1"),
        ("lower_bound_floor = 0.0", "lower_bound_floor = 0.1"),
        (
            'label = "rounding_sensitivity_not_confidence_interval"',
            'label = "confidence_interval"',
        ),
        ('decomposition = "shapley"', 'decomposition = "sequential"'),
        ("relative_tolerance = 1e-10", "relative_tolerance = 1e-8"),
    ],
)
def test_every_method_constant_is_an_exact_pin(
    tmp_path: Path, needle: str, replacement: str
) -> None:
    candidate = tmp_path / "method.toml"
    candidate.write_text(
        Path("config/method.toml").read_text(encoding="utf-8").replace(needle, replacement),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="pin"):
        load_method(candidate)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?date=2016:2018&format=json&per_page=20000",
            "https://example.invalid/changed",
        ),
        ("data/snapshots/wdi/SP.POP.TOTL.json", "data/snapshots/wdi/changed.json"),
        ('publisher = "World Bank"', 'publisher = "Changed publisher"'),
        ('source_family = "wdi_current"', 'source_family = "edgar_ar5_excl_lulucf"'),
        ('unit = "Mt CO2 equivalent"', 'unit = "kt CO2 equivalent"'),
        ('expected_source_id = "57"', 'expected_source_id = "2"'),
        ('expected_indicator = "EN.GHG.CH4.MT.CE.AR5"', 'expected_indicator = "EN.GHG.N2O.MT.CE.AR5"'),
        ("redistributable = false", "redistributable = true"),
        (
            "65bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73",
            "00bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73",
        ),
        ("source_updated_at = \"2025-08-19T13:13:14Z\"", "source_updated_at = \"2025-08-20T00:00:00Z\""),
    ],
)
def test_canonical_source_lock_rejects_each_changed_field(
    tmp_path: Path, needle: str, replacement: str
) -> None:
    candidate = tmp_path / "sources.toml"
    candidate.write_text(
        Path("config/sources.toml").read_text(encoding="utf-8").replace(needle, replacement, 1),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="canonical source lock"):
        load_sources(candidate)


@pytest.mark.parametrize(
    "content_transform",
    [
        lambda content: content.replace('key = "wdi_ghg_ch4"', 'key = "wdi_extra"', 1),
        lambda content: content
        + """
[[source]]
key = "unregistered_source"
url = "https://example.invalid/source"
path = "data/snapshots/unregistered.json"
publisher = "Example"
source_family = "wdi_current"
unit = "metadata"
expected_source_id = "2"
access_date = "2026-07-17"
redistributable = true
sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
""",
    ],
)
def test_canonical_source_lock_rejects_missing_or_extra_keys(tmp_path: Path, content_transform) -> None:
    candidate = tmp_path / "sources.toml"
    candidate.write_text(
        content_transform(Path("config/sources.toml").read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="canonical source lock"):
        load_sources(candidate)


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        ('source_family = "unknown"', "source_family"),
        ('source_family = "wdi_current"\nfallback_family = "wdi_archive_ds57"', "fallback"),
    ],
)
def test_invalid_source_family_or_fallback_fails_closed(
    tmp_path: Path, replacement: str, match: str
) -> None:
    content = Path("config/sources.toml").read_text(encoding="utf-8")
    candidate = tmp_path / "sources.toml"
    candidate.write_text(
        content.replace('source_family = "wdi_current"', replacement, 1),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=match):
        load_sources(candidate)
