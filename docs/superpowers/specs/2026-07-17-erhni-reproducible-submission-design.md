# ERHNI 2016-2018 Reproducible Submission Design

**Status:** Approved; source and denominator pin-downs resolved on 17 July 2026

**Working title:** *Clearing the Air on the Environmentally Responsible Happy Nation Index: A Reproducible Update of ERHNI, 2016-2018*

## 1. Goal

Prepare the first submission of the 2016-2018 ERHNI results as a reproducible methodological update. The work must replace the stateful notebook and manually assembled outputs with a deterministic pipeline, regenerate every reported number, and revise the manuscript only after the results are locked.

The submission will target the current regular-article requirements of MDPI *Sustainability*. The closed 2021 Special Issue is not the submission target.

## 2. Scope

The build will deliver:

1. a deterministic Python analysis package and command-line interface;
2. source manifests, checksums, country mappings, exclusions, and licenses;
3. a generated balanced analysis panel whose country count is an output;
4. primary, legacy, and alternative-allocation specifications;
5. generated country, global, regional, ranking, sensitivity, and reconciliation tables;
6. publication-quality figures generated from the locked outputs;
7. a clean v3 manuscript, a v2-to-v3 comparison copy, supplementary files, cover letter, and submission checklist;
8. a tagged GitHub release prepared for Zenodo archival and a DOI-backed data-availability statement once the archive is minted.

The work will not claim causal source attribution. A pollutant source-receptor model and a separate future-climate-damage ledger are beyond the present paper's scope.

## 3. Scientific Definitions

### 3.1 Net happy life years

For country `i` and calendar year `t`:

```text
NHLY_it = ((H_it - 5) / 10) * LE_it
```

where:

- `H_it` is the published national annual-average Cantril-ladder score;
- `LE_it` is life expectancy in the same calendar year;
- the neutral point of 5 and the cardinal transformation are normative assumptions and will be sensitivity-tested.

The unit is net-happiness-weighted years per resident.

### 3.2 Reproducible annual observations and access status

The pre-lock source check recovered the official *World Happiness Report 2022* supplemental workbook **Data for Table 2.1**, which the report site publicly linked in 2022. The workbook contains country-year national averages, including `Life Ladder`, rather than the three-year ranking averages in Figure 2.1. The public build will use its 2016, 2017, and 2018 rows and align every other input to the same calendar year.

The original publisher URL is no longer directly downloadable, so acquisition is pinned to the Internet Archive capture of the historical official release:

```text
original_url = https://happiness-report.s3.amazonaws.com/2022/DataForTable2.1.xls
archive_url = https://web.archive.org/web/20220715181822id_/https://happiness-report.s3.amazonaws.com/2022/DataForTable2.1.xls
provenance_page = https://web.archive.org/web/20220715181822id_/https://worldhappiness.report/ed/2022/
archive_capture = 2022-07-15T18:18:22Z
sha256 = f118e7f606f091b978edc674242b491b79ee37bea6cb2b5243f805f5f39ccfa4
```

The archived 2022 report page identifies the file as “Data for Table 2.1,” establishing historical public availability and provenance, not a license. The current WHR data-sharing page routes annual Gallup World Poll data to request or subscription and does not grant an explicit redistribution or public-use license for this historical workbook. The repository will therefore provide deterministic acquisition and checksum verification but will not redistribute the raw workbook. Submission requires written rights/access confirmation from WHR or Gallup, or a documented applicable license; otherwise the annual-panel analysis remains a reproducible research draft rather than a submission-ready package.

The source choice is explicit and fail-closed: the pipeline must not silently replace this annual panel with Figure 2.1 three-year averages, a Kaggle mirror, or subscription data. If the pinned file cannot be acquired, the build stops before analysis.

For each year 2016-2018:

- life expectancy, country population, and territorial GHG are the same-year World Bank values;
- AQLI burden uses the same year's directly published historical `whoYYYY` field and the same-year World Bank population for every eligible AQLI entity;
- no annual happiness, demographic, environmental, or pollution value is imputed;
- the headline sample is the complete-case country panel balanced across all three years.

The manuscript may describe balanced-panel changes from 2016 to 2018, but it must distinguish description from inference and must not make causal-policy or survey-microdata claims.

