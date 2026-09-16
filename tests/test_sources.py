from __future__ import annotations

import csv
from dataclasses import replace
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from shutil import copy2
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from erhni.config import REPOSITORY_ROOT, SourceLock, load_sources
from erhni.disclosure import ConfigError, load_disclosure, validate_staged_path
from erhni.sources import (
    SourceAcquisitionError,
    SourceFamilyError,
    SourceIntegrityError,
    SourceSchemaError,
    acquire_one,
    build_source_manifest,
    read_aqli,
    read_wdi_archive,
    read_wdi_metadata,
    read_wdi_observations,
    read_whr_annual,
    resolve_source_path,
    validate_all,
    validate_source,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sources"
YEARS = (2016, 2017, 2018)


def _lock(
    *,
    key: str = "fixture",
    content: bytes = b"expected",
    relative_path: str = "data/snapshots/wdi/fixture.bin",
    source_family: str = "wdi_current",
    unit: str = "people",
    source_id: str = "2",
    indicator: str | None = "SP.POP.TOTL",
    redistributable: bool = True,
) -> SourceLock:
    if (
        source_family == "wdi_archive_ds57"
        and relative_path == "data/snapshots/wdi/fixture.bin"
        and indicator is not None
    ):
        relative_path = f"data/snapshots/wdi_archive/{indicator}.zip"
    return SourceLock(
        key=key,
        url=f"https://example.invalid/{key}",
        relative_path=Path(relative_path),
        path=REPOSITORY_ROOT / relative_path,
        publisher="Fixture publisher",
        source_family=source_family,
        unit=unit,
        expected_source_id=source_id,
        expected_indicator=indicator,
        access_date="2026-07-17",
        redistributable=redistributable,
        sha256=sha256(content).hexdigest(),
    )


def test_acquire_rejects_wrong_hash_and_removes_partial_file(tmp_path: Path) -> None:
    lock = _lock()

    with pytest.raises(SourceIntegrityError, match="sha256"):
        acquire_one(lock, tmp_path, downloader=lambda _: b"changed")

    destination = tmp_path / lock.relative_path
    assert not destination.exists()
    assert not destination.with_name(destination.name + ".part").exists()


def test_acquire_reuses_verified_file_without_network(tmp_path: Path) -> None:
    lock = _lock()
    destination = tmp_path / lock.relative_path
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"expected")

    def unavailable(_: str) -> bytes:
        raise AssertionError("verified files must not be downloaded again")

    assert acquire_one(lock, tmp_path, downloader=unavailable) == destination


def test_whr_schema_is_annual_unique_and_ignores_pooled_scores() -> None:
    frame = read_whr_annual(FIXTURES / "whr_annual.csv", years=YEARS)

    assert set(frame.columns) == {"source_name", "year", "life_ladder"}
    assert set(frame["year"]) == set(YEARS)
    assert not frame.duplicated(["source_name", "year"]).any()
    assert "pooled" not in " ".join(frame.columns).lower()


def test_whr_requires_direct_annual_fields_and_unique_country_year(
    tmp_path: Path,
) -> None:
    pooled_only = tmp_path / "pooled.csv"
    pooled_only.write_text(
        "Country name,Figure 2.1 pooled score\nChina,5.5\n", encoding="utf-8"
    )
    with pytest.raises(SourceSchemaError, match="Life Ladder|year"):
        read_whr_annual(pooled_only, years=YEARS)

    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        "Country name,year,Life Ladder\nChina,2016,5.4\nChina,2016,5.5\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceSchemaError, match="duplicate"):
        read_whr_annual(duplicate, years=YEARS)


