# DHV Project — NIRF 2017–2025 Data Cleaning & Unification Pipeline

Complete modular data cleaning and longitudinal unification pipeline for the **NIRF 2017–2025** rankings dataset (`6,966` rows across `17` categories and `9` years).

## Modular Architecture

The pipeline is split into focused Python modules connected through **`main.py`**:

### Entry Point & Configuration
- **`main.py`** — Single entry point that runs the entire end-to-end pipeline (Stage 1 Cleaning + Stage 2 Unification).
- **`config.py`** — File paths, column definitions, standardization mappings (`STATE_MAP`, `CATEGORY_MAP`, `CITY_CLEAN_MAP`), abbreviation/city aliases, and curated manual unification overrides (`MANUAL_2017`, `MANUAL_POST`, `REJECT_PAIRS`, `DO_NOT_MERGE_POST`).

### Stage 1: Data Cleaning (`clean_nirf.py`)
1. **`clean_ranks_scores.py`** — Strips embedded line breaks (`\r\n`), strips alphanumeric rank suffixes (`21A` → `21`), flags `"Rank Withdrawn"` rows (`Rank_Withdrawn`), converts `Rank` to nullable `Int64`, flags missing parameter scores (`Scores_Missing`), and adds `Has_Rank_Tie`, `In_Top100`, and `In_Top50` flags.
2. **`clean_locations_categories.py`** — Standardizes `State` (`33` unique states/UTs), `Category` (`17` consistent title-case categories), and `City` (removes `Dist.`/`District` prefixes, standardizes old/new city names like `Calcutta` → `Kolkata`, `Mysore` → `Mysuru`, `Belgaum` → `Belagavi`, and recovers missing cities from names).
3. **`clean_names_ids.py`** — Extracts `Base_ID` from fragmented NIRF ID schemes, cleans institution names (backticks, mojibake, apostrophes, spaces), maps each `Base_ID` to its latest name (`Name_Standardized`), and disambiguates homonymous colleges (`Name_Display`).
4. **`clean_nirf.py`** — Stage 1 orchestrator that connects the cleaning modules (`nirf_2017_2025_raw.csv` → `nirf_2017_2025_cleaned.csv`).

### Stage 2: Cross-Year Institute Unification (`unify_institutes.py`)
1. **`normalizer.py`** — Normalizes institution names (expands `IIT`/`NIT`/`IIM`/etc., strips noise/punctuation) and cities (`norm_city`, `norm_name`, `strip_city`, `sim`).
2. **`unify_matcher.py`** — Merges duplicate IDs within 2018–2025, matches 2017 legacy IDs (`IR17-...`) to 2018–2025 AISHE-based IDs (`IR-...`) into a single canonical **`Unified_ID`** and **`Name_Unified`** (`2,173` raw IDs → `924` unique institutions), disambiguates homonymous names, and validates uniqueness per `(Year, Category)`.
3. **`unify_institutes.py`** — Stage 2 orchestrator that connects the unification modules (`nirf_2017_2025_cleaned.csv` → `nirf_2017_2025_unified.csv` & `institute_id_mapping.csv`).

## Usage

Run the complete pipeline with a single command:

```bash
python main.py
```

Or run individual stages separately:

```bash
python clean_nirf.py
python unify_institutes.py
```

## Files in Repository

| File | Description |
|---|---|
| `main.py` | Main script that connects and runs the full cleaning + unification pipeline |
| `config.py` | Shared configuration, paths, and mapping dictionaries |
| `clean_nirf.py` | Stage 1 cleaning orchestrator |
| `clean_ranks_scores.py` | Rank, score, tie, and band-comparability cleaning module |
| `clean_locations_categories.py` | State, Category, and City standardization module |
| `clean_names_ids.py` | `Base_ID` extraction, name cleaning, and homonym disambiguation module |
| `unify_institutes.py` | Stage 2 cross-year unification orchestrator |
| `normalizer.py` | Name and city normalization utilities |
| `unify_matcher.py` | Cross-year institute deduplication, matching, and validation module |
| `nirf_2017_2025_raw.csv` | Raw input dataset (6,966 rows, 13 columns) |
| `nirf_2017_2025_unified.csv` | **Final cleaned & unified dataset** (6,966 rows, 24 columns) |
| `institute_id_mapping.csv` | Lookup table of all 924 unified institutions with every raw ID and raw name absorbed |
| `cleaning_log.txt` / `matching_log.txt` | Execution and audit logs |
