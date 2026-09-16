# ERHNI Reproducible Pipeline Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the legacy ERHNI notebooks with a tested, deterministic Python pipeline that acquires and validates pinned official inputs, constructs the 2016-2018 balanced annual panel, generates primary and sensitivity results, reconciles legacy outputs, and locks every numeric artifact needed to rewrite the paper.

**Architecture:** A small `src/erhni` package separates configuration, source acquisition, identity mapping, annual normalization, scientific metrics, sample construction, aggregation, sensitivities, reconciliation, figures, and deterministic output I/O. Source locks and method choices live in TOML; country decisions live in reviewed CSV crosswalks; every output is a pure function of pinned source bytes plus committed configuration. Restricted raw WHR/AQLI files and their row-level derivatives stay in ignored classified directories; permitted source snapshots, aggregate diagnostics/results, and closure manifests are committed through an explicit public allow-list.

**Tech Stack:** Python 3.12, uv, pandas, NumPy, SciPy, Matplotlib, xlrd, openpyxl, pytest, pytest-cov, Ruff, and the standard-library `tomllib`, `hashlib`, `json`, `zipfile`, and `urllib` modules.

**Approved design:** `docs/superpowers/specs/2026-07-17-erhni-reproducible-submission-design.md` at or after commit `64e385b`.

**Execution boundary:** This plan locks analysis outputs. After Task 13 passes, write a second TDD plan for the manuscript, supplement, DOCX comparison copy, cover letter, submission checklist, and release archive. Do not finalize results prose before Task 13.

---

## Task 1: Preserve the exact legacy tree before creating active data paths

**Files:**

- Create before any environment command: `.gitignore`
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `scripts/archive_legacy.py`
- Create: `tests/test_legacy_archive.py`
- Create: `archive/legacy-2022/README.md`
- Create: `archive/legacy-2022/original-paths.txt`
- Create: `archive/legacy-2022/sha256.txt`
- Move: every path listed below to `archive/legacy-2022/original/<same-path>` with `git mv`

### Step 1: Write the failing archive-integrity test

Before the first `uv` or pytest command, create a minimal fail-safe `.gitignore` covering `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `**/__pycache__/`, `*.pyc`, `.coverage`, `htmlcov/`, `.DS_Store`, `data/raw/external/`, `data/derived/restricted/`, `outputs/restricted/`, and `outputs/review/`. Later tasks may extend but never weaken it.

The test must read the frozen path/hash manifests, assert that every listed path exists under `archive/legacy-2022/original/`, assert that no listed path remains active, and recompute each SHA-256. It must also assert that newly created `data/raw/`, `data/snapshots/`, and `data/derived/` paths are not archive candidates.

Test `scripts/archive_legacy.py --check-staged` against a temporary index: it must fail if an environment/cache, ignored restricted path, or unclassified generated path is staged.

Run:

```bash
uv run pytest tests/test_legacy_archive.py -q
```

Expected: failure because the archive and manifests do not exist.

### Step 2: Freeze the exact base tree and hashes, then move only those paths

The source set is exactly the files returned by `git ls-tree -r --name-only 669f6e2`:

```text
.ipynb_checkpoints/erhni_2016-checkpoint.ipynb
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
merged_y.csv
```

`scripts/archive_legacy.py` must verify that this literal list equals the base tree, hash each working-tree byte sequence before moving, invoke `git mv` one path at a time, and write deterministic sorted manifests. It must refuse to run if a path is missing, changed during the move, outside this list, or already under an active new-data directory. `archive/legacy-2022/README.md` labels every item forensic and outside the active calculation path.

### Step 3: Verify GREEN

```bash
uv lock
uv run pytest tests/test_legacy_archive.py -q
git diff --check
```

Expected: exact path and byte-hash preservation; no active legacy input paths remain.

### Step 4: Commit the complete rename set

```bash
git add -A
uv run python scripts/archive_legacy.py --check-staged
git commit -m "chore: preserve legacy ERHNI artifacts"
```

---

## Task 2: Package foundation and fail-closed method/source configuration

**Files:**

- Update: `pyproject.toml`
- Create: `src/erhni/__init__.py`
- Create: `src/erhni/config.py`
- Create: `src/erhni/disclosure.py`
- Create: `config/method.toml`
- Create: `config/sources.toml`
- Create: `config/disclosure.toml`
- Create: `tests/test_config.py`
- Create: `tests/test_disclosure.py`
- Create: `tests/conftest.py`
- Update: `uv.lock`

### Step 1: Write failing configuration tests

Create tests that load both TOML files and assert all review pin-downs before any result code exists:

```python
def test_primary_method_pins_universes(method):
    assert method.years == (2016, 2017, 2018)
    assert method.burden_universe == "aqli_full_wdi_population"
    assert method.allocation_denominator == "wdi_wld"
    assert method.happiness_weight_universe == "balanced_analysis_panel"
    assert method.ranking_universe == "balanced_complete_case"
    assert method.max_abs_wld_reconciliation_share == 0.05


def test_primary_weight_is_net_and_gross_is_only_a_sensitivity(method):
    assert method.headline_weight == "population_weighted_net_happiness"
    assert method.neutral_point == 5.0
    assert method.gross_penalty_sensitivity is True
    assert method.nonpositive_weight == "error"


def test_ghg_family_is_explicit_and_has_no_fallback(method):
    assert method.primary_ghg_family == "edgar_ar5_excl_lulucf"
    assert method.ghg_total_indicator == "EN.GHG.ALL.MT.CE.AR5"
    assert method.ghg_fallback_family is None
```

Add source-lock assertions for:

- WHR archive URL and SHA-256 `f118e7f606f091b978edc674242b491b79ee37bea6cb2b5243f805f5f39ccfa4`;
- AQLI URL and SHA-256 `65bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73`;
- WDI observation hashes:
  - `SP.POP.TOTL`: `37c342714703650a21a159153626e42f114005220d77e60eeff835c70b95bd66`;
  - `SP.DYN.LE00.IN`: `5bf9cb1fab1a58a5eef347da0fe0356fb80ff1539171deebc41455f8ecf47693`;
  - `EN.GHG.ALL.MT.CE.AR5`: `68207c08d82f19942abb8a4437449079a4d46a645d4136ccb7698ab983d79b58`;
  - `EN.GHG.CO2.MT.CE.AR5`: `a97b7839bc570ff012478ca1db8661c4ae4ca502ee4d8188a86ea922eed0f8d0`;
  - `EN.GHG.CH4.MT.CE.AR5`: `5a5dbd12458e21022f3264faa43349dd94a061a68fb552889f5c6d806605eae4`;
  - `EN.GHG.N2O.MT.CE.AR5`: `e862b242cccfc9b78ba92c2f2341e5da888061d00629ab74ab5d347202ee2b79`;
  - country metadata: `d29d57f8adf954c5e2a1520a02fb2c7b45575d8db3bd327a9dff47d66914231c`;
- WDI indicator-metadata hashes:
  - population: `2f8491efc00bf2c0995112ff8e87aba69e5e9d22d0880b22f7e3a4ec757ba05c`;
  - life expectancy: `a39cb6fddfbbb953053690366243dffe77a266c4deae79c46ce5a06da9f5fc31`;
  - total GHG: `cc3dc0cec5b9a6bd3874cfc8c3e4f0e7ee5232f8726927d9784b6abdcc8e3ed8`;
  - CO2: `b589d061bd920762db1bc986fd2e8f75cb25aeb940509907a1906fd40484e839`;
  - CH4: `708193dc91019e5dee1d8c426a67fca4967ca2fedac12598ab64730e4037375e`;
  - N2O: `c4d6c1792a8a4ce42271b0237e08af0a1362de841965cad4a7f6a7131e0adf8e`;
- DS57 archive ZIP hashes:
  - total GHG: `ba749f90dc55b7373c3b7b7eab0cd7c8eb5dac9a070c6a746225c90f94271ba8`;
  - CH4: `c1bf878a5bad6151bde1258e5f4c25fddfa9a5862180927c6e25e2127d2fbb54`;
  - N2O: `d9aec51af3b04beeeb0389e218eb43b18f1a526d4d42bc3325726ffd866efad9`.

Pin the corresponding official World Bank retrieval URLs and durable committed paths:

```text
https://api.worldbank.org/v2/en/indicator/EN.ATM.GHGT.KT.CE?downloadformat=csv  data/snapshots/wdi_archive/EN.ATM.GHGT.KT.CE.zip
https://api.worldbank.org/v2/en/indicator/EN.ATM.METH.KT.CE?downloadformat=csv  data/snapshots/wdi_archive/EN.ATM.METH.KT.CE.zip
https://api.worldbank.org/v2/en/indicator/EN.ATM.NOXE.KT.CE?downloadformat=csv  data/snapshots/wdi_archive/EN.ATM.NOXE.KT.CE.zip
```

Also test that an unknown universe, automatic source fallback, a non-5 AQLI benchmark, a nonpositive residual tolerance, or use of retired `EN.ATM.GHGT.KT.CE` as the primary indicator raises `ConfigError`.

Add disclosure tests requiring one explicit data/artifact class for every planned raw, snapshot, derived, output, figure, and table path. Allowed disclosure classes are `public_snapshot`, `public_aggregate`, `restricted_source`, `restricted_derived`, and `review_only`. WHR/AQLI raw files are `restricted_source`; row-level happiness, AQLI, exclusions, country-year, ranking, sensitivity, and rank-comparison files are `restricted_derived`; figures/tables that reveal country-level values are `review_only` until written rights confirmation; WDI and EDGAR official snapshots are `public_snapshot`. No restricted or review-only path may be staged by the release allow-list.

Keep release roles separate from scientific disclosure classes. Every staged path has exactly one release role from `public_code`, `public_config`, `public_documentation`, `public_evidence`, `public_snapshot`, or `public_aggregate`; data/artifact paths additionally retain their disclosure class. A restricted/review-only disclosure class can never map to a public release role. Tests cover code, configs, tests, scripts, documentation, evidence, snapshots, and aggregate outputs so non-data files are not forced into a false scientific classification.

### Step 2: Run the tests and verify RED

Run:

```bash
uv run pytest tests/test_config.py tests/test_disclosure.py -q
```

Expected: collection or import failure because `erhni.config` and the TOML files do not exist.

### Step 3: Add the minimal package and validated dataclasses

Use frozen dataclasses or equivalent immutable objects. `load_method()` and `load_sources()` must resolve paths relative to the repository/config file, validate enumerated values, and retain source hashes as lowercase 64-character hexadecimal strings.

The method file must pin:

```toml
[analysis]
years = [2016, 2017, 2018]