def test_aqli_direct_fields_zeros_and_blank_exclusions() -> None:
    frame = read_aqli(FIXTURES / "aqli.csv", years=YEARS)

    assert tuple(frame.query("iso3 == 'CHN'").sort_values("year").aqli_years_lost) == (
        3.4,
        3.1,
        2.7,
    )
    assert tuple(frame.query("iso3 == 'IND'").sort_values("year").aqli_years_lost) == (
        4.2,
        4.1,
        4.1,
    )
    assert tuple(frame.query("iso3 == 'ABW'").sort_values("year").aqli_years_lost) == (
        0.0,
        0.0,
        0.0,
    )
    assert not ((frame["iso3"] == "USA") & (frame["year"] == 2016)).any()


def test_aqli_whitespace_only_cells_are_exclusions(tmp_path: Path) -> None:
    path = tmp_path / "aqli.csv"
    path.write_text(
        "id,whostandard,who2016,who2017,who2018\nCHN,5,   ,1.0,0.0\n",
        encoding="utf-8",
    )

    frame = read_aqli(path, years=YEARS)

    assert tuple(frame["year"]) == (2017, 2018)
    assert tuple(frame["aqli_years_lost"]) == (1.0, 0.0)


@pytest.mark.parametrize(
    "token",
    ["N/A", "NA", "null", "NaN", "garbage", "Infinity", "-Infinity", "inf", "-inf"],
)
def test_aqli_rejects_nonempty_tokens_and_nonfinite_numbers(
    tmp_path: Path, token: str
) -> None:
    path = tmp_path / "aqli.csv"
    path.write_text(
        f"id,whostandard,who2016,who2017,who2018\nCHN,5,{token},1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceSchemaError, match="nonnumeric|finite"):
        read_aqli(path, years=YEARS)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("id,whostandard,who2016,who2017\nCHN,5,1,1\n", "who2018"),
        ("id,whostandard,who2016,who2017,who2018\nCHN,5,-1,1,1\n", "negative"),
        ("id,whostandard,who2016,who2017,who2018\nCHN,10,1,1,1\n", "whostandard"),
    ],
)
def test_aqli_rejects_missing_negative_or_wrong_benchmark(
    tmp_path: Path, content: str, match: str
) -> None:
    path = tmp_path / "aqli.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SourceSchemaError, match=match):
        read_aqli(path, years=YEARS)


def test_wdi_observations_require_indicator_source_units_years_uniqueness_and_wld() -> (
    None
):
    lock = _lock()
    frame = read_wdi_observations(FIXTURES / "wdi_observations.json", lock, years=YEARS)

    assert set(frame["indicator"]) == {"SP.POP.TOTL"}
    assert set(frame["source_id"]) == {"2"}
    assert set(frame["unit"]) == {"people"}
    assert set(frame["year"]) == set(YEARS)
    assert "WLD" in set(frame["iso3"])
    assert not frame.duplicated(["iso3", "year"]).any()


@pytest.mark.parametrize(
    ("field", "replacement", "match"),
    [
        ("sourceid", "57", "source"),
        ("countryiso3code", "CH", "ISO3"),
        ("date", "2015", "year"),
    ],
)
def test_wdi_observations_fail_closed_on_wrong_schema(
    tmp_path: Path, field: str, replacement: str, match: str
) -> None:
    payload = json.loads(
        (FIXTURES / "wdi_observations.json").read_text(encoding="utf-8")
    )
    if field == "sourceid":
        payload[0][field] = replacement
    else:
        payload[1][0][field] = replacement
    path = tmp_path / "observations.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SourceSchemaError, match=match):
        read_wdi_observations(path, _lock(), years=YEARS)


def test_wdi_ghg_metadata_locks_source_boundary_ar5_and_co2_equivalent() -> None:
    lock = _lock(
        source_family="edgar_ar5_excl_lulucf",
        unit="metadata",
        indicator="EN.GHG.CH4.MT.CE.AR5",
    )
    summary = read_wdi_metadata(FIXTURES / "wdi_ghg_metadata.json", lock)

    assert summary["source_id"] == "2"
    assert summary["unit"] == "Mt CO2e"
    assert summary["assessment"] == "AR5"
    assert summary["boundary"] == "excludes LULUCF"
    assert summary["already_co2_equivalent"] is True