### 3.3 Primary current-generation responsibility allocation and fixed universes

Let:

```text
B_t = sum_j(N^WDI_jt * A_jt), j in the full WDI-populated AQLI universe J_t
s_it = G_it / G_WLD,t
Hbar_t = sum_i(N_it * H_it) / sum_i(N_it), i in the balanced analysis panel
w_t = (Hbar_t - 5) / 10
L_it = w_t * s_it * B_t
P_it = L_it / N_it
ERHNI_it = NHLY_it - P_it
```

where:

- `J_t` contains every unique AQLI release entity with a valid canonical identifier, finite nonnegative WHO-benchmark value `A_jt`, and finite positive same-year World Bank population `N^WDI_jt`; every other AQLI row is retained in an exclusion and coverage ledger;
- `B_t` is the resulting same-year ambient-PM life-expectancy burden in raw person-years over `J_t`; it is never recomputed on the ranked ERHNI sample;
- `A_jt` is AQLI life expectancy lost per resident under the fixed WHO benchmark;
- `G_WLD,t` is the official `WLD` observation for the selected World Bank GHG series, not a sum over the ranked or matched country sample;
- `s_it` is country `i`'s share of that world aggregate;
- `Hbar_t` is the population-weighted life evaluation across the balanced, ranked analysis panel;
- `w_t` converts raw lost life-years into the net-happiness-weighted unit used by NHLY;
- `L_it` is the country allocation in total net-happiness-weighted person-years and does not require a population observation;
- `P_it` is the normative current-generation environmental-responsibility penalty per resident.

These universe choices are named values in `config/method.toml`: `burden_universe = "aqli_full_wdi_population"`, `allocation_denominator = "wdi_wld"`, `happiness_weight_universe = "balanced_analysis_panel"`, and `ranking_universe = "balanced_complete_case"`. They are validated by tests and written to every result manifest.

The pipeline must fail with a clear diagnostic if `w_t <= 0`; it must not clamp or silently replace the value.

The official `WLD` observation may differ from the sum of ordinary country/economy observations. The pipeline therefore emits an allocation ledger for every row that official World Bank metadata classifies as non-aggregate and that has a finite nonnegative GHG observation, plus a signed `wld_reconciliation_residual` row. Per-capita penalties separately require a finite positive population, and missing population does not remove the country's total allocation from the ledger. Conservation is tested as:

```text
r_t = 1 - sum_c(s_ct)
R_t = r_t * w_t * B_t
sum_c(L_ct) + R_t = w_t * B_t
```

where `c` spans the defined non-aggregate GHG source rows, not only ranked countries. The ranked-sample share, out-of-sample country share, rows lacking population, and signed `WLD` reconciliation residual are reported separately. No sample-dependent renormalization to one is permitted. The primary configuration sets `max_abs_wld_reconciliation_share = 0.05`; the build records the observed sign and magnitude and fails if `abs(r_t)` exceeds that bound.

The headline weight remains `w_t = (Hbar_t - 5) / 10`. Its expected small magnitude, and the corresponding result that primary ERHNI remains close to NHLY, are substantive consequences of the net-happiness unit and removed legacy multipliers; they are not reasons to inflate the primary coefficient. A prominent penalty-valuation sensitivity uses the gross-happiness weight `Hbar_t / 10`, which is equivalent to a zero neutral point for the penalty while headline NHLY retains a neutral point of 5. It is not presented as a fully unit-consistent alternative ERHNI unless NHLY is also recomputed on the gross scale. Fixed weights are reported as explicitly normative alternatives. The manuscript must not describe any of these weights as empirically calibrated.

The primary model deliberately drops the inherited `beta`, `gamma`, `theta`, and `xi` chain. It therefore measures a current-generation, PM-mortality-sized burden only. It does not estimate morbidity, harm to future generations, climate damages, or the portion of pollution imposed specifically on people outside the emitting country.

The manuscript will call `P_it` a normative environmental-responsibility allocation or responsibility penalty. It will not describe it as causal attribution or literal per-capita external cost without the accompanying proxy qualification.

### 3.4 Allocation-key limitation