[universes]
burden = "aqli_full_wdi_population"
allocation_denominator = "wdi_wld"
happiness_weight = "balanced_analysis_panel"
ranking = "balanced_complete_case"

[nhly]
neutral_point = 5.0
scale = 10.0

[responsibility]
headline_weight = "population_weighted_net_happiness"
nonpositive_weight = "error"
max_abs_wld_reconciliation_share = 0.05

[ghg]
primary_family = "edgar_ar5_excl_lulucf"
total_indicator = "EN.GHG.ALL.MT.CE.AR5"
co2_indicator = "EN.GHG.CO2.MT.CE.AR5"
ch4_indicator = "EN.GHG.CH4.MT.CE.AR5"
n2o_indicator = "EN.GHG.N2O.MT.CE.AR5"
fallback_family = "none"

[sensitivity]
gross_penalty_weight = true
fixed_penalty_weights = [0.05, 0.10, 0.25, 0.50, 0.765, 1.00]
neutral_points = [4.0, 4.5, 5.0, 5.1]

[uncertainty]
aqli_rounding_half_width = 0.05
lower_bound_floor = 0.0
label = "rounding_sensitivity_not_confidence_interval"

[reconciliation]
decomposition = "shapley"
absolute_tolerance = 1e-9
relative_tolerance = 1e-10
```

`sources.toml` must include each exact URL, snapshot path, publisher, source family, unit, expected source ID, access date `2026-07-17`, redistribution flag, and hash. Record `WDI lastupdated = "2026-07-13"`, `AQLI source_updated_at = "2025-08-19T13:13:14Z"`, and the WHR provenance page/capture timestamp. The archive and successor families must have different names and no fallback relationship.

`disclosure.toml` is fail closed: every generated data/artifact path must match exactly one disclosure rule; every potentially staged path must match exactly one release-role rule; public staging reads only release roles; and rights confirmation changes classification only through a reviewed config commit. A manifest/hash of a restricted file may be public evidence; its row-level contents may not.

### Step 4: Lock dependencies and verify GREEN

Run:

```bash
uv lock
uv run pytest tests/test_config.py tests/test_disclosure.py -q
uv run ruff check src tests
```

Expected: all configuration tests pass; Ruff reports no errors.

### Step 5: Commit

```bash
git add pyproject.toml uv.lock src/erhni/__init__.py src/erhni/config.py src/erhni/disclosure.py config/method.toml config/sources.toml config/disclosure.toml tests/conftest.py tests/test_config.py tests/test_disclosure.py
git commit -m "build: pin ERHNI method and source configuration"
```

---

## Task 3: Checksum-verified acquisition and source-schema validation

**Files:**

- Update: `.gitignore`
- Create: `src/erhni/sources.py`
- Create: `src/erhni/hashing.py`
- Create: `tests/fixtures/sources/`
- Create: `tests/test_sources.py`
- Create: `data/snapshots/wdi/*.json` and `data/snapshots/wdi/*.metadata.json` from the already hash-pinned official WDI responses
- Create: `data/snapshots/wdi_archive/*.zip` from the three already hash-pinned official DS57 downloads
- Create: `data/derived/source_manifest.json` through the acquisition command

### Step 1: Write failing acquisition and validation tests

Cover these behaviors with small local fixtures and an injected downloader:

```python
def test_acquire_rejects_wrong_hash(tmp_path, source_lock):
    with pytest.raises(SourceIntegrityError, match="sha256"):
        acquire_one(source_lock, tmp_path, downloader=lambda _: b"changed")


def test_whr_schema_is_annual_and_unique(whr_fixture):
    frame = read_whr_annual(whr_fixture, years=(2016, 2017, 2018))
    assert set(frame.columns) == {"source_name", "year", "life_ladder"}
    assert not frame.duplicated(["source_name", "year"]).any()


def test_aqli_direct_fields_and_sentinels(aqli_fixture):
    frame = read_aqli(aqli_fixture, years=(2016, 2017, 2018))
    assert tuple(frame.query("iso3 == 'CHN'").sort_values("year").aqli_years_lost) == (3.4, 3.1, 2.7)
    assert tuple(frame.query("iso3 == 'IND'").sort_values("year").aqli_years_lost) == (4.2, 4.1, 4.1)
    assert tuple(frame.query("iso3 == 'ABW'").sort_values("year").aqli_years_lost) == (0.0, 0.0, 0.0)
```

Also test:

- WHR requires `Country name`, `year`, and `Life Ladder`, selects only 2016-2018, accepts no duplicated country-year, and never reads Figure 2.1 pooled scores;
- AQLI requires `id`, `whostandard`, `who2016`, `who2017`, and `who2018`; zeros are valid; blanks are exclusions; negatives and `whostandard != 5` are errors;
- WDI observations contain the configured indicator, years, source, units, unique ISO3-year rows, and `WLD`;
- WDI metadata states source ID `2`, Mt CO2e, AR5, and excludes LULUCF for successor GHG series;
- CH4 and N2O are recognized as already CO2-equivalent;
- DS57 ZIPs resolve to committed `data/snapshots/wdi_archive/` files, identify source 57, validate member schemas offline, and cannot be passed to the successor parser;
- the manifest is stable, sorted, contains configured access dates rather than the wall clock, and never includes machine-local absolute paths.
- redistributable WDI observations/metadata resolve to committed `data/snapshots/wdi/` files and validate offline in a fresh temporary checkout;
- restricted WHR/AQLI bytes resolve only to ignored `data/raw/external/` paths and are rejected by the public release allow-list.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_sources.py -q
```

Expected: import failure for `erhni.sources` or missing functions.

### Step 3: Implement atomic acquisition, verification, and parsers

Acquisition requirements:

- download to `*.part`, hash bytes, then atomically replace the destination only on a match;
- allow already-present verified files without network access;
- fail closed on unavailable sources, wrong hash, wrong schema, wrong family, or unexpected WDI metadata;
- write restricted inputs under `data/raw/external/`, ignored by Git;
- write the exact already-pinned WDI response/metadata bytes under `data/snapshots/wdi/` and all three DS57 ZIP bytes under `data/snapshots/wdi_archive/`, then commit them so mutable APIs cannot strand future clones; live WDI URLs are provenance/update inputs, not required by an offline build from the pinned bundle;
- write a deterministic `data/derived/source_manifest.json` containing publisher, release, original URL, retrieval URL, access date, expected/observed hashes, byte count, schema summary, rights note, and configured family;
- expose `python -m erhni.sources acquire --config config/sources.toml --raw-dir data/raw/external`.

Do not copy the WHR or AQLI raw files or their row-level normalized derivatives into committed directories. WDI/EDGAR redistribution decisions remain explicit in the manifest.

### Step 4: Run unit tests, then acquire and validate real pinned inputs

```bash
uv run pytest tests/test_sources.py -q
uv run python -m erhni.sources acquire --config config/sources.toml --raw-dir data/raw/external
uv run python -m erhni.sources validate --config config/sources.toml --raw-dir data/raw/external
```

Expected: tests pass; all configured sources validate; `data/derived/source_manifest.json` is produced. If a mutable WDI endpoint no longer matches, use the already acquired 17 July 2026 snapshots, retain their exact bytes under `data/snapshots/wdi/`, and document the pinned snapshot rather than changing a hash silently.

### Step 5: Commit

```bash
git add .gitignore src/erhni/sources.py src/erhni/hashing.py tests/fixtures/sources tests/test_sources.py data/snapshots/wdi data/snapshots/wdi_archive data/derived/source_manifest.json
git commit -m "feat: acquire and validate pinned ERHNI sources"
```

---

## Task 4: Explicit country identity, annual normalization, and exclusion evidence

**Files:**

- Create: `config/country_map.csv`
- Create: `config/regions.csv`
- Create: `src/erhni/countries.py`
- Create: `src/erhni/years.py`
- Create: `tests/test_countries.py`
- Create: `tests/test_years.py`
- Generate, restricted and ignored: `data/derived/restricted/happiness_annual.csv`
- Generate and commit: `data/derived/public/wdi_annual.csv`
- Generate, restricted and ignored: `data/derived/restricted/aqli_annual.csv`
- Generate, restricted and ignored: `data/derived/restricted/source_exclusions.csv` containing row keys and terminal reasons
- Generate and commit: `data/derived/public/source_exclusion_summary.csv` containing disclosure-controlled aggregate counts only
- Update and commit: `data/derived/source_manifest.json` with hashes/classifications for all five files

### Step 1: Write failing identity and annual-normalization tests

Required tests:

```python
def test_sensitive_territories_are_not_sovereign_aliases(crosswalk):
    assert crosswalk.resolve("whr", "North Cyprus").status == "exclude"
    assert crosswalk.resolve("whr", "North Cyprus").iso3 is None
    assert crosswalk.resolve("whr", "Somaliland region").status == "exclude"
    assert crosswalk.resolve("whr", "Somaliland region").iso3 is None


def test_every_source_name_has_one_explicit_decision(raw_names, crosswalk):
    decisions = crosswalk.coverage(raw_names)
    assert decisions.missing == ()
    assert decisions.duplicate == ()


def test_annual_inputs_are_not_imputed(normalized):
    assert set(normalized.year.unique()) == {2016, 2017, 2018}
    assert not normalized.imputed.any()
```

Also test `Ivory Coast -> CIV`, `Trinidad & Tobago -> TTO`, `Turkey -> TUR`, `Vietnam -> VNM`, the two Congos as distinct ISO3 codes, and Taiwan as an explicit include/exclude decision rather than a silent name match. Require unique `(source, source_name)` decisions and unique `(iso3, year)` normalized rows. Detailed restricted exclusions preserve every source key/reason. The public summary contains no record/country key, applies coordinated suppression to cells with counts below five, and exposes no overlapping margins from which a singleton can be recovered by subtraction.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_countries.py tests/test_years.py -q
```

Expected: imports/files missing.

### Step 3: Implement reviewed mappings and normalization

`country_map.csv` columns:

```text
source,source_name,canonical_iso3,display_name,status,reason
```

Allowed statuses are `include`, `exclude`, and `aggregate`. Blank decisions are invalid. Bootstrap candidate names mechanically from source files, but review and commit every final row. AQLI and WDI ISO3 codes still pass through validation; no direct name join is allowed.

`regions.csv` must hold one canonical row per included ISO3 and preserve the official source region plus the manuscript display region. Region aggregates from WDI are not countries.

Normalization rules:

- WHR: select direct annual Life Ladder values for 2016-2018;
- WDI: select same-year population, life expectancy, and four successor GHG series; preserve `WLD` separately and classify aggregates from country metadata;
- AQLI: reshape direct `who2016`-`who2018` columns without rounding or recalculation;
- never impute; write every dropped source row to restricted `source_exclusions.csv` with source, source key, year, stage, and reason;
- sort by `source`, `year`, and `iso3`; write LF-terminated UTF-8 CSV with stable float formatting;
- enforce `config/disclosure.toml` before writing: restricted row-level files go only to ignored `data/derived/restricted/`; the public exclusion summary contains only coordinated-threshold aggregate counts by broad source/stage/reason groups and no record/country identifiers or restricted numeric values.

Expose `python -m erhni.years normalize` to regenerate the five derived CSVs.

### Step 4: Verify real-source coverage

```bash
uv run pytest tests/test_countries.py tests/test_years.py -q
uv run python -m erhni.years normalize --method config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --derived-dir data/derived
uv run pytest tests/test_countries.py tests/test_years.py -q
```

Expected: all raw names have explicit decisions; derived keys are unique; no hard-coded final sample count appears in source or config.

### Step 5: Commit

```bash
git add config/country_map.csv config/regions.csv src/erhni/countries.py src/erhni/years.py tests/test_countries.py tests/test_years.py data/derived/public/wdi_annual.csv data/derived/public/source_exclusion_summary.csv data/derived/source_manifest.json
git commit -m "feat: normalize annual ERHNI inputs with explicit identities"
```

---

## Task 5: Scientific metric kernel and allocation conservation

**Files:**

- Create: `src/erhni/metrics.py`
- Create: `src/erhni/allocation.py`
- Create: `tests/test_metrics.py`
- Create: `tests/test_allocation.py`

### Step 1: Write failing formula tests with exact synthetic values

```python
def test_nhly():
    assert nhly(happiness=6.0, life_expectancy=80.0, neutral=5.0, scale=10.0) == pytest.approx(8.0)


def test_population_weighted_net_weight():
    # H=[4,6], N=[1,3] => Hbar=5.5, w=.05
    assert net_lost_year_weight([4.0, 6.0], [1.0, 3.0], neutral=5.0) == pytest.approx(0.05)


def test_nonpositive_weight_is_an_error():
    with pytest.raises(NonPositiveWeightError):
        net_lost_year_weight([4.0, 6.0], [1.0, 1.0], neutral=5.0)


def test_gross_minus_net_weight_is_one_half():
    assert gross_lost_year_weight([4.0, 6.0], [1.0, 3.0]) - net_lost_year_weight([4.0, 6.0], [1.0, 3.0]) == pytest.approx(0.5)
```

Allocation fixture: `B=700`, `w=.05`, `G_WLD=100`, country emissions `[20, 70]`. Shares are `.2` and `.7`, country allocations are `7` and `24.5`, signed residual share is `.1`, residual allocation is `3.5`, and total conserved allocation is `35 = wB`. If populations are `[100, 350]`, per-capita penalties are `.07` and `.07`.

Also test:

- AQLI burden includes every valid AQLI-WDI population row, including zeros, independently of the ranked sample;
- duplicate AQLI rows, negative loss, zero/nonfinite population, or missing mapping become explicit errors/exclusions according to the contract;
- WLD is the denominator and country shares are never renormalized;
- signed residuals of either sign work, while `abs(residual_share) > 0.05` fails for primary;
- allocations without population remain in total conservation but have no per-capita penalty;
- row order and common population-scale invariance;
- `ERHNI = NHLY - penalty` row by row;
- corrected three-gas is direct `CO2e + CH4e + N2Oe`; no GWP multiplier exists in the code path.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_metrics.py tests/test_allocation.py -q
```

Expected: imports missing.

### Step 3: Implement pure, vectorized metric functions

Keep formulas side-effect free and explicit about units. Return named dataclasses/data frames containing the burden universe count, burden person-years, `Hbar`, net/gross weights, WLD total, every source share, total allocation, per-capita penalty status, and signed residual. Validate finite inputs before arithmetic.

Do not import file or network modules into `metrics.py` or `allocation.py`.

### Step 4: Verify GREEN and coverage

```bash
uv run pytest tests/test_metrics.py tests/test_allocation.py -q --cov=erhni.metrics --cov=erhni.allocation --cov-report=term-missing
uv run ruff check src/erhni/metrics.py src/erhni/allocation.py tests/test_metrics.py tests/test_allocation.py
```

Expected: all tests pass and all scientific branches are exercised.

### Step 5: Commit

```bash
git add src/erhni/metrics.py src/erhni/allocation.py tests/test_metrics.py tests/test_allocation.py
git commit -m "feat: implement tested ERHNI scientific metrics"
```

---

## Task 6: Balanced sample and in-memory primary analysis model

**Files:**

- Create: `src/erhni/sample.py`
- Create: `src/erhni/pipeline.py`
- Create: `tests/test_sample.py`
- Create: `tests/test_pipeline.py`

### Step 1: Write failing sample and in-memory integration tests

Test sample construction on fixtures where countries fail at different stages. The flow counts must be computed from rows, not constants. Require balance across exactly three years, complete primary inputs, one ISO3-year row, and stable alphabetical tie-breaking after metric rank.

```python
def test_primary_model_invariants(primary_result):
    panel = primary_result.country_year
    assert set(panel.year) == {2016, 2017, 2018}
    assert panel.groupby("iso3").size().eq(3).all()
    np.testing.assert_allclose(panel.erhni, panel.nhly - panel.penalty, rtol=1e-12, atol=1e-12)
    ledger = primary_result.allocation_ledger.groupby("year", as_index=True).allocated_happy_person_years.sum()
    target = primary_result.year_summary.set_index("year").weighted_aqli_burden
    assert ledger.index.equals(target.index)
    np.testing.assert_allclose(ledger.to_numpy(), target.to_numpy(), rtol=1e-12, atol=1e-6)
    assert set(primary_result.allocation_ledger.query("ledger_role == 'wld_reconciliation_residual'").year) == {2016, 2017, 2018}
```

Also test that the happiness weight is calculated only after balanced-panel construction; burden and allocation universes do not shrink to the ranking sample; every exclusion has one terminal reason; and the same input frames in a different row order yield identical sorted model frames.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_sample.py tests/test_pipeline.py -q
```

Expected: `erhni.sample` and the primary model builder are missing.

### Step 3: Implement the pure in-memory model graph

`build_primary_model(method, happiness, wdi, aqli, crosswalk, regions)` returns named data frames but writes no files. Its order is fixed:

1. validate normalized annual inputs;
2. construct the sample-independent AQLI burden and full GHG responsibility/share ledgers;
3. construct maximal complete-case rows and then the balanced ranking panel;
4. compute `Hbar`/`w` on the balanced panel;
5. apply pre-defined country allocations and per-capita penalties;
6. rank descending by metric, then ISO3 ascending for ties;
7. return country-year, burden, allocation, exclusion, flow, and year-summary frames.

No network, filesystem, serialization, or CLI code belongs in this task.

### Step 4: Verify GREEN

```bash
uv run pytest tests/test_sample.py tests/test_pipeline.py -q --cov=erhni.sample --cov=erhni.pipeline --cov-report=term-missing
uv run ruff check src/erhni/sample.py src/erhni/pipeline.py tests/test_sample.py tests/test_pipeline.py
```

### Step 5: Commit

```bash
git add src/erhni/sample.py src/erhni/pipeline.py tests/test_sample.py tests/test_pipeline.py
git commit -m "feat: build balanced in-memory ERHNI model"
```

---

## Task 7: Deterministic aggregation, classified outputs, and primary CLI

**Files:**

- Create: `src/erhni/aggregate.py`
- Create: `src/erhni/output.py`
- Create: `src/erhni/cli.py`
- Create: `tests/test_aggregate.py`
- Create: `tests/test_output.py`
- Create: `tests/test_cli.py`
- Generate, restricted and ignored: `outputs/restricted/country_year.csv`
- Generate, restricted and ignored: `outputs/restricted/burden_universe.csv`
- Generate, restricted and ignored: `outputs/restricted/allocation_ledger.csv`
- Generate, restricted and ignored: `outputs/restricted/rankings.csv`
- Generate, restricted and ignored: `outputs/restricted/exclusions.csv`
- Generate and commit: `outputs/public/exclusion_summary.csv`
- Generate and commit: `outputs/public/sample_flow.csv`
- Generate and commit: `outputs/public/global_summary.csv`
- Generate and commit: `outputs/public/regional_summary.csv`
- Generate and commit: `outputs/manifest.json`

### Step 1: Write failing aggregation, disclosure, serialization, and CLI tests

Test distinct unweighted-country and population-weighted-resident aggregates; regional/global reconciliation; explicit column order; stable `%.12g` floats; LF endings; atomic writes; and deterministic relative hashes. `manifest.json` excludes itself and both lock paths from its output-hash map. Every emitted data/artifact path must have exactly one disclosure class, and public staging must reject every restricted file. Public exclusion/sample-flow tables contain coordinated-threshold counts only; regional aggregates with fewer than five underlying countries are suppressed into a broader region, and published margins cannot disclose singleton country values by subtraction.

```python
def test_second_build_is_byte_identical(tmp_path, configured_workspace):
    first = build_all(
        method_path=configured_workspace.method,
        sources_path=configured_workspace.sources,
        disclosure_path=configured_workspace.disclosure,
        raw_dir=configured_workspace.raw,
        output_dir=tmp_path / "a",
        offline=True,
    )
    second = build_all(
        method_path=configured_workspace.method,
        sources_path=configured_workspace.sources,
        disclosure_path=configured_workspace.disclosure,
        raw_dir=configured_workspace.raw,
        output_dir=tmp_path / "b",
        offline=True,
    )
    assert directory_hashes(first) == directory_hashes(second)
```

Test that `--offline` fails clearly if a restricted raw source is absent and never switches sources.

Define repo-relative defaults `--sources config/sources.toml`, `--disclosure config/disclosure.toml`, and `--raw-dir data/raw/external`. Add a CLI integration test that changes to the repository root and invokes the approved canonical command verbatim:

```bash
uv run erhni all --config config/method.toml --output-dir outputs
```

The test must prove that these defaults resolve relative to the repository/config location rather than the caller's home directory and produce the same hashes as the explicit long form.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_aggregate.py tests/test_output.py tests/test_cli.py -q
```

Expected: aggregate/output/CLI modules missing.

### Step 3: Implement primary orchestration and classified writes

The `all` graph now verifies/acquires pinned sources, normalizes them, calls `build_primary_model`, aggregates, writes restricted and public outputs to separate directories, and writes one manifest containing both sets of hashes/classes without exposing restricted rows. Use stable sorts, explicit schemas, configured access dates rather than wall-clock times, and no machine-local absolute paths.

Expose the approved short command, while retaining explicit overrides for nonstandard workspaces:

```bash
uv run erhni all --config config/method.toml --output-dir outputs
```

### Step 4: Build real primary outputs and verify determinism

```bash
uv run pytest tests/test_aggregate.py tests/test_output.py tests/test_cli.py -q
uv run erhni all --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
cp -R outputs /tmp/erhni-outputs-first
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
diff -ru /tmp/erhni-outputs-first outputs
```

Expected: all files exist at their classified paths; `diff` has no output; only `outputs/public/` and hash/classification manifests are eligible for staging.

### Step 5: Commit only public-safe contents

```bash
git add src/erhni/aggregate.py src/erhni/output.py src/erhni/cli.py tests/test_aggregate.py tests/test_output.py tests/test_cli.py outputs/public outputs/manifest.json
git commit -m "feat: generate classified deterministic ERHNI outputs"
```

---

## Task 8: Normative weights, neutral points, GHG boundaries, samples, and rank sensitivities

**Files:**

- Create: `src/erhni/sensitivity.py`
- Create: `tests/test_sensitivity.py`
- Update: `src/erhni/pipeline.py`
- Update: `src/erhni/cli.py`
- Update: `tests/test_cli.py`
- Generate, restricted and ignored: `outputs/restricted/sensitivities.csv`
- Generate, restricted and ignored: `outputs/restricted/rank_robustness.csv`
- Generate and commit: `outputs/public/sensitivity_summary.csv`
- Update: `outputs/manifest.json`

### Step 1: Write failing sensitivity tests

Cover one-factor-at-a-time scenarios with explicit labels and reference method:

- headline observed net weight;
- gross penalty-only weight `Hbar/10`, labeled unit-inconsistent with net NHLY;
- fully gross alternative where both achievement and penalty use zero neutral point, labeled a different index;
- fixed penalty weights `0.05`, `0.10`, `0.25`, `0.50`, `0.765`, and `1.00`;
- NHLY neutral points `4.0`, `4.5`, `5.0`, and `5.1`;
- no-penalty control as a separate scenario, not a successful zero weight;
- total GHG, direct current three-gas sum, and CO2-only keys;
- balanced and maximal-coverage samples;
- same-year alignment for every Task 8 scenario;
- unweighted-country and population-weighted aggregates.
- formula-only legacy corrected branch `0.765 * current_aligned_aqli * emissions_ratio`, labeled `legacy_formula_sensitivity` and never headline eligible;
- formula-only stored ten-times branch `7.65 * current_aligned_aqli * emissions_ratio`, labeled `replication_formula_only` and never headline eligible;
- AQLI rounding bounds `max(0, A - 0.05)` and `A + 0.05`, labeled a deterministic rounding-sensitivity envelope and never a confidence interval.

Tests must prove fixed-weight penalty linearity, `gross-net=.5`, no second GWP conversion, observed weight range generated from output rather than config, expected failure when a neutral point makes `w <= 0`, and unique scenario/year/ISO3 keys.

Rank tests must produce Spearman, Kendall, top-10 overlap, and count/list of rank crossings. No robustness prose or boolean may be generated from an unconfigured threshold.

Add the CLI deletion/recreation test now, before implementation: delete both sensitivity files, invoke `erhni all`, and require their exact recreated hashes. It must fail because `all` does not yet include the sensitivity stage.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_sensitivity.py tests/test_cli.py -q
```

Expected: `erhni.sensitivity` missing.

### Step 3: Implement the sensitivity engine

Reuse the metric kernel; do not fork formulas. Store dimensions in long form:

```text
scenario,year,iso3,achievement_basis,penalty_weight_mode,penalty_weight,neutral_point,allocation_key,sample,timing,nhly,penalty,erhni,rank
```

Attach `normative_status`, `unit_status`, `uncertainty_status`, and `headline_eligible` fields so penalty-only gross weighting, formula-only legacy branches, and the rounding envelope cannot be mistaken for the primary result. Task 8's two legacy formulas deliberately use the current official aligned AQLI values and timing; they test formula magnitude only. They may not read any archive path. The public summary contains aggregate scenario/year statistics only; country rows and rank comparisons stay restricted.

Extend `build_all` and the CLI so `erhni all` now regenerates primary plus sensitivity outputs in one graph. Make the Step 1 CLI integration test pass without weakening its deletion/recreation assertions.

### Step 4: Generate and verify

```bash
uv run pytest tests/test_sensitivity.py tests/test_cli.py -q
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
uv run pytest tests/test_sensitivity.py tests/test_cli.py -q
```

Expected: tests pass; sensitivity and rank files are nonempty and manifest hashes update deterministically.

### Step 5: Commit

```bash
git add src/erhni/sensitivity.py src/erhni/pipeline.py src/erhni/cli.py tests/test_sensitivity.py tests/test_cli.py outputs/public/sensitivity_summary.csv outputs/manifest.json
git commit -m "feat: generate ERHNI decision sensitivities"
```

---

## Task 9: Old-versus-new reconciliation

**Files:**

- Update: `archive/legacy-2022/README.md` with formula findings; do not move any files in this task
- Create: `src/erhni/reconcile.py`
- Create: `tests/test_reconcile.py`
- Update: `src/erhni/pipeline.py`
- Update: `src/erhni/cli.py`
- Update: `tests/test_cli.py`
- Generate and commit: `outputs/public/legacy_reconciliation.csv` containing aggregate decomposition only
- Generate, restricted and ignored: `outputs/restricted/legacy_rank_comparison.csv`
- Update: `outputs/manifest.json`

### Step 1: Write failing forensic and reconciliation tests

Tests must assert:

- archived notebooks and CSVs keep their pre-move SHA-256 values;
- active package code imports nothing from `archive/legacy-2022`;
- stored legacy rows satisfy the forensic identity actually encoded in the CSVs, `NHLY - ERHNI = PCEC * extcostratio`, while `PCEC = 7.65 * local_aqli`; the column names and factor placement are documented rather than reinterpreted;
- formula branches evaluate exactly `0.765 * local_aqli * emissions_ratio` and `7.65 * local_aqli * emissions_ratio` and the latter is labeled `replication_only`;
- each annual and pooled primary-versus-legacy aggregate difference is assigned to formula, happiness source/timing, life expectancy/population timing, GHG source/boundary, AQLI release/benchmark, country mapping, sample, or separately labeled endpoint-reproduction residual;
- all 128 hybrid block states have a defined, nonempty eligible population; decomposition components sum to the scalar endpoint difference within configured tolerance;
- country-level old/new comparisons are calculated only on the common ISO3-year intersection and are descriptive, never presented as Shapley contributions;
- no primary result reads the unprovenanced legacy AQLI file.

Add the CLI deletion/recreation test before implementation: delete both reconciliation files, invoke `erhni all`, and require their exact recreated hashes. Add a separate forensic-adapter test that requires the literal root `archive/legacy-2022/original`, verifies every consumed legacy byte against `archive/legacy-2022/sha256.txt`, rejects any unlisted or changed file, and proves the adapter cannot be passed to the primary model.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_reconcile.py tests/test_cli.py -q
```

Expected: archive/reconciliation code missing.

### Step 3: Implement the pinned Shapley decomposition

The legacy bytes were already preserved in Task 1. Implement a read-only `LegacyAdapter` inside `reconcile.py`, with the literal default root `archive/legacy-2022/original` and manifest `archive/legacy-2022/sha256.txt`. Only this adapter may read the archived unprovenanced AQLI and mixed source/report-year files. It verifies every consumed byte before parsing and labels all resulting scenarios `forensic_legacy`; the primary pipeline accepts no adapter/archive argument. `erhni all` passes the adapter only to the reconciliation stage through its pinned internal default, while a changed/missing legacy byte fails reconciliation rather than switching inputs.

The reconciliation module evaluates the seven configured blocks—formula, happiness source/timing, life expectancy/population timing, GHG source/boundary, AQLI release/benchmark, country mapping, and sample—over every subset. This is where the documented old mixed-source/report-year construction is introduced; Task 8 remains current-source formula-only.

Pin the Shapley estimand before implementation. For year `y` and hybrid block set `S`, let `E_y(S)` be the nonempty set of rows eligible under that hybrid's mapping, source completeness, and sample rule. Missing hybrid rows are excluded explicitly and recorded; the population denominator is recalculated over exactly `E_y(S)` rather than carrying a row across methods:

```text
v_y(S) = sum[i in E_y(S)] population_i(S) * ERHNI_i(S)
         / sum[i in E_y(S)] population_i(S)
```

The pooled estimand applies the same formula over all eligible country-years in 2016-2018. The sample block switches the complete legacy eligibility rule versus the current balanced-complete-case rule; the mapping block switches the complete legacy mapping versus the reviewed current crosswalk. Every one of the 128 states must have positive total population, a recorded eligible count, and deterministic missing-row reasons. The legacy endpoint is `v(∅)` and the current endpoint is `v(all seven blocks)`.

Report exact Shapley-average contributions only for these annual and pooled scalar estimands. Contributions must sum to `v(new)-v(legacy)` with `rtol=1e-10` and `atol=1e-9`; do not produce row-level Shapley values. Separately compare the adapter's legacy endpoint with the archived published aggregate and label any mismatch `endpoint_reproduction_residual`; a residual above tolerance blocks locking. Do not substitute a sequential or reverse-only decomposition.

Keep retired WDI archive and successor families distinct. Read the three retired indicators only from the hash-pinned committed `data/snapshots/wdi_archive/*.zip` family. The locally committed legacy CO2 CSV has hash `eb100c261759d4e8ba64106a2f553e1b9695fe62f396a225b1624b24cc742ea0` and remains a forensic endpoint check, not a substitute for an official DS57 series. Never splice archive observations into current WDI observations.

Extend `build_all`/`erhni all` to recreate both reconciliation files and make the Step 1 CLI integration test pass.

### Step 4: Generate and verify reconciliation

```bash
uv run pytest tests/test_reconcile.py tests/test_cli.py -q
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
uv run pytest tests/test_reconcile.py tests/test_cli.py -q
```

Expected: all 128 states per estimand are defined; Shapley contributions close exactly; any endpoint-reproduction residual is explicit and blocks output lock above tolerance.

### Step 5: Commit

```bash
git add archive/legacy-2022/README.md src/erhni/reconcile.py src/erhni/pipeline.py src/erhni/cli.py tests/test_reconcile.py tests/test_cli.py outputs/public/legacy_reconciliation.csv outputs/manifest.json
git commit -m "feat: reconcile legacy and primary ERHNI results"
```

---

## Task 10: EDGAR v8.1 pollutant-specific allocation sensitivities

**Files:**

- Update: `config/sources.toml`
- Create: `src/erhni/edgar.py`
- Create: `tests/test_edgar.py`
- Update: `src/erhni/sensitivity.py`
- Update: `src/erhni/pipeline.py`
- Update: `src/erhni/cli.py`
- Update: `tests/test_sensitivity.py`
- Update: `tests/test_cli.py`
- Create and commit: `data/snapshots/edgar/*.zip`
- Generate and commit: `data/derived/public/edgar_air_pollutants.csv`
- Update, restricted and ignored: `outputs/restricted/sensitivities.csv`
- Update and commit: `outputs/public/sensitivity_summary.csv`
- Generate and commit: `outputs/public/edgar_coverage.csv`
- Update and commit: `data/derived/source_manifest.json`
- Update: `outputs/manifest.json`

### Step 1: Pin the official release and write failing tests

Use European Commission JRC dataset **EDGAR v8.1 Global Air Pollutant Emissions**, DOI `10.2905/JRC.E1ZGQER`, PID `http://data.europa.eu/89h/a3af16e4-21ac-420a-b98c-b78a9b7723be`, no-login access, and the EC reuse notice at `https://commission.europa.eu/legal-notice_en#copyright-notice` as accessed `2026-07-17`. The dataset-specific page obliges attribution and notes that third-party rights remain excluded from the general reuse authorization. Pin these four official ZIPs and SHA-256 hashes:

```text
PM2.5  https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/EDGAR_PM25_1970_2022.zip     4af5b9c3fcac47d0b507f5b2d8cc55eb4bb851e31fb814ed45b8a50adda6c5a3
SO2    https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/EDGAR_SO2_1970_2022_v2.zip   73e3c7d72dfef5f30b8c63015979b896e08352ebe42509fb3dd9cadc5396aafb
NOx    https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/EDGAR_NOx_1970_2022.zip      a1c99caeb3d7323df1b78b106226b8b5814146da85cc31ec9c996369103b9864
NH3    https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/EDGAR_NH3_1970_2022.zip      b908a8425bbf8c2fdb9f7b4d600a301315e152fa60f6111e6c2e9fcc599409e8
```

Expected workbook members and member hashes are:

```text
EDGAR_PM2.5_1970_2022.xlsx  5ceac898d9a9ede42502617476134aa5d7d01a57cef2a4b35dbd254169ea931d
EDGAR_SO2_1970_2022.xlsx    01b55552f8f503f3cd4f87b18d4adeb0e1fc6fd0036ae35eb04ab3d426dbe5d0
EDGAR_NOx_1970_2022.xlsx    dfff7f1c3e1c191ebd017495a785df6e253855971ac0016813fd124e3c98e337
EDGAR_NH3_1970_2022.xlsx    6bd89ce46f750044018426eb53ffeb15e699d99b377595f403dcb3c0d074f2b5
_readme.html                c3ef899b7fd8af55cb6a03a61a076301572c0bd24b24a3918eed1ca9cec1089f
```

A missing hash, changed archive, or unexpected member/schema is a hard failure. Record ZIP/member hashes, workbook dimensions, sheet/header selection, units, sentinels, PID/DOI, and reuse-policy URL in `data/derived/source_manifest.json`.

Tests must prove:

- only sheet `TOTALS BY COUNTRY`, whose metadata occupies rows 1-8 and header is row 10, is read; columns `Country_code_A3`, `Name`, `Substance`, `Y_2016`, `Y_2017`, and `Y_2018` are selected;
- each ordinary ISO A3 row is used once; detailed `IPCC 2006` and `IPCC 1996` sheets are never summed into the already-collapsed totals, and pseudo-countries `AIR` and `SEA` are excluded from country rankings while retained in denominator diagnostics;
- units remain `kt substance/year` for each pollutant;
- PM2.5, SO2, NOx, and NH3 remain four separate allocation keys;
- no raw-mass sum or invented combined score exists;
- each pollutant uses its own world/country-total denominator and emits coverage diagnostics;
- incomplete years are reported rather than imputed;
- exact locked sentinel country-year values match the source workbooks: USA PM2.5 `(1420.8672211655, 1386.102695179, 1488.7320031727)`, USA SO2 `(3900.4116011665001, 3734.590315077, 3924.6779467278998)`, USA NOx `(9274.1479831273, 9056.5318771121, 9476.3335637128)`, USA NH3 `(4227.305504305, 4240.6679486136, 4250.7111713104)`, and CHN PM2.5 `(11818.726550237, 11383.51444905, 10515.280658711)` for 2016-2018.

Add the CLI deletion/recreation test before implementation: delete the EDGAR normalized file, coverage output, and affected sensitivity files, invoke `erhni all`, and require their exact recreated hashes. It must fail because `all` does not yet include EDGAR normalization/sensitivities.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_edgar.py tests/test_sensitivity.py tests/test_cli.py -q
```

Expected: EDGAR parser/source locks missing.

### Step 3: Implement parsing and four independent sensitivities

Read workbook members directly from verified ZIPs. Metadata cell `B5` must equal `Gg`, numerically identical to kt, and the substance label must match the configured pollutant. Normalize JRC country codes through explicit crosswalk decisions. Produce one row per pollutant/year/ISO3 and a coverage table with raw rows, mapped rows, missing countries, ordinary-country total, `AIR`, `SEA`, denominator choice, sample share, and excluded aggregates. The denominator is the published total across all `TOTALS BY COUNTRY` rows for that pollutant/year, with ordinary-country, international-aviation, and international-shipping shares reported separately; ranked country shares are not renormalized.

Reuse the allocation ledger logic with a pollutant-specific denominator; retain the PM-burden sizing and normative-proxy caveat. Never call these source-receptor results. Expose `erhni edgar-normalize --sources ... --snapshot-dir data/snapshots/edgar --derived-dir data/derived/public`, then extend `build_all` so `erhni all` invokes it before generating all sensitivity outputs. Make the Step 1 CLI deletion/recreation test pass.

### Step 4: Acquire, generate, and verify

```bash
uv run python -m erhni.sources acquire --config config/sources.toml --raw-dir data/raw/external
uv run pytest tests/test_edgar.py tests/test_sensitivity.py tests/test_cli.py -q
uv run erhni edgar-normalize --sources config/sources.toml --snapshot-dir data/snapshots/edgar --derived-dir data/derived/public
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
```

Expected: all four pollutant scenarios are present separately; coverage is machine-readable; manifest hashes update.

### Step 5: Commit

```bash
git add config/sources.toml src/erhni/edgar.py src/erhni/sensitivity.py src/erhni/pipeline.py src/erhni/cli.py tests/test_edgar.py tests/test_sensitivity.py tests/test_cli.py data/snapshots/edgar data/derived/public/edgar_air_pollutants.csv data/derived/source_manifest.json outputs/public/sensitivity_summary.csv outputs/public/edgar_coverage.csv outputs/manifest.json
git commit -m "feat: add pollutant-specific EDGAR sensitivities"
```

---

## Task 11: Publication figures and generated manuscript tables

**Files:**

- Create: `src/erhni/figures.py`
- Create: `src/erhni/tables.py`
- Create: `tests/test_figures.py`
- Create: `tests/test_tables.py`
- Update: `src/erhni/pipeline.py`
- Update: `src/erhni/cli.py`
- Update: `tests/test_cli.py`
- Generate and commit: `outputs/public/figures/sample_flow.{svg,png,txt}`
- Generate and commit: `outputs/public/figures/net_vs_gross_aggregate.{svg,png,txt}`
- Generate and commit: `outputs/public/figures/legacy_reconciliation_aggregate.{svg,png,txt}`
- Generate and commit: `outputs/public/tables/global_summary.csv`
- Generate and commit: `outputs/public/tables/sample_flow.csv`
- Generate, review-only and ignored: `outputs/review/figures/primary_country_comparison.{svg,png,txt}`
- Generate, review-only and ignored: `outputs/review/figures/country_rank_changes.{svg,png,txt}`
- Generate, review-only and ignored: `outputs/review/figures/sensitivity_rank_correlation.{svg,png,txt}`
- Generate, review-only and ignored: `outputs/review/tables/country_results.csv`
- Generate, review-only and ignored: `outputs/review/tables/sensitivity_results.csv`
- Generate and commit: `outputs/public/table_manifest.json`
- Generate and commit: `outputs/public/figure_manifest.json`
- Update: `outputs/manifest.json`

### Step 1: Write failing figure/table tests

Require at least:

- primary 2016-2018 country-level ERHNI/NHLY comparison, classified `review_only`;
- aggregate penalty magnitude under net versus gross valuation, classified `public_aggregate`;
- country-rank changes from NHLY to primary ERHNI, classified `review_only`;
- aggregate primary-versus-legacy reconciliation, classified `public_aggregate`;
- sensitivity rank-correlation matrix, classified `review_only`;
- aggregate sample-flow/coverage figure, classified `public_aggregate`.

Tests must assert nonempty SVG/PNG files, fixed dimensions/DPI, embedded or explicitly configured fonts, readable labels, alt-text sidecar entries, no title embedded twice, and plotted values matching source CSVs. Table tests must compare every generated numeric cell with its source output at declared rounding precision and prohibit hand-entered totals.

Add the CLI deletion/recreation test before implementation: remove every figure, table, and figure/table manifest, invoke `erhni all`, and require the exact recreated file set and hashes. It must fail because `all` does not yet include publication-artifact generation.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_figures.py tests/test_tables.py tests/test_cli.py -q
```

Expected: figure/table modules missing.

### Step 3: Implement deterministic visual and tabular generation

Set Matplotlib backend, theme, font, figure size, DPI, SVG hash salt, and metadata explicitly. Strip creation timestamps from image metadata. Use colorblind-safe colors and direct labels where feasible. Each figure gets a `.txt` alt-text file that states the takeaway without claiming unsupported causality.

Generate compact manuscript tables from classified pipeline outputs; include source filename/hash, disclosure class, destination, and rounding rule in the table manifest. Country-level figures and tables are written only beneath `outputs/review/`, which is ignored and prohibited by the public-release allow-list. Aggregate files beneath `outputs/public/` must pass disclosure validation before writing.

Extend `build_all`/`erhni all` to recreate both public and review-only figures and tables after the analysis, sensitivity, reconciliation, and EDGAR stages. Make the Step 1 CLI integration test pass. This closes the §8.1 contract that the canonical command regenerates every number, table, and figure used by the manuscript in an authorized environment.

### Step 4: Generate and inspect

```bash
uv run pytest tests/test_figures.py tests/test_tables.py tests/test_cli.py -q
uv run erhni figures --input-dir outputs --public-dir outputs/public/figures --review-dir outputs/review/figures
uv run erhni tables --input-dir outputs --public-dir outputs/public/tables --review-dir outputs/review/tables
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
uv run pytest tests/test_figures.py tests/test_tables.py -q
```

Expected: all figures/tables are generated deterministically and tests pass. Open every PNG at full size and correct clipping, overlap, unreadable annotations, and color/legend ambiguity before commit. Record visual inspection in the figure manifest; do not stage review-only artifacts.

### Step 5: Commit

```bash
git add src/erhni/figures.py src/erhni/tables.py src/erhni/pipeline.py src/erhni/cli.py tests/test_figures.py tests/test_tables.py tests/test_cli.py outputs/public/figures outputs/public/tables outputs/public/table_manifest.json outputs/public/figure_manifest.json outputs/manifest.json
git commit -m "feat: generate classified ERHNI publication artifacts"
```

---

## Task 12: Documentation, public-release boundary, and clean-clone verification

**Files:**

- Create: `README.md` replacing the legacy README content
- Create: `DATA_SOURCES.md`
- Create: `DATA_DICTIONARY.md`
- Create: `REPRODUCIBILITY.md`
- Create: `CHANGELOG.md`
- Create: `LICENSING.md`
- Create: `src/erhni/release.py`
- Create: `tests/test_release.py`
- Create: `scripts/stage-public-release`
- Generate and commit: `release/public-manifest.json`
- Update: `config/disclosure.toml`
- Update: `tests/test_disclosure.py`
- Update: `pyproject.toml`
- Update: `.gitignore`

### Step 1: Write failing public-boundary tests

Tests must require a fail-closed, explicit allow-list and prove:

- `data/raw/external/**`, `data/derived/restricted/**`, `outputs/restricted/**`, `outputs/review/**`, and all legacy row-level WHR/AQLI derivatives are absent from the staged public bundle;
- no file classified `restricted_source`, `restricted_derived`, or `review_only` can be copied even when it is passed explicitly or symlinked from an allowed directory;
- committed WDI and EDGAR snapshots, source/config locks, code, tests, aggregate public artifacts, documentation, and manifests are included;
- every staged file except `release/public-manifest.json` has a hash and release role in that manifest, with no unclassified files; staged data/artifacts also retain their disclosure class, and the manifest is explicitly excluded from its own inventory;
- source and derived manifests contain no local absolute path, access token, cookie, credential, or raw restricted value;
- `erhni verify-public-bundle` succeeds without network access in a clean copy of the staged bundle and revalidates permitted snapshot hashes, schemas, configs, aggregate-output hashes, and manifest closure;
- a full scientific rebuild is deliberately reported as `authorized_inputs_required` when the WHR/AQLI files are absent, not misreported as successful or irreproducible.

### Step 2: Run the tests and verify RED

```bash
uv run pytest tests/test_release.py -q
```

Expected: public staging and verification commands do not exist.

### Step 3: Implement the allow-listed release and documentation

Implement `scripts/stage-public-release DEST` as a thin entry point over `erhni release stage`. Resolve real paths, reject symlinks that escape an allowed root, validate each release role and any applicable disclosure class before copying, and build into a new empty destination. Never implement a deny-list fallback. `erhni verify-public-bundle BUNDLE --offline` must validate the bundle without importing any ignored local artifact.

Documentation must explain:

- exact authorized canonical build, `uv run erhni all --config config/method.toml --output-dir outputs`, and public-bundle offline verification;
- why WHR/AQLI raw and row-level derived files are acquired locally but not redistributed pending written rights confirmation;
- which aggregate outputs are public by default and which country-level artifacts remain review-only;
- current WDI successor versus archived forensic families and their gas/boundary/unit distinctions;
- annual source alignment and the pinned 2016-2018 window;
- all denominator universes, allocation conservation, and the signed WLD reconciliation residual;
- why the small net-surplus weight is primary and gross valuation is a labeled normative sensitivity;
- how to audit exclusions, crosswalks, coverage, EDGAR pseudo-countries, and the legacy reconciliation;
- that AQLI's `±0.05` envelope is a rounding-resolution sensitivity, not a confidence interval;
- the two-tier reproducibility contract: fully deterministic rebuild with authorized restricted inputs, and fully offline audit of the redistributable public bundle.

Do not choose an open-source license or assert third-party rights on the author's behalf. `LICENSING.md` records upstream reuse terms and marks the project-code license and WHR/AQLI redistribution permissions as author/legal gates.

### Step 4: Verify a genuinely clean staged bundle

```bash
uv run pytest tests/test_release.py -q
rm -rf /tmp/erhni-public-release /tmp/erhni-public-check
uv run scripts/stage-public-release /tmp/erhni-public-release
git -C /tmp/erhni-public-release init -q
git -C /tmp/erhni-public-release -c user.name=ERHNI -c user.email=reproducibility@example.invalid add -A
git -C /tmp/erhni-public-release -c user.name=ERHNI -c user.email=reproducibility@example.invalid commit -q -m "test public bundle"
git clone --no-local /tmp/erhni-public-release /tmp/erhni-public-check
cd /tmp/erhni-public-check
uv sync --frozen
uv run erhni verify-public-bundle . --offline
uv run pytest tests/test_release.py -q
```

The production staging command must not initialize Git or mutate the source repository. The test-only commands above create one local commit after staging so `git clone` exercises a real clean checkout. Expected: offline verification passes, and attempting the full build without authorized WHR/AQLI inputs exits with the documented `authorized_inputs_required` status.

### Step 5: Commit

```bash
git add README.md DATA_SOURCES.md DATA_DICTIONARY.md REPRODUCIBILITY.md CHANGELOG.md LICENSING.md src/erhni/release.py tests/test_release.py tests/test_disclosure.py scripts/stage-public-release release/public-manifest.json config/disclosure.toml pyproject.toml .gitignore
git commit -m "docs: define and verify the public reproducibility bundle"
```

---

## Task 13: Output lock, whole-pipeline regression tests, and evidence bundle

**Files:**

- Create: `tests/test_locked_outputs.py`
- Create and commit: `outputs/public/LOCK.json`
- Create, restricted and ignored: `outputs/restricted/LOCK-private.json`
- Create: `outputs/README.md`
- Create: `docs/reproducibility-audit.md`
- Update: `outputs/manifest.json`
- Update: `release/public-manifest.json`

### Step 1: Write failing locked-output tests

After reviewing the generated results, add exact public regression assertions for:

- balanced sample count, but not the row-level ISO3 set;
- annual `Hbar`, net `w`, gross `w`, AQLI burden, WLD total, signed WLD residual, and allocated burden;
- unweighted and population-weighted primary aggregates;
- aggregate primary-versus-legacy penalty factors, described as aggregate rather than universal country ratios;
- public output file hashes and figure/table manifest hashes;
- hashes of every restricted/review-only artifact without copying its contents into a committed fixture.

The ignored private lock contains the exact balanced ISO3 set, top/bottom rankings, deterministic tie order, country-level sentinels, and hashes. Do not invent expected numbers: copy them from reviewed generated files, then independently recompute global formulas from the local country/burden/allocation ledgers. Committed test source must contain only public aggregate sentinels and hashes; it loads `LOCK-private.json` for authorized full-pipeline checks and explicitly skips only those private assertions when restricted inputs are unavailable. A clean public-bundle test must never silently skip aggregate or manifest assertions.

### Step 2: Run the lock tests and verify RED

```bash
uv run pytest tests/test_locked_outputs.py -q
```

Expected: missing public/private lock files or intentionally mismatched regression fixtures; do not weaken assertions to make them pass.

### Step 3: Create the reviewed lock and audit record

The lock graph is an explicit DAG and each writer must test its exclusions:

```text
analysis artifacts
  -> outputs/manifest.json
     (hashes analysis artifacts; excludes itself and both LOCK files)
  -> outputs/public/LOCK.json
     (hashes outputs/manifest.json and LOCK-private.json; excludes itself and release/public-manifest.json)
  -> release/public-manifest.json
     (hashes every staged file including the public LOCK; excludes itself)
```

Create the private lock first, then `outputs/manifest.json`, then the public lock, then the release manifest. A manifest-to-lock or lock-to-release-manifest hash edge is a hard error.

`outputs/public/LOCK.json` must contain:

- analysis commit under test, defined as the Task 12 commit immediately preceding the lock commit so the identifier is not self-referential;
- approved spec/config hashes;
- permitted source and public-output hashes, excluding both lock files from their own hash inventory and including the non-self-referential `manifest.json` hash;
- aggregate generated scientific sentinels and hashes of private artifacts, but no country-level rows or rankings;
- rights status for each source;
- unresolved external gates (`whr_gallup_rights`, `aqli_rights`, `project_code_license`, `ng_method_signoff`, author metadata/approval, venue metadata, and Zenodo DOI);
- lock status `analysis_locked` rather than `submission_ready` while any external gate is open.

`outputs/restricted/LOCK-private.json` contains the row-level sentinels needed for authorized regression testing and is validated against its public hash. `docs/reproducibility-audit.md` records every command, environment version, deterministic diff result, test count, coverage summary, clean-bundle result, and any scientifically material deviation from the approved design.

Before writing either lock, assert that `src/`, `config/`, `data/snapshots/`, `uv.lock`, and `pyproject.toml` exactly match the Task 12 analysis commit named by the lock. Task 13 may add tests, documentation, and lock/manifests, but it may not change analysis code, configuration, snapshots, or dependencies under that identifier.

### Step 4: Run the full clean verification twice

```bash
uv sync --frozen
uv run ruff check .
uv run pytest -q --cov=erhni --cov-report=term-missing
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
rm -rf /tmp/erhni-lock-first
cp -R outputs /tmp/erhni-lock-first
uv run erhni all --offline --config config/method.toml --sources config/sources.toml --disclosure config/disclosure.toml --raw-dir data/raw/external --output-dir outputs
diff -ru /tmp/erhni-lock-first outputs
uv run pytest tests/test_locked_outputs.py -q
rm -rf /tmp/erhni-public-release /tmp/erhni-public-check
uv run scripts/stage-public-release /tmp/erhni-public-release
git -C /tmp/erhni-public-release init -q
git -C /tmp/erhni-public-release -c user.name=ERHNI -c user.email=reproducibility@example.invalid add -A
git -C /tmp/erhni-public-release -c user.name=ERHNI -c user.email=reproducibility@example.invalid commit -q -m "test public bundle"
git clone --no-local /tmp/erhni-public-release /tmp/erhni-public-check
cd /tmp/erhni-public-check
uv sync --frozen
uv run erhni verify-public-bundle . --offline
uv run pytest tests/test_release.py tests/test_locked_outputs.py -q
```

Expected: dependency lock honored; lint/tests pass; the second authorized build is byte-identical; private and public locked-output tests pass; the staged public bundle independently verifies offline. Then run the repository evidence command if present and save its manifest. Apply the verification-before-completion checklist and obtain a fresh whole-branch code/scientific review. Do not claim submission readiness while external gates in the public lock remain open.

### Step 5: Commit

```bash
git add tests/test_locked_outputs.py outputs/public/LOCK.json outputs/README.md outputs/manifest.json release/public-manifest.json docs/reproducibility-audit.md
git commit -m "test: lock reproducible ERHNI analysis outputs"
```

### Step 6: Hand off to the manuscript plan

Read `outputs/public/LOCK.json`, the public aggregate tables, and—only in the authorized local environment—the review-only country/sensitivity tables and private lock. Write a separate plan that builds the manuscript and submission files only from locked artifacts, uses the Documents/PDF render-and-inspection workflow, and keeps unresolved author, venue, rights, code-license, sign-off, and DOI fields visibly blocked rather than guessed. The manuscript plan must preserve the same disclosure boundary: submission-review files may use authorized review-only derivatives, while the default public bundle remains aggregate-only until written rights permission is recorded.