def test_wdi_ghg_metadata_rejects_unexpected_source(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "wdi_ghg_metadata.json").read_text(encoding="utf-8")
    )
    payload[1][0]["source"]["id"] = "57"
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    lock = _lock(
        source_family="edgar_ar5_excl_lulucf",
        unit="metadata",
        indicator="EN.GHG.CH4.MT.CE.AR5",
    )

    with pytest.raises(SourceSchemaError, match="source"):
        read_wdi_metadata(path, lock)


def test_wdi_ghg_metadata_rejects_contradictory_lulucf_boundary(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (FIXTURES / "wdi_ghg_metadata.json").read_text(encoding="utf-8")
    )
    payload[1][0]["sourceNote"] = (
        "This measure does not exclude LULUCF and is standardized to carbon dioxide "
        "equivalent values using IPCC AR5 global warming potentials."
    )
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    lock = _lock(
        source_family="edgar_ar5_excl_lulucf",
        unit="metadata",
        indicator="EN.GHG.CH4.MT.CE.AR5",
    )

    with pytest.raises(SourceSchemaError, match="exclude LULUCF|contradict"):
        read_wdi_metadata(path, lock)


def test_wdi_ghg_metadata_rejects_contradictory_co2e_standardization(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (FIXTURES / "wdi_ghg_metadata.json").read_text(encoding="utf-8")
    )
    payload[1][0]["sourceNote"] = (
        "This measure excludes LULUCF but is not standardized to carbon dioxide "
        "equivalent values using IPCC AR5 global warming potentials."
    )
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    lock = _lock(
        source_family="edgar_ar5_excl_lulucf",
        unit="metadata",
        indicator="EN.GHG.CH4.MT.CE.AR5",
    )

    with pytest.raises(SourceSchemaError, match="standardization|standardized"):
        read_wdi_metadata(path, lock)


def _csv_text(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _canonical_ds57_members(indicator: str) -> dict[str, str]:
    revision = "1"
    observation_fields = [
        "Country Name",
        "Country Code",
        "Indicator Name",
        "Indicator Code",
        *(str(year) for year in range(1960, 2026)),
    ]
    indicator_name = "Methane emissions (kt of CO2 equivalent)"
    observation_rows = []
    for name, code, values in (
        ("China", "CHN", {"2016": "100", "2017": "101", "2018": "102"}),
        ("World", "WLD", {"2016": "1000", "2017": "1001", "2018": "1002"}),
    ):
        observation_rows.append(
            {
                "Country Name": name,
                "Country Code": code,
                "Indicator Name": indicator_name,
                "Indicator Code": indicator,
                **values,
            }
        )
    observation_text = (
        "Data Source,WDI Database Archives\n\n"
        "Last Updated Date,2025-10-29\n\n"
        + _csv_text(observation_fields, observation_rows)
    )
    indicator_text = _csv_text(
        ["INDICATOR_CODE", "INDICATOR_NAME", "SOURCE_NOTE", "SOURCE_ORGANIZATION"],
        [
            {
                "INDICATOR_CODE": indicator,
                "INDICATOR_NAME": indicator_name,
                "SOURCE_NOTE": "Archived methane series",
                "SOURCE_ORGANIZATION": "World Resources Institute",
            }
        ],
    )
    country_text = _csv_text(
        ["Country Code", "Region", "IncomeGroup", "SpecialNotes", "TableName"],
        [
            {
                "Country Code": "CHN",
                "Region": "East Asia & Pacific",
                "IncomeGroup": "Upper middle income",
                "SpecialNotes": "",
                "TableName": "China",
            },
            {
                "Country Code": "WLD",
                "Region": "",
                "IncomeGroup": "",
                "SpecialNotes": "World aggregate",
                "TableName": "World",
            },
        ],
    )
    return {
        f"API_{indicator}_DS57_en_csv_v2_{revision}.csv": observation_text,
        f"Metadata_Indicator_API_{indicator}_DS57_en_csv_v2_{revision}.csv": indicator_text,
        f"Metadata_Country_API_{indicator}_DS57_en_csv_v2_{revision}.csv": country_text,
    }


def _write_ds57_zip(
    path: Path,
    indicator: str = "EN.ATM.METH.KT.CE",
    *,
    members: dict[str, str] | None = None,
) -> None:
    members = _canonical_ds57_members(indicator) if members is None else members
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_ds57_archive_identifies_source_and_validates_members_offline(
    tmp_path: Path,
) -> None:
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path)
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        unit="kt CO2 equivalent",
        source_id="57",
        indicator="EN.ATM.METH.KT.CE",
    )

    frame = read_wdi_archive(path, lock, years=YEARS)
    assert set(frame["source_id"]) == {"57"}
    assert set(frame["indicator"]) == {"EN.ATM.METH.KT.CE"}
    assert "WLD" in set(frame["iso3"])
    assert frame["country_metadata_member"].all()

    with pytest.raises(SourceFamilyError, match="successor|family|JSON"):
        read_wdi_observations(path, lock, years=YEARS)


