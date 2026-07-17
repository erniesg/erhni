# ERHNI 2016-2018 Reproducible Submission Design

**Status:** Approved with amendments on 17 July 2026

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

For country `i` and report vintage `v`:

```text
NHLY_iv = ((H_iv - 5) / 10) * LE_iv
```

where:

- `H_iv` is the published national Cantril-ladder score for the report vintage;
- `LE_iv` is life expectancy aligned to the same observation window;
- the neutral point of 5 and the cardinal transformation are normative assumptions and will be sensitivity-tested.

The unit is net-happiness-weighted years per resident.

### 3.2 Freely reproducible observation windows

The free official World Happiness Report material provides published three-year life-evaluation scores, while genuine annual Gallup country averages require institutional access or subscription. The public build will therefore use these overlapping report-vintage windows:

| Report vintage | Life-evaluation window | Environmental and demographic window |
|---|---:|---:|
| WHR 2016 | 2013-2015 | annual inputs averaged over 2013-2015 |
| WHR 2017 | 2014-2016 | annual inputs averaged over 2014-2016 |
| WHR 2018 | 2015-2017 | annual inputs averaged over 2015-2017 |

The manuscript will call these overlapping period snapshots or report vintages. It will not call them independent annual observations or use them for annual trend, panel-regression, or causal-policy claims.

For each window:

- life expectancy is the arithmetic mean of the three annual country values;
- country population is the arithmetic mean of the three annual values;
- country GHG is the arithmetic mean of the three annual territorial totals;
- aggregate AQLI burden is computed annually as `population * AQLI years`, then averaged across the three years.

This convention avoids silently pairing a three-year happiness score with a single end-year or midpoint environmental observation.

### 3.3 Primary current-generation responsibility allocation

Let:

```text
B_v = mean_y(sum_j(N_jy * A_jy))
s_iv = G_iv / sum_k(G_kv)
Hbar_v = sum_i(N_iv * H_iv) / sum_i(N_iv)
w_v = (Hbar_v - 5) / 10
P_iv = w_v * s_iv * B_v / N_iv
ERHNI_iv = NHLY_iv - P_iv
```

where:

- `B_v` is the annual-average global ambient-PM life-expectancy burden in raw person-years over the documented AQLI coverage universe;
- `A_jy` is AQLI life expectancy lost per resident under a fixed WHO benchmark;
- `s_iv` is country `i`'s share of covered territorial GHG emissions;
- `Hbar_v` is the population-weighted life evaluation across the ranked analysis sample;
- `w_v` converts raw lost life-years into the net-happiness-weighted unit used by NHLY;
- `P_iv` is the normative current-generation environmental-responsibility penalty per resident.

The pipeline must fail with a clear diagnostic if `w_v <= 0`; it must not clamp or silently replace the value.

This formulation conserves the allocated happiness-weighted burden across the covered source universe:

```text
sum_i(N_iv * P_iv) = w_v * B_v
```

The primary model deliberately drops the inherited `beta`, `gamma`, `theta`, and `xi` chain. It therefore measures a current-generation, PM-mortality-sized burden only. It does not estimate morbidity, harm to future generations, climate damages, or the portion of pollution imposed specifically on people outside the emitting country.

The manuscript will call `P_iv` a normative environmental-responsibility allocation or responsibility penalty. It will not describe it as causal attribution or literal per-capita external cost without the accompanying proxy qualification.

### 3.4 Allocation-key limitation

The primary model sizes the global burden using ambient-PM life-expectancy loss but allocates it using territorial GHG shares. This is a normative polluter-pays proxy, not evidence that the selected GHG inventory caused the contemporaneous PM burden.

The paper must state this structural mismatch when introducing the equation, in the limitations section, and when interpreting rankings.

### 3.5 Cross-vintage comparability

Primary v3 levels are not directly comparable with the 2008 or 2016 published ERHNI levels because the environmental component, unit conversion, coverage, and timing differ. The headline manuscript will not make level or trend claims across vintages.

Cross-vintage comparison will appear only in the legacy reconciliation and sensitivity material, with formula, sample, source, and timing effects separated.

## 4. Source Policy

### 4.1 Primary sources

The pipeline will cite and acquire data from primary or official publishers:

- World Happiness Report official reports, appendices, and data releases;
- World Bank World Development Indicators for life expectancy, population, and GHG totals;
- the official AQLI release for PM2.5 exposure and life-expectancy loss;
- European Commission JRC EDGAR for the air-pollutant allocation sensitivity.

Kaggle mirrors may be retained only as legacy evidence. They will not be cited as the scientific source.

### 4.2 GHG primary and sensitivity series

The primary GHG allocator is World Bank indicator `EN.ATM.GHGT.KT.CE`, total territorial GHG emissions in kt CO2 equivalent, which includes CO2, CH4, N2O, and F-gases under one documented boundary.

A required sensitivity reconstructs the original three-gas boundary as:

```text
three_gas_co2e_kt = co2_kt + ch4_kt_co2e + n2o_kt_co2e
```

The CH4 and N2O series are already CO2-equivalent. No GWP factors may be applied again. A CO2-only sensitivity will also be reported.

### 4.3 AQLI benchmark and vintage

One official AQLI release and one WHO PM2.5 counterfactual must be fixed across all three windows. The source manifest must record the release, benchmark, URL, access date, license or redistribution terms, and SHA-256 checksum.

The current repository snapshot may be used only after its provenance is established against an official release. Otherwise the pipeline must reacquire the official file before generating headline results.

### 4.4 EDGAR air-pollutant sensitivity

The build will include four separate secondary allocations based on country-year emissions of primary PM2.5, SO2, NOx, and NH3 from an official EDGAR country-total release. Each pollutant is used as its own allocation key. Their raw masses will not be summed or converted into an invented combined-pollutant score. These allocations will not be described as source-receptor models.

If an official series has incomplete coverage for one of the three windows, the pipeline will report the available-window result and a machine-readable coverage diagnostic instead of imputing missing pollutant emissions.

## 5. Country Identity, Sample, and Aggregation

The sample size is never a configured target. It is generated by the following rules:

1. every source country name maps through a committed, reviewed crosswalk;
2. each report vintage has at most one row per canonical ISO3 code;
3. a territory is not aliased to a sovereign country's data;
4. every included row has the primary happiness, life-expectancy, population, AQLI, and GHG inputs;
5. the headline panel is balanced across all three report vintages;
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
2. alternative fixed lost-year weights and the observed `w_v` range;
3. the legacy `0.765 * AQLI * emissions-ratio` formula;
4. the legacy ten-times branch as replication evidence only;
5. consolidated total GHG, corrected three-gas, and CO2-only allocation keys;
6. separate EDGAR PM2.5, SO2, NOx, and NH3 allocations;
7. aligned three-year windows versus the old report-year match;
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
  periods.py
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
  country_period.csv
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

- exact World Bank indicator codes and source hashes;
- no second GWP conversion of CO2-equivalent CH4 or N2O;
- exact NHLY and responsibility-penalty unit calculations on synthetic fixtures;
- burden conservation;
- unique `(vintage, ISO3)` rows;
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
- state the unit conversion, current-generation scope, allocation mismatch, overlapping windows, and cross-vintage non-comparability prominently;
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