The primary model sizes the global burden using ambient-PM life-expectancy loss but allocates it using territorial GHG shares. This is a normative polluter-pays proxy, not evidence that the selected GHG inventory caused the contemporaneous PM burden.

The paper must state this structural mismatch when introducing the equation, in the limitations section, and when interpreting rankings.

### 3.5 Cross-edition comparability

Primary v3 levels are not directly comparable with the 2008 or previously calculated 2016 ERHNI levels because the environmental component, unit conversion, coverage, and timing differ. The headline manuscript will not make level or trend claims across method editions.

Cross-edition comparison will appear only in the legacy reconciliation and sensitivity material, with formula, sample, source, and timing effects separated.

## 4. Source Policy

### 4.1 Primary sources

The pipeline will cite and acquire data from primary or official publishers:

- World Happiness Report official reports, appendices, and data releases;
- World Bank World Development Indicators for life expectancy, population, and GHG totals;
- the official AQLI release for PM2.5 exposure and life-expectancy loss;
- European Commission JRC EDGAR for the air-pollutant allocation sensitivity.

Kaggle mirrors may be retained only as legacy evidence. They will not be cited as the scientific source.

### 4.2 GHG primary, archived legacy, and sensitivity series

The primary GHG allocator is the active World Bank WDI/EDGAR AR5 indicator `EN.GHG.ALL.MT.CE.AR5`: territorial Kyoto-gas emissions excluding LULUCF, in Mt CO2 equivalent. Its system boundary, AR5 basis, unit, source ID, observation years, raw response, metadata, and checksum are pinned. The calculation may retain Mt consistently or convert once to kt; the unit choice is recorded in the output manifest.

The retired indicators `EN.ATM.GHGT.KT.CE`, `EN.ATM.METH.KT.CE`, and `EN.ATM.NOXE.KT.CE` resolve to World Bank source 57, *WDI Database Archives*, not the active WDI source. They may be used only through an explicitly selected `archive` family with pinned official DS57 ZIPs and hashes. They are retained for legacy reproduction and reconciliation, not silently substituted into the primary run.

The current successor family is explicitly named `edgar_ar5_excl_lulucf`. It uses:

- total: `EN.GHG.ALL.MT.CE.AR5`;
- CO2: `EN.GHG.CO2.MT.CE.AR5`;
- CH4: `EN.GHG.CH4.MT.CE.AR5`;
- N2O: `EN.GHG.N2O.MT.CE.AR5`.

A required sensitivity reconstructs the current three-gas boundary as:

```text
three_gas_co2e_mt = co2_mt_co2e + ch4_mt_co2e + n2o_mt_co2e
```

All three successor component series are already in Mt CO2 equivalent under AR5. No GWP factors may be applied again. A CO2-only sensitivity will also be reported. The archived and successor families have different methods and boundaries and must never be concatenated, automatically substituted, or presented as one continuous series. An unavailable selected family is a hard error.

### 4.3 AQLI benchmark and release

The primary burden source is the official AQLI country-level (`gadm0`) CSV exposed by the 2025 AQLI site release, using its directly published historical `who2016`, `who2017`, and `who2018` fields and the WHO PM2.5 counterfactual of 5 micrograms per cubic metre. The pipeline parses those fields as finite decimal years with no transformation or intermediate rounding. Zero is a valid published value; blank or nonnumeric values are excluded with a source-specific reason, and negative values are errors. Every included row must have `whostandard = 5`. Locked-source tests verify, among other sentinels, that `CHN` has `(3.4, 3.1, 2.7)`, `IND` has `(4.2, 4.1, 4.1)`, and `ABW` has `(0, 0, 0)` for 2016-2018. The pinned source is:

```text
release = AQLI 2025 country-level data
url = https://cdn.sanity.io/files/3o8tp68r/production/4d1bc319df6657d5ced2fdfc38604e0da13cc812.csv
source_updated_at = 2025-08-19T13:13:14Z
sha256 = 65bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73
```

The source contains one release-level population field derived from LandScan, but its reference date is not identified in the CSV metadata. It is not used to size the primary annual burden. Instead, the full burden universe is constructed independently of the ERHNI ranking sample from all uniquely mapped AQLI rows with a valid `whoYYYY` value and same-year World Bank population. Missing or non-unique mappings and missing population are reported as burden-universe exclusions. The AQLI release population is retained only for source-coverage diagnostics, not represented as a same-year observation.