def test_ds57_archive_rejects_missing_or_unexpected_members(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("unexpected.csv", b"wrong")
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator="EN.ATM.METH.KT.CE",
    )
    with pytest.raises(SourceSchemaError, match="member"):
        read_wdi_archive(path, lock, years=YEARS)


def _replace_ds57_member(
    members: dict[str, str], prefix: str, transform
) -> dict[str, str]:
    changed = dict(members)
    name = next(name for name in changed if name.startswith(prefix))
    changed[name] = transform(changed[name])
    return changed


def _add_nonempty_trailing_ds57_column(text: str) -> str:
    lines = text.splitlines()
    lines[4] += ","
    lines[5] += ",unexpected"
    lines[6] += ","
    return "\n".join(lines) + "\n"


def _truncate_ds57_row(text: str, *, line_index: int, missing_fields: int) -> str:
    lines = text.splitlines()
    values = next(csv.reader([lines[line_index]]))
    output = StringIO()
    csv.writer(output, lineterminator="").writerow(values[:-missing_fields])
    lines[line_index] = output.getvalue()
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(
    ("prefix", "line_index", "missing_fields"),
    [
        ("Metadata_Indicator_", 1, 2),
        ("Metadata_Country_", 1, 1),
        ("API_", 5, 1),
    ],
)
def test_ds57_archive_rejects_truncated_member_rows(
    tmp_path: Path, prefix: str, line_index: int, missing_fields: int
) -> None:
    indicator = "EN.ATM.METH.KT.CE"
    members = _replace_ds57_member(
        _canonical_ds57_members(indicator),
        prefix,
        lambda text: _truncate_ds57_row(
            text, line_index=line_index, missing_fields=missing_fields
        ),
    )
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path, indicator, members=members)
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator=indicator,
    )

    with pytest.raises(SourceSchemaError, match="truncated|schema"):
        read_wdi_archive(path, lock, years=YEARS)


@pytest.mark.parametrize(
    ("prefix", "transform", "match"),
    [
        (
            "Metadata_Indicator_",
            lambda text: text.replace("Archived methane series", ""),
            "nonblank|metadata",
        ),
        (
            "Metadata_Indicator_",
            lambda text: text + text.splitlines()[1] + "\n",
            "one indicator|metadata",
        ),
        (
            "Metadata_Country_",
            lambda text: text + text.splitlines()[1] + "\n",
            "duplicate|country",
        ),
        (
            "Metadata_Country_",
            lambda text: text.replace("CHN,", ",", 1),
            "nonblank country codes|country metadata",
        ),
        (
            "Metadata_Country_",
            lambda text: text.replace("Country Code,", "Unexpected,", 1),
            "columns|schema",
        ),
        (
            "API_",
            lambda text: text.replace(",2025\n", ",2025,Unexpected\n", 1),
            "columns|schema",
        ),
        (
            "API_",
            _add_nonempty_trailing_ds57_column,
            "trailing|schema",
        ),
        (
            "API_",
            lambda text: text.replace(",CHN,", ",ZZZ,", 1),
            "country metadata|membership|inconsistent",
        ),
    ],
)
def test_ds57_archive_rejects_corrupt_member_schemas(
    tmp_path: Path, prefix: str, transform, match: str
) -> None:
    indicator = "EN.ATM.METH.KT.CE"
    members = _replace_ds57_member(
        _canonical_ds57_members(indicator), prefix, transform
    )
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path, indicator, members=members)
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator=indicator,
    )

    with pytest.raises(SourceSchemaError, match=match):
        read_wdi_archive(path, lock, years=YEARS)


