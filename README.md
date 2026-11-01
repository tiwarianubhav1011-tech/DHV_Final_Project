# NIRF Interactive Dashboard (2017--2025)

An interactive data analytics dashboard for exploring the National
Institutional Ranking Framework (NIRF) rankings published in India from
2017 to 2025.

The project aims to bring the available NIRF ranking categories and
years into a consistent analytical structure and help users explore
institutional performance through filters, statistical analysis,
visualizations, and (as an advanced extension) natural-language
questions.

> **Project status:** Initial setup / development in progress. Features
> described as planned below should not be considered implemented until
> they have been developed and tested.

## Table of Contents

-   [Project Overview](#project-overview)
-   [Objectives](#objectives)
-   [Project Levels](#project-levels)
-   [Analytical Areas](#analytical-areas)
-   [Data Sources and Coverage](#data-sources-and-coverage)
-   [Data Preparation Approach](#data-preparation-approach)
-   [Proposed Technology Stack](#proposed-technology-stack)
-   [Provisional Project Structure](#provisional-project-structure)
-   [Getting Started](#getting-started)
-   [Data and Methodology
    Considerations](#data-and-methodology-considerations)
-   [Testing and Validation](#testing-and-validation)
-   [Team and Contributions](#team-and-contributions)
-   [Limitations and Future Work](#limitations-and-future-work)
-   [Acknowledgements](#acknowledgements)

## Project Overview

NIRF publishes rankings of higher education institutions across multiple
categories. The categories available, the number of ranked institutions,
and potentially the ranking methodology can vary across years.

This project will develop an interactive dashboard using NIRF data from
**2017 to 2025**, covering every category that can be reliably collected
for each year.

Users should be able to:

-   Explore institutions by year and ranking category.
-   Compare institutions and their scores.
-   Study rank and score trends over time.
-   Examine the geographical distribution of ranked institutions.
-   Investigate relationships between NIRF parameters.
-   Analyze ranking-band transitions and institutional mobility.
-   Identify statistical outliers and performance gaps.
-   Select filters and generate visualizations dynamically.
-   Ask analytical questions in natural language through a planned
    advanced interface.

## Objectives

1.  Collect NIRF ranking data for 2017--2025 from official or otherwise
    reliable sources.
2.  Inspect the available categories, fields, formats, and methodology
    for each year.
3.  Clean and standardize the collected data without losing original
    source information.
4.  Integrate the available years and categories into a documented
    analytical dataset.
5.  Implement the analytical questions in the project assignment's
    Annexure A.
6.  Build a dashboard that supports both predefined questions and new
    combinations of filters and variables.
7.  Explore a natural-language interface that translates questions into
    validated analytical operations.
8.  Test the outputs and document the project's methods, assumptions,
    and limitations.

## Project Levels

### Level 1 --- Sample Questions

Implement all questions in the assignment's Annexure A. Each question
should use the appropriate filters, analytical method, and
visualization.

### Level 2 --- Dynamic Analytical Dashboard

Allow users to select relevant dimensions such as:

-   Year or year range
-   Ranking category
-   Institution
-   State
-   Ranking band
-   Numerical NIRF parameters
-   Two numerical variables for scatter plots and correlation analysis

The dashboard should generate results from the selected data rather than
relying on hardcoded answers.

### Level 3 --- Natural-Language Query Interface

Provide a chat-style interface where a user can ask questions such as:

-   Which institutions improved the most between 2017 and 2025?
-   Compare two institutions in Engineering.
-   Which states have the highest representation in the top 100?
-   Show the relationship between RPC and overall score.
-   Which institutions have high research scores but relatively low
    teaching scores?

The language model, if used, should interpret the question and help
construct a validated query plan. **All numerical results must be
calculated from the actual project dataset.** Generated queries must be
validated before execution; arbitrary AI-generated code must not be
executed.

## Analytical Areas

The dashboard is intended to cover all eight analytical areas in
Annexure A.

  -----------------------------------------------------------------------
  Area                    Example analyses        Possible visualizations
  ----------------------- ----------------------- -----------------------
  Time-series and trend   Rank/score changes,     Line chart, slope chart
  analysis                improvement or decline, 
                          repeated top-10         
                          presence                

  Geospatial and regional State-wise top-100      Choropleth map, bar
  analysis                counts, regional        chart
                          representation, state   
                          comparisons             

  Univariate analysis     Score/rank              Histogram, box plot
                          distributions,          
                          descriptive statistics, 
                          quartiles               

  Bivariate analysis and  RPC vs overall score,   Scatter plot,
  correlation             TLR vs RPC, parameter   regression line,
                          correlations            correlation heatmap

  Multivariate analysis   Compare five            Radar chart,
                          parameters, identify    parallel-coordinates
                          parameter strengths and plot
                          weaknesses              

  Distribution and        Compare score           Box plot, violin plot
  statistical comparison  distributions, spread,  
                          median and IQR          

  Ranking transitions and Movement between rank   Sankey diagram,
  institutional mobility  bands, top-10           transition matrix
                          entry/exit,             
                          upward/downward         
                          movement                

  Outlier detection and   Unusual score changes,  Box plot, scatter plot,
  performance gaps        research/teaching gaps, annotated table
                          ranking volatility      
  -----------------------------------------------------------------------

The chart type will be selected according to the question, data
structure, and analytical purpose. Visualizations will include
meaningful titles, axis labels, legends, and explanatory notes where
appropriate.

## Data Sources and Coverage

The intended period is **2017--2025 inclusive**.

The preferred source is the official NIRF website and its published
ranking data and methodology documents:

-   [NIRF official website](https://www.nirfindia.org/)
-   [NIRF ranking pages](https://www.nirfindia.org/Rankings)

For each year, the project will record:

-   Source URL or document reference
-   Publication year
-   Ranking category
-   Date of retrieval, where relevant
-   Original file name and format
-   Fields available in the source
-   Any extraction or interpretation notes

Not every category necessarily exists in every year. A category that was
not published in a particular year must be represented as unavailable,
not as a zero score or an empty ranking.

The exact year-by-category coverage will be established during data
collection and documented in a coverage matrix.

## Data Preparation Approach

The project will keep original source files separate from cleaned and
integrated data.

Planned preparation steps:

1.  Inventory and preserve the original downloaded files.
2.  Inspect each file's structure, columns, units, and data types.
3.  Record differences in category coverage and methodology across
    years.
4.  Standardize column names and data types where meanings are
    equivalent.
5.  Preserve original institution names and category labels alongside
    standardized values.
6.  Create and review institution-name aliases; use stable official
    identifiers where available.
7.  Standardize state and location names using a documented mapping.
8.  Detect exact duplicates and investigate possible duplicate
    institutions.
9.  Handle missing, suppressed, unavailable, and not-applicable values
    distinctly.
10. Validate ranks, score ranges, parameter values, and record counts.
11. Integrate compatible records while retaining year and category.
12. Save cleaning decisions and data lineage so results can be
    reproduced.

### Proposed data fields

The final schema will depend on what is available in the source files.
Candidate fields include:

  -----------------------------------------------------------------------
  Field                               Description
  ----------------------------------- -----------------------------------
  `year`                              Ranking publication year

  `category_original`                 Category label as published

  `category_standardized`             Harmonized category label

  `institution_name_original`         Institution name as published

  `institution_name_standardized`     Reviewed standardized institution
                                      name

  `institution_id`                    Stable identifier, if available and
                                      reliable

  `city`                              Institution city, if available

  `state_original`                    State/UT label as published

  `state_standardized`                Standardized state/UT label

  `rank`                              Published rank or rank-band
                                      information

  `score`                             Overall score, if published

  `tlr`                               Teaching, Learning and Resources
                                      score, if available

  `rpc`                               Research and Professional Practice
                                      score, if available

  `go`                                Graduation Outcomes score, if
                                      available

  `oi`                                Outreach and Inclusivity score, if
                                      available

  `pr`                                Perception score, if available

  `source_file`                       Source file used for the record
  -----------------------------------------------------------------------

These are proposed fields, not a claim that every source year contains
every field.

## Proposed Technology Stack

The implementation will primarily use Python.

  -----------------------------------------------------------------------
  Technology                          Intended use
  ----------------------------------- -----------------------------------
  Python                              Main programming language

  Pandas                              Data inspection, cleaning,
                                      transformation, and integration

  NumPy                               Numerical operations

  Matplotlib / Seaborn                Statistical and exploratory
                                      visualizations

  Plotly                              Interactive charts

  Streamlit                           Interactive dashboard application

  GeoPandas or Plotly geographic      Geographical analysis, where
  features                            suitable

  SciPy / scikit-learn                Selected statistical methods and
                                      analytical techniques

  LLM API or local model (to be       Natural-language question
  evaluated)                          interpretation, if feasible
  -----------------------------------------------------------------------

The final stack may be adjusted to keep the application reliable,
understandable, and suitable for the project evaluation.

## Provisional Project Structure

The repository may evolve as the source formats and implementation
become clearer.

``` text
nirf-interactive-dashboard/
│
├── data/
│   ├── raw/                 # Original downloaded source files; do not edit
│   │   ├── 2017/
│   │   ├── 2018/
│   │   └── .../
│   ├── processed/           # Cleaned and integrated datasets
│   └── reference/           # Category, state, alias and methodology mappings
│
├── notebooks/
│   ├── 01_data_inspection.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_data_integration.ipynb
│   ├── 04_exploratory_analysis.ipynb
│   └── 05_analytical_questions.ipynb
│
├── src/
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── analytics.py
│   ├── visualizations.py
│   └── query_engine.py
│
├── dashboard/
│   ├── app.py
│   ├── pages/
│   └── components/
│
├── tests/
├── docs/
├── requirements.txt
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

-   Python 3.10 or a compatible version selected for the project
    dependencies
-   Git
-   GitHub account
-   Visual Studio Code or another Python IDE

### 1. Clone the repository

Replace the placeholder with the URL of your GitHub repository.

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd nirf-interactive-dashboard
```

### 2. Create a virtual environment

``` bash
python -m venv .venv
```

Activate it:

**macOS / Linux**

``` bash
source .venv/bin/activate
```

**Windows PowerShell**

``` powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

Once `requirements.txt` has been created and reviewed:

``` bash
pip install -r requirements.txt
```

### 4. Run the dashboard

After the Streamlit application has been implemented:

``` bash
streamlit run dashboard/app.py
```

> The dashboard command is a planned run instruction. It will work after
> the application entry point and its dependencies have been
> implemented.

## Data and Methodology Considerations

Historical comparisons require care.

-   **Category coverage:** Do not compare a category in a year in which
    it was not published.
-   **Rank versus score:** Rank is ordinal (a smaller number is better);
    score is numerical (a larger score is better). Analyze them
    separately.
-   **Rank bands:** Some rankings may publish rank ranges rather than
    exact positions. Do not invent exact ranks for institutions in a
    band.
-   **Missing data:** Distinguish unavailable data, unranked
    institutions, suppressed values, and values that are genuinely
    missing.
-   **Institution identity:** Names may change or appear in different
    formats. Do not merge records based only on approximate text
    similarity.
-   **Methodology changes:** Parameter definitions, weights, and
    category rules may change. Check the relevant year's methodology
    before interpreting long-term score comparisons.
-   **Correlation:** Association between two parameters does not
    establish causation.
-   **Geography:** State-wise counts depend on the selected year,
    category, and ranking cutoff. Use clear denominators and filters.
-   **Ranking mobility:** An institution absent from a later published
    list cannot automatically be described as having declined to a
    particular rank.

All analytical assumptions and transformations should be documented.

## Testing and Validation

Planned checks include:

-   Verify source files and record counts.
-   Check required columns and data types.
-   Check duplicate records using appropriate keys.
-   Validate rank and score ranges against the source.
-   Verify year/category coverage.
-   Compare selected cleaned records with their original source.
-   Test calculations against manually checked examples.
-   Test filters with empty and single-record results.
-   Test rank-band transitions without assigning invented ranks.
-   Ensure charts use the correct year, category, and parameter.
-   Test natural-language query interpretation and reject unsupported or
    ambiguous requests.
-   Confirm that all displayed numerical answers come from executed
    analytical operations.

## Team and Contributions

The assignment requires a team of **6--8 members**.

Suggested work areas:

-   Data collection and source verification
-   Data cleaning and standardization
-   Dataset integration and exploratory analysis
-   Statistical analysis and analytical functions
-   Visualization and geographical analysis
-   Dashboard development and dynamic filters
-   Natural-language interface
-   Testing, documentation, and presentation

Actual team members and responsibilities will be added once finalized.

Contributions should be made through descriptive commits and, where
practical, reviewed pull requests.

## Limitations and Future Work

Potential limitations include incomplete historical source availability,
changes in NIRF methodology, institution-name inconsistencies, rank-band
reporting, and differences in category coverage.

Future improvements may include:

-   More detailed institution identity resolution
-   Additional geographical analysis
-   Downloadable filtered reports
-   More advanced statistical comparisons
-   Improved natural-language question interpretation
-   Deployment of the dashboard for public access

## Acknowledgements

-   National Institutional Ranking Framework (NIRF), Ministry of
    Education, Government of India, for published ranking information
    and methodology documents.
-   Course instructors and laboratory materials that support the data
    handling, statistical analysis, and visualization techniques used in
    this project.
-   All project team members and contributors.

------------------------------------------------------------------------

**Academic project:** NIRF Interactive Dashboard (2017--2025)\
**Evaluation:** November 7, 2026\
**Status:** Development in progress
