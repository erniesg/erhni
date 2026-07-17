"""Direct annual normalization with explicit identity and disclosure decisions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from erhni.config import ConfigError, REPOSITORY_ROOT, load_method, load_sources
from erhni.countries import (
    CountryCrosswalk,
    collect_source_identities,
    load_country_map,
    load_regions,
)
from erhni.disclosure import classify_path, load_disclosure, release_role_for_path
from erhni.hashing import sha256_file
from erhni.sources import (
    read_aqli,
    read_wdi_observations,
    read_whr_annual,
    resolve_source_path,
    validate_all,
)


OUTPUTS = {
    "happiness": (
        "data/derived/restricted/happiness_annual.csv",
        "restricted_derived",
    ),
    "wdi": ("data/derived/public/wdi_annual.csv", "public_aggregate"),
    "aqli": ("data/derived/restricted/aqli_annual.csv", "restricted_derived"),
    "exclusions": (
        "data/derived/restricted/source_exclusions.csv",
        "restricted_derived",
    ),
    "exclusion_summary": (
        "data/derived/public/source_exclusion_summary.csv",
        "public_aggregate",
    ),
}
MANIFEST_LOGICAL_PATH = "data/derived/source_manifest.json"
PUBLIC_RELEASE_ROLES = {
    "data/derived/public/wdi_annual.csv": "public_aggregate",
    "data/derived/public/source_exclusion_summary.csv": "public_aggregate",
    MANIFEST_LOGICAL_PATH: "public_evidence",
}
EXCLUSION_COLUMNS = ("source", "source_key", "year", "stage", "reason")
SUMMARY_COLUMNS = ("source", "stage", "reason_group", "count")
FLOAT_FORMAT = "%.15g"


def _add_exclusion(
    exclusions: list[dict[str, object]],
    *,
    source: str,
    source_key: str,
    year: int,
    stage: str,
    reason: str,
) -> None:
    exclusions.append(
        {
            "source": source,
            "source_key": source_key,
            "year": int(year),
            "stage": stage,
            "reason": reason,
        }
    )


def normalize_whr(
    frame: pd.DataFrame,
    crosswalk: CountryCrosswalk,
    *,
    exclusions: list[dict[str, object]] | None = None,
) -> pd.DataFrame:
    """Apply exact WHR identities without averaging or filling annual observations."""

    dropped = [] if exclusions is None else exclusions
    records: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        decision = crosswalk.resolve("whr", str(row.source_name))
        if decision.status != "include":
            _add_exclusion(
                dropped,
                source="whr",
                source_key=str(row.source_name),
                year=int(row.year),
                stage="identity",
                reason=decision.reason,
            )
            continue
        records.append(
            {
                "source": "whr",
                "year": int(row.year),
                "iso3": decision.iso3,
                "display_name": decision.display_name,
                "life_ladder": row.life_ladder,
                "imputed": False,
            }
        )
    normalized = pd.DataFrame.from_records(
        records,
        columns=(
            "source",
            "year",
            "iso3",
            "display_name",
            "life_ladder",
            "imputed",
        ),
    ).sort_values(["source", "year", "iso3"], kind="stable", ignore_index=True)
    if normalized.duplicated(["iso3", "year"]).any():
        raise ValueError("WHR normalization produced duplicate ISO3-year rows")
    return normalized


def normalize_aqli(
    frame: pd.DataFrame,
    crosswalk: CountryCrosswalk,
    *,
    exclusions: list[dict[str, object]] | None = None,
) -> pd.DataFrame:
    """Reshape already-validated direct AQLI WHO fields without recalculation."""

    dropped = [] if exclusions is None else exclusions
    records: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        source_key = str(row.iso3)
        decision = crosswalk.resolve("aqli", source_key)
        if decision.status != "include":
            _add_exclusion(
                dropped,
                source="aqli",
                source_key=source_key,
                year=int(row.year),
                stage="identity",
                reason=decision.reason,
            )
            continue
        records.append(
            {
                "source": "aqli",
                "year": int(row.year),
                "iso3": decision.iso3,
                "display_name": decision.display_name,
                "aqli_years_lost": row.aqli_years_lost,
                "imputed": False,
            }
        )
    normalized = pd.DataFrame.from_records(
        records,
        columns=(
            "source",
            "year",
            "iso3",
            "display_name",
            "aqli_years_lost",
            "imputed",
        ),
    ).sort_values(["source", "year", "iso3"], kind="stable", ignore_index=True)
    if normalized.duplicated(["iso3", "year"]).any():
        raise ValueError("AQLI normalization produced duplicate ISO3-year rows")
    return normalized


def record_aqli_missing_fields(
    raw: pd.DataFrame,
    *,
    years: Sequence[int],
    crosswalk: CountryCrosswalk,
    exclusions: list[dict[str, object]],
) -> None:
    """Record annual AQLI fields omitted by the validated direct-value parser."""

    required = {"id", *(f"who{year}" for year in years)}
    if not required.issubset(raw.columns):
        raise ValueError("AQLI raw table lacks reviewed annual fields")
    for row in raw.loc[:, sorted(required)].to_dict(orient="records"):
        source_key = str(row["id"])
        decision = crosswalk.resolve("aqli", source_key)
        for year in years:
            if str(row[f"who{year}"]).strip() != "":
                continue
            stage = "identity" if decision.status != "include" else "value"
            reason = (
                decision.reason
                if stage == "identity"
                else "Missing direct annual source value."
            )
            _add_exclusion(
                exclusions,
                source="aqli",
                source_key=source_key,
                year=year,
                stage=stage,
                reason=reason,
            )


def record_wdi_skipped_identities(
    rows: Iterable[dict[str, object]],
    *,
    indicator: str,
    crosswalk: CountryCrosswalk,
    exclusions: list[dict[str, object]],
) -> None:
    """Record WDI rows whose API response omits an ISO3 observation token."""

    for row in rows:
        if row.get("countryiso3code") != "":
            continue
        country = row.get("country")
        if not isinstance(country, dict) or not isinstance(country.get("id"), str):
            raise ValueError("WDI skipped row lacks a source identity")
        source_token = country["id"]
        decision = crosswalk.resolve("wdi", source_token)
        if decision.status not in {"exclude", "aggregate"}:
            raise ValueError("WDI skipped source identity must be explicitly non-country")
        try:
            year = int(str(row["date"]))
        except (KeyError, ValueError) as error:
            raise ValueError("WDI skipped row has an invalid year") from error
        _add_exclusion(
            exclusions,
            source="wdi",
            source_key=f"{source_token}|{indicator}",
            year=year,
            stage="identity",
            reason=decision.reason,
        )


def normalize_wdi(
    observations: Mapping[str, pd.DataFrame],
    crosswalk: CountryCrosswalk,
    *,
    indicator_columns: Mapping[str, str],
    exclusions: list[dict[str, object]] | None = None,
) -> pd.DataFrame:
    """Align same-year WDI indicators, retaining WLD and no other aggregate."""

    dropped = [] if exclusions is None else exclusions
    selected: list[dict[str, object]] = []
    for indicator, frame in observations.items():
        if indicator not in indicator_columns:
            raise ValueError(f"unreviewed WDI indicator: {indicator}")
        for row in frame.itertuples(index=False):
            source_code = str(row.iso3)
            decision = crosswalk.resolve("wdi", source_code)
            source_key = f"{source_code}|{indicator}"
            if decision.status == "aggregate" and source_code != "WLD":
                _add_exclusion(
                    dropped,
                    source="wdi",
                    source_key=source_key,
                    year=int(row.year),
                    stage="identity",
                    reason=decision.reason,
                )
                continue
            if decision.status == "exclude":
                _add_exclusion(
                    dropped,
                    source="wdi",
                    source_key=source_key,
                    year=int(row.year),
                    stage="identity",
                    reason=decision.reason,
                )
                continue
            if decision.status != "include" and source_code != "WLD":
                raise ValueError(f"unsupported WDI identity decision for {source_code}")
            value = row.value
            if pd.isna(value):
                _add_exclusion(
                    dropped,
                    source="wdi",
                    source_key=source_key,
                    year=int(row.year),
                    stage="value",
                    reason="Missing direct annual source value.",
                )
            selected.append(
                {
                    "source": "wdi",
                    "year": int(row.year),
                    "iso3": source_code if source_code == "WLD" else decision.iso3,
                    "display_name": decision.display_name,
                    "record_type": "world" if source_code == "WLD" else "country",
                    "indicator": indicator,
                    "value": value,
                }
            )

    long = pd.DataFrame.from_records(selected)
    keys = ["source", "year", "iso3", "display_name", "record_type"]
    if long.duplicated([*keys, "indicator"]).any():
        raise ValueError("WDI normalization produced duplicate indicator rows")
    base = long.loc[:, keys].drop_duplicates(ignore_index=True)
    normalized = base
    for indicator, column in indicator_columns.items():
        values = long.loc[
            long["indicator"].eq(indicator), ["year", "iso3", "value"]
        ].rename(columns={"value": column})
        normalized = normalized.merge(
            values,
            how="left",
            on=["year", "iso3"],
            validate="one_to_one",
            sort=False,
        )
    normalized["imputed"] = False
    normalized = normalized.loc[
        :,
        [
            *keys,
            *indicator_columns.values(),
            "imputed",
        ],
    ].sort_values(["source", "year", "iso3"], kind="stable", ignore_index=True)
    if normalized.duplicated(["iso3", "year"]).any():
        raise ValueError("WDI normalization produced duplicate ISO3-year rows")
    world = normalized.loc[normalized["record_type"].eq("world"), "iso3"]
    if set(world) != {"WLD"}:
        raise ValueError("WDI normalization must preserve WLD separately")
    return normalized


def _reason_group(stage: str, reason: str) -> str:
    lowered = reason.lower()
    if stage == "value":
        return "missing_direct_value"
    if "aggregate" in lowered:
        return "source_aggregate"
    return "explicit_identity_exclusion"


def build_public_exclusion_summary(
    exclusions: pd.DataFrame, *, threshold: int = 5
) -> pd.DataFrame:
    """Build one mutually exclusive leaf partition with coordinated suppression."""

    if threshold < 2:
        raise ValueError("disclosure threshold must be at least two")
    if exclusions.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    required = set(EXCLUSION_COLUMNS)
    if not required.issubset(exclusions.columns):
        raise ValueError("detailed exclusions have an unexpected schema")
    broad = exclusions.loc[:, ["source", "stage", "reason"]].copy()
    broad["reason_group"] = [
        _reason_group(str(stage), str(reason))
        for stage, reason in zip(broad["stage"], broad["reason"], strict=True)
    ]
    grouped = (
        broad.groupby(["source", "stage", "reason_group"], sort=True, dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )
    small = grouped[grouped["count"] < threshold]
    publish = grouped[grouped["count"] >= threshold].copy()
    if not small.empty:
        pooled_count = int(small["count"].sum())
        if pooled_count < threshold and not publish.empty:
            neighboring = publish.sort_values(
                ["count", "source", "stage", "reason_group"], kind="stable"
            ).iloc[0]
            pooled_count += int(neighboring["count"])
            mask = (
                publish["source"].eq(neighboring["source"])
                & publish["stage"].eq(neighboring["stage"])
                & publish["reason_group"].eq(neighboring["reason_group"])
            )
            publish = publish.loc[~mask]
        if pooled_count >= threshold:
            publish = pd.concat(
                [
                    publish,
                    pd.DataFrame(
                        [
                            {
                                "source": "pooled_sources",
                                "stage": "pooled_stages",
                                "reason_group": "pooled_small_cells",
                                "count": pooled_count,
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    publish = publish.loc[:, SUMMARY_COLUMNS].sort_values(
        ["source", "stage", "reason_group"], kind="stable", ignore_index=True
    )
    if not publish.empty and (publish["count"] < threshold).any():
        raise ValueError("public exclusion summary contains an unsafe cell")
    if int(publish["count"].sum()) > len(exclusions):
        raise ValueError("public exclusion partition overlaps")
    return publish


def _preflight_outputs(disclosure) -> None:
    planned = (*OUTPUTS.values(), (MANIFEST_LOGICAL_PATH, "public_aggregate"))
    for logical_path, expected_class in planned:
        observed = classify_path(disclosure, logical_path)
        if observed != expected_class:
            raise ConfigError(
                f"output disclosure mismatch for {logical_path}: "
                f"expected {expected_class}, observed {observed}"
            )
        expected_role = PUBLIC_RELEASE_ROLES.get(logical_path)
        if expected_role is not None:
            observed_role = release_role_for_path(disclosure, logical_path)
            if observed_role != expected_role:
                raise ConfigError(
                    f"output release role mismatch for {logical_path}: "
                    f"expected {expected_role}, observed {observed_role}"
                )


def _destination(derived_dir: Path, logical_path: str) -> Path:
    relative = Path(logical_path).relative_to("data/derived")
    destination = (derived_dir / relative).resolve()
    if derived_dir.resolve() not in destination.parents:
        raise ConfigError("derived output path escapes its configured root")
    return destination


def _write_csv(frame: pd.DataFrame, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    try:
        frame.to_csv(
            part,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format=FLOAT_FORMAT,
        )
        os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return destination


def _artifact_manifest_entry(
    key: str,
    path: Path,
    frame: pd.DataFrame,
    disclosure_class: str,
) -> dict[str, object]:
    return {
        "key": key,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "disclosure_class": disclosure_class,
        "rows": len(frame),
        "schema": {"columns": list(frame.columns)},
    }


def _write_manifest(
    *,
    source_manifest: Path,
    destination: Path,
    artifacts: Iterable[dict[str, object]],
) -> Path:
    try:
        payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read validated source manifest: {error}") from error
    payload["derived"] = sorted(artifacts, key=lambda entry: str(entry["key"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    try:
        part.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return destination


def _read_wdi_country_metadata(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload[1]
    except (OSError, UnicodeError, json.JSONDecodeError, IndexError, TypeError) as error:
        raise ValueError("validated WDI country metadata cannot be read") from error
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("validated WDI country metadata rows are invalid")
    return rows


def _validate_wdi_metadata_decisions(
    rows: Iterable[dict[str, object]], crosswalk: CountryCrosswalk
) -> None:
    for row in rows:
        code = str(row["id"])
        region = row["region"]
        if not isinstance(region, dict):
            raise ValueError("validated WDI country metadata region is invalid")
        decision = crosswalk.resolve("wdi", code)
        is_aggregate = region.get("value") == "Aggregates"
        if is_aggregate != (decision.status == "aggregate"):
            raise ValueError(f"WDI aggregate decision disagrees with metadata: {code}")


def normalize_all(
    *,
    method_path: str | Path,
    sources_path: str | Path,
    disclosure_path: str | Path,
    country_map_path: str | Path,
    regions_path: str | Path,
    raw_dir: str | Path,
    derived_dir: str | Path,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> tuple[Path, ...]:
    """Regenerate all five normalized artifacts and their public evidence manifest."""

    root = Path(repository_root).resolve()
    derived_root = Path(derived_dir).resolve()
    method = load_method(method_path)
    sources = load_sources(sources_path)
    disclosure = load_disclosure(disclosure_path)
    crosswalk = load_country_map(country_map_path)
    regions = load_regions(regions_path)
    _preflight_outputs(disclosure)

    included = {
        decision.iso3
        for decision in crosswalk.decisions
        if decision.status == "include"
    }
    if set(regions["iso3"]) != included:
        raise ValueError("regions table does not cover the included identity decisions")
    validate_all(
        sources,
        repository_root=root,
        raw_dir=raw_dir,
        include_restricted=True,
    )
    identities = collect_source_identities(
        sources,
        repository_root=root,
        raw_dir=raw_dir,
    )
    coverage = crosswalk.coverage(identities)
    if coverage.missing or coverage.duplicate:
        raise ValueError(f"country-map coverage is incomplete: {coverage}")

    whr_path = resolve_source_path(
        sources.whr, repository_root=root, raw_dir=raw_dir
    )
    aqli_path = resolve_source_path(
        sources.aqli, repository_root=root, raw_dir=raw_dir
    )
    country_lock = sources.lock("wdi_country_metadata")
    country_path = resolve_source_path(
        country_lock, repository_root=root, raw_dir=raw_dir
    )
    _validate_wdi_metadata_decisions(
        _read_wdi_country_metadata(country_path), crosswalk
    )

    exclusions: list[dict[str, object]] = []
    happiness = normalize_whr(
        read_whr_annual(whr_path, years=method.years),
        crosswalk,
        exclusions=exclusions,
    )
    aqli = normalize_aqli(
        read_aqli(aqli_path, years=method.years),
        crosswalk,
        exclusions=exclusions,
    )
    aqli_raw = pd.read_csv(
        aqli_path,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
    )
    record_aqli_missing_fields(
        aqli_raw,
        years=method.years,
        crosswalk=crosswalk,
        exclusions=exclusions,
    )

    wdi_keys = (
        "wdi_population",
        "wdi_life_expectancy",
        "wdi_ghg_total",
        "wdi_ghg_co2",
        "wdi_ghg_ch4",
        "wdi_ghg_n2o",
    )
    observations: dict[str, pd.DataFrame] = {}
    for key in wdi_keys:
        lock = sources.lock(key)
        if lock.expected_indicator is None:
            raise ValueError(f"WDI observation lock lacks an indicator: {key}")
        path = resolve_source_path(lock, repository_root=root, raw_dir=raw_dir)
        observations[lock.expected_indicator] = read_wdi_observations(
            path,
            lock,
            years=method.years,
            expected_lastupdated=sources.wdi_lastupdated,
        )
        try:
            raw_observation_rows = json.loads(path.read_text(encoding="utf-8"))[1]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            IndexError,
            TypeError,
        ) as error:
            raise ValueError("validated WDI observation rows cannot be read") from error
        if not isinstance(raw_observation_rows, list) or not all(
            isinstance(row, dict) for row in raw_observation_rows
        ):
            raise ValueError("validated WDI observation rows are invalid")
        record_wdi_skipped_identities(
            raw_observation_rows,
            indicator=lock.expected_indicator,
            crosswalk=crosswalk,
            exclusions=exclusions,
        )
    indicator_columns = {
        "SP.POP.TOTL": "population",
        "SP.DYN.LE00.IN": "life_expectancy",
        method.ghg_total_indicator: "ghg_total",
        method.ghg_co2_indicator: "ghg_co2",
        method.ghg_ch4_indicator: "ghg_ch4",
        method.ghg_n2o_indicator: "ghg_n2o",
    }
    wdi = normalize_wdi(
        observations,
        crosswalk,
        indicator_columns=indicator_columns,
        exclusions=exclusions,
    )
    exclusion_detail = pd.DataFrame.from_records(
        exclusions, columns=EXCLUSION_COLUMNS
    ).sort_values(
        ["source", "year", "source_key", "stage", "reason"],
        kind="stable",
        ignore_index=True,
    )
    exclusion_summary = build_public_exclusion_summary(exclusion_detail, threshold=5)

    frames = {
        "happiness": happiness,
        "wdi": wdi,
        "aqli": aqli,
        "exclusions": exclusion_detail,
        "exclusion_summary": exclusion_summary,
    }
    written: list[Path] = []
    artifact_entries: list[dict[str, object]] = []
    for key, frame in frames.items():
        logical_path, disclosure_class = OUTPUTS[key]
        destination = _destination(derived_root, logical_path)
        _write_csv(frame, destination)
        written.append(destination)
        artifact_entries.append(
            _artifact_manifest_entry(key, destination, frame, disclosure_class)
        )

    manifest_destination = _destination(derived_root, MANIFEST_LOGICAL_PATH)
    _write_manifest(
        source_manifest=root / MANIFEST_LOGICAL_PATH,
        destination=manifest_destination,
        artifacts=artifact_entries,
    )
    written.append(manifest_destination)
    return tuple(written)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    normalize = subcommands.add_parser("normalize", help="normalize locked annual inputs")
    normalize.add_argument("--method", type=Path, default=Path("config/method.toml"))
    normalize.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    normalize.add_argument(
        "--disclosure", type=Path, default=Path("config/disclosure.toml")
    )
    normalize.add_argument(
        "--country-map", type=Path, default=Path("config/country_map.csv")
    )
    normalize.add_argument("--regions", type=Path, default=Path("config/regions.csv"))
    normalize.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw/external")
    )
    normalize.add_argument("--derived-dir", type=Path, default=Path("data/derived"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "normalize":
        normalize_all(
            method_path=args.method,
            sources_path=args.sources,
            disclosure_path=args.disclosure,
            country_map_path=args.country_map,
            regions_path=args.regions,
            raw_dir=args.raw_dir,
            derived_dir=args.derived_dir,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