def test_ds57_archive_rejects_noncanonical_source57_member_name(tmp_path: Path) -> None:
    indicator = "EN.ATM.METH.KT.CE"
    members = _canonical_ds57_members(indicator)
    name = next(name for name in members if name.startswith("API_"))
    members[name.replace("DS57", "DS58")] = members.pop(name)
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path, indicator, members=members)
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator=indicator,
    )

    with pytest.raises(SourceSchemaError, match="member|source 57|DS57"):
        read_wdi_archive(path, lock, years=YEARS)


def test_ds57_archive_rejects_noncanonical_lock_path(tmp_path: Path) -> None:
    indicator = "EN.ATM.METH.KT.CE"
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path, indicator)
    lock = _lock(
        content=path.read_bytes(),
        relative_path="data/snapshots/wdi_archive/not-the-indicator.zip",
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator=indicator,
    )

    with pytest.raises(SourceFamilyError, match="lock|path|family"):
        read_wdi_archive(path, lock, years=YEARS)


def test_ds57_archive_marks_known_historical_aggregate_without_metadata(
    tmp_path: Path,
) -> None:
    indicator = "EN.ATM.METH.KT.CE"
    members = _canonical_ds57_members(indicator)
    members = _replace_ds57_member(
        members,
        "API_",
        lambda text: text + text.splitlines()[5].replace("CHN", "EEC") + "\n",
    )
    path = tmp_path / "archive.zip"
    _write_ds57_zip(path, indicator, members=members)
    lock = _lock(
        content=path.read_bytes(),
        source_family="wdi_archive_ds57",
        source_id="57",
        indicator=indicator,
    )

    frame = read_wdi_archive(path, lock, years=YEARS)

    aggregate = frame.query("iso3 == 'EEC'")
    assert not aggregate.empty
    assert not aggregate["country_metadata_member"].any()
    summary = validate_source(lock, path, years=YEARS)
    assert summary["archive_only_country_code_count"] == 1
    assert "archive_only_country_codes" not in summary


def test_paths_keep_restricted_inputs_out_of_snapshots_and_public_release(
    tmp_path: Path,
) -> None:
    sources = load_sources()
    restricted = resolve_source_path(sources.whr, repository_root=tmp_path)
    public = resolve_source_path(
        sources.lock("wdi_population"),
        repository_root=tmp_path,
        raw_dir=tmp_path / "raw",
    )

    assert restricted == (
        tmp_path / "data/raw/external" / sources.whr.relative_path.name
    )
    assert public == tmp_path / "data/snapshots/wdi/SP.POP.TOTL.json"
    with pytest.raises(ConfigError, match="non-public"):
        validate_staged_path(load_disclosure(), sources.whr.relative_path)


def test_restricted_path_accepts_destination_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-restricted"
    path = resolve_source_path(
        load_sources().whr, repository_root=tmp_path, raw_dir=outside
    )

    assert path == outside / "whr_2022_data_for_table_2_1.xls"