The source manifest must record the AQLI release, benchmark, URL, source update time, access date, schema, license or redistribution terms, and SHA-256 checksum. The current site publishes the CSV for download but does not state an explicit data license, so the repository provides deterministic acquisition and checksum verification without redistributing the raw file unless permission or an applicable license is established.

The unprovenanced `data/aqli_global_data.csv` in the legacy repository is forensic evidence only and must not enter the primary calculation.

### 4.4 EDGAR air-pollutant sensitivity

The build will include four separate secondary allocations based on country-year emissions of primary PM2.5, SO2, NOx, and NH3 from an official EDGAR country-total release. Each pollutant is used as its own allocation key. Their raw masses will not be summed or converted into an invented combined-pollutant score. These allocations will not be described as source-receptor models.

If an official series has incomplete coverage for one of the three years, the pipeline will report the available-year result and a machine-readable coverage diagnostic instead of imputing missing pollutant emissions.

## 5. Country Identity, Sample, and Aggregation

The sample size is never a configured target. It is generated by the following rules:

1. every source country name maps through a committed, reviewed crosswalk;
2. each calendar year has at most one row per canonical ISO3 code;
3. a territory is not aliased to a sovereign country's data;
4. every included row has the primary happiness, life-expectancy, population, AQLI, and GHG inputs;
5. the headline panel is balanced across 2016, 2017, and 2018;
6. every excluded or collapsed source record has a specific machine-readable reason;
7. the generated sample-flow table reports counts after each rule.

North Cyprus must not inherit Cyprus's World Bank observations, and Somaliland must not inherit Somalia's observations. Politically sensitive display labels will be separated from computational identity codes.

The paper will report both:

- unweighted means across included countries; and
- population-weighted means across included residents.

It will never label an unweighted country mean simply as the world average.

## 6. Specifications and Sensitivity Analysis

The generated sensitivity grid will include:

1. primary happiness-weighted responsibility allocation;
2. the prominent gross-happiness weight, alternative fixed lost-year weights, and the observed `w_t` range;
3. the legacy `0.765 * AQLI * emissions-ratio` formula;
4. the legacy ten-times branch as replication evidence only;
5. consolidated total GHG, corrected three-gas, and CO2-only allocation keys;
6. separate EDGAR PM2.5, SO2, NOx, and NH3 allocations;
7. aligned same-year annual inputs versus the old mixed-source/report-year construction;
8. balanced-panel versus maximal-coverage samples;
9. unweighted versus population-weighted aggregates;
10. sensitivity of NHLY to the neutral point of 5;
11. rank Spearman and Kendall correlations, top-10 overlap, and rank crossings;
12. input uncertainty or sensitivity envelopes, clearly distinguished from confidence intervals.

No rank-robustness claim may appear unless generated results support it.

## 7. Reproducibility Architecture

The repository will use a small Python package rather than a stateful notebook or workflow engine:

```text
pyproject.toml
uv.lock
README.md
LICENSE

config/
  method.toml
  sources.toml
  country_map.csv
  regions.csv

src/erhni/
  cli.py
  sources.py
  countries.py
  years.py
  metrics.py
  sample.py
  aggregate.py
  sensitivity.py
  reconcile.py
  figures.py

data/raw/
data/derived/
archive/legacy-2022/

outputs/
  country_year.csv
  exclusions.csv
  sample_flow.csv
  global_summary.csv
  regional_summary.csv
  rankings.csv
  sensitivities.csv
  legacy_reconciliation.csv
  figures/

paper/
  manuscript/
  supplement/
  submission/

tests/
```

The canonical command will be:

```bash
uv run erhni all --config config/method.toml --output-dir outputs
```

The command must regenerate every manuscript table and figure. Running it twice from the same source snapshots must produce byte-identical tabular outputs and a generated manifest containing source hashes, software versions, configuration hash, and output hashes.

The original notebooks and incompatible CSV branches will be retained under `archive/legacy-2022/` as forensic evidence and removed from the active calculation path.

## 8. Test and Evidence Contract

Tests must establish at least:

- the exact archived official WHR annual-panel URL, hash, schema, and 2016-2018 year selection;
- exact World Bank indicator codes and source hashes;
- explicit, fail-closed selection of the archived or successor GHG family with no automatic fallback or concatenation;
- no second GWP conversion of CO2-equivalent CH4 or N2O;
- exact net-happiness weight, nonpositive-weight failure, and gross-minus-net weight identity of `0.5`;
- exact NHLY and responsibility-penalty unit calculations on synthetic fixtures;
- exact `aqli_full_wdi_population`, `wdi_wld`, `balanced_analysis_panel`, and `balanced_complete_case` universe selection;
- exact `WLD`-denominator allocation with a reported residual and no sample renormalization;
- burden conservation including the signed `wld_reconciliation_residual` ledger row and the configured residual-share bound;
- unique `(year, ISO3)` rows;
- complete explicit mapping decisions;
- balanced-panel construction without a hard-coded country target;
- stable sorting and deterministic tie-breaking;
- row-wise `ERHNI = NHLY - penalty`;
- aggregate reconciliation with country rows;
- classification of every legacy difference;
- deterministic reruns and nonempty figures;
- manuscript tables matching their generated CSV sources.

All implementation changes follow test-first red-green-refactor cycles.

## 9. Manuscript Design

The v2 draft is the editorial base, but all numbers, results prose, tables, figures, decomposition percentages, and rankings are replace-only.

The v3 manuscript will:

- present this as the corrected first publication of ERHNI 2016-2018;
- describe reproducibility as the methodological backbone rather than the thesis;
- remove unsupported annual-trend, China-campaign, Global Financial Crisis, pandemic, and policy-causality claims;
- state the unit conversion, current-generation scope, allocation mismatch, annual-data provenance, and cross-edition non-comparability prominently;
- report generated sample counts and coverage rather than precommitting them;
- distinguish average-country and average-person results;
- include an old-versus-new rank reconciliation in the supplement;
- verify Chen et al. (2017), DOI `10.1007/s11205-016-1422-2`, and every other citation against primary sources;
- satisfy current *Sustainability* front matter, methods, declarations, data-availability, figure, and cover-letter requirements.

No results sentence will be finalized before the locked pipeline run.

## 10. Release and Archival Design

The final repository state will be tagged. The tag will include:

- code and tests;
- permitted source snapshots or deterministic acquisition instructions;
- source and output manifests;
- the harmonized analysis panel;
- all generated tables and figures;
- the manuscript source and submission artifacts;
- a changelog linking each manuscript result to its generating output.

The tagged GitHub release will be connected to Zenodo. The data-availability statement may cite a DOI only after Zenodo has minted it; the draft will not contain a fictitious DOI.

## 11. Submission-Readiness Gate

The paper is submission-ready only when all of the following are true:

1. one documented command regenerates every number, table, and figure byte-identically;
2. the complete test suite and evidence checks pass;
3. the abstract, results, discussion, and conclusion are written from the locked generated outputs;
4. the Chen et al. citation and all data/method references are verified;
5. the clean DOCX passes a full render-and-inspection cycle;
6. the supplement, cover letter, data-availability statement, declarations, and checklist are complete;
7. author affiliations, ORCIDs, funding, conflicts, CRediT roles, and all-author approval are supplied and confirmed;
8. Yew-Kwang Ng explicitly approves the primary method's replacement of the inherited parameter chain;
9. the tagged release exists and the Zenodo DOI, if claimed, resolves to the archived release.
10. written WHR/Gallup rights or access confirmation, or a documented applicable license, supports use of the annual Table 2.1 workbook in the submission and reproducibility package.

Co-author sign-off and author-supplied declarations are hard gates. They cannot be inferred or waived by the analysis pipeline.

## 12. Execution Order

1. Build tests and the deterministic pipeline.
2. Generate the source, mapping, exclusion, and sample-flow evidence.
3. Generate primary and sensitivity results.
4. Produce the old-versus-new reconciliation.
5. Lock outputs and review the scientific conclusions.
6. Rewrite the manuscript from the locked results.
7. Render and inspect the submission documents.
8. Prepare the release, archive, cover letter, and submission checklist.
9. Collect author metadata and Yew-Kwang Ng's method sign-off before submission.