@pytest.mark.parametrize(
    "relative_raw",
    [
        "data/snapshots/not-ignored",
        "data/derived/public/raw",
        "other/raw",
        "data/raw/external/../../snapshots/not-ignored",
    ],
)
def test_restricted_path_rejects_nonignored_in_repo_destination(
    tmp_path: Path, relative_raw: str
) -> None:
    with pytest.raises(SourceAcquisitionError, match="restricted destination"):
        resolve_source_path(
            load_sources().whr,
            repository_root=tmp_path,
            raw_dir=tmp_path / relative_raw,
        )


def test_restricted_path_rejects_symlink_into_nonignored_repo_path(
    tmp_path: Path,
) -> None:
    snapshots = tmp_path / "data/snapshots/not-ignored"
    snapshots.mkdir(parents=True)
    outside_alias = tmp_path.parent / f"{tmp_path.name}-alias"
    outside_alias.symlink_to(snapshots, target_is_directory=True)

    with pytest.raises(SourceAcquisitionError, match="restricted destination"):
        resolve_source_path(
            load_sources().whr,
            repository_root=tmp_path,
            raw_dir=outside_alias,
        )


def test_restricted_path_rejects_existing_file_symlink_out_of_ignored_root(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "data/raw/external"
    raw.mkdir(parents=True)
    leaked = tmp_path / "data/snapshots/leaked.xls"
    leaked.parent.mkdir(parents=True)
    destination = raw / "whr_2022_data_for_table_2_1.xls"
    destination.symlink_to(leaked)

    with pytest.raises(SourceAcquisitionError, match="restricted destination"):
        resolve_source_path(load_sources().whr, repository_root=tmp_path, raw_dir=raw)


def test_cli_rejects_nonignored_restricted_raw_directory() -> None:
    rejected_raw_dir = "data/snapshots/not-ignored-cli-test"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "erhni.sources",
            "acquire",
            "--config",
            "config/sources.toml",
            "--raw-dir",
            rejected_raw_dir,
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "restricted destination" in result.stderr
    assert not (REPOSITORY_ROOT / rejected_raw_dir).exists()


def test_manifest_is_stable_sorted_config_dated_and_machine_path_free(
    tmp_path: Path,
) -> None:
    first = _lock(key="z_source")
    second = replace(
        _lock(key="a_source", content=b"other"),
        access_date="2020-01-02",
        publisher="Another publisher",
    )
    paths = {}
    for lock, content in ((first, b"expected"), (second, b"other")):
        path = tmp_path / lock.relative_path.name
        path.write_bytes(content)
        paths[lock.key] = path
    destination = tmp_path / "source_manifest.json"

    build_source_manifest(
        (first, second),
        paths,
        destination,
        schemas={
            first.key: {"rows": 1},
            second.key: {"rows": 2},
        },
    )
    first_bytes = destination.read_bytes()
    build_source_manifest(
        (second, first),
        paths,
        destination,
        schemas={
            second.key: {"rows": 2},
            first.key: {"rows": 1},
        },
    )

    assert destination.read_bytes() == first_bytes
    manifest = json.loads(first_bytes)
    assert [entry["key"] for entry in manifest["sources"]] == ["a_source", "z_source"]
    assert [entry["access_date"] for entry in manifest["sources"]] == [
        "2020-01-02",
        "2026-07-17",
    ]
    assert str(tmp_path) not in first_bytes.decode("utf-8")
    assert all(
        "rights" in entry and "observed_sha256" in entry
        for entry in manifest["sources"]
    )


def test_committed_snapshots_validate_offline_from_a_fresh_root(tmp_path: Path) -> None:
    sources = load_sources()
    for lock in sources.locks.values():
        if not lock.redistributable:
            continue
        destination = tmp_path / lock.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(lock.path, destination)

    summaries = validate_all(
        sources,
        repository_root=tmp_path,
        raw_dir=tmp_path / "data/raw/external",
        include_restricted=False,
    )
    assert set(summaries) == {
        key for key, lock in sources.locks.items() if lock.redistributable
    }


def test_sources_module_is_available_to_the_documented_python_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "erhni.sources", "--help"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "acquire" in result.stdout and "validate" in result.stdout
