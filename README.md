# NCI-IDD Outcomes & Workforce Dashboards — NYS (Simulated)

**Live dashboard:** [https://zia207.github.io/NCI-IDD-dashboard/](https://zia207.github.io/NCI-IDD-dashboard/)

Two professional dashboards for the National Core Indicators – Intellectual and
Developmental Disabilities (NCI-IDD) program for New York State (OPWDD), built on
**simulated** data for all three NCI surveys: the In-Person Survey, the Family
Surveys, and the State of the Workforce Survey.

> **All data are synthetic** and represent no real individuals, families, provider
> agencies, or OPWDD program results. For technical demonstration only.

## What's here

### 1. Python dashboard 
- **`nci_idd_dashboard.html`** — open in any browser. Interactive: a region
  selector filters KPIs and outcome charts; tabs for Overview, In-Person Survey,
  Family Surveys, Workforce, and Methodology. It is **fully self-contained** —
  Plotly.js is inlined, so it works offline and needs no CDN. (Only the web font
  loads from the internet and falls back to system fonts if offline.) GitHub
  Pages serves this file as the site homepage via `.github/workflows/pages.yml`.
- **Interactive workforce map:** the Workforce tab includes a choropleth of the
  10 NYS regions with a metric toggle (DSP turnover / avg wage / vacancy /
  tenure). It is drawn as filled polygons on a cartesian plot (no online map
  tiles or base topojson), so it also works fully offline.
- **`simulate_nci_data.py`** — generates the three survey datasets (seeded/reproducible).
- **`build_geo.py`** — maps NY's 62 counties to the 10 regions and dissolves them
  into `nys_regions.geojson` (14 KB, used to draw the map).
- **`build_dashboard.py`** — aggregates the data and writes the HTML dashboard.

Rebuild from scratch:
```bash
pip install numpy pandas geopandas shapely
python simulate_nci_data.py     # -> nci_ips.csv, nci_family.csv, nci_workforce.csv
python build_geo.py             # -> nys_regions.geojson  (needs us_counties.json; see note)
python build_dashboard.py       # -> nci_idd_dashboard.html
```
*Note:* `build_geo.py` reads a US counties GeoJSON (`us_counties.json`). Download it
once from the public plotly datasets repo, or reuse the included `nys_regions.geojson`
and skip this step. To keep the HTML self-contained, place `plotly.min.js` beside
`build_dashboard.py` (it inlines it; otherwise it falls back to the CDN).

### 2. Tableau dashboard
- **`Tableau_Build_Guide.md`** — complete step-by-step spec to reproduce the same
  dashboard in Tableau: data connections, calculated fields (incl. DSP-weighted
  LOD rates and % favorable), every worksheet, the five dashboards, formatting,
  and the methodology text to embed.
- **`tableau_prep.py`** — reshapes IPS and Family data to long/tidy format so
  `% favorable = AVG([Value]) * 100` in Tableau.
- **`nci_ips_long.csv`, `nci_family_long.csv`** — the Tableau-ready extracts.
- **`nci_workforce.csv`** — used as-is (already agency-level numeric).

### Data dictionary (quick)
- **IPS** — one row per adult respondent; 13 quality-of-life indicators (0/1),
  employment items, demographics (region, age, gender, race/ethnicity, residence
  type, level of I/DD, communication mode).
- **Family** — one row per family respondent; survey type; 8 experience indicators (0/1).
- **Workforce** — one row per provider agency; turnover, vacancy, wages, tenure,
  overtime, benefits, sign-on bonus, region, agency size, DSP count.

## Design notes
Institutional palette (navy `#1C3A5E`, teal `#0F7C8C`, amber `#E0952A`), favorability
banding (green ≥75% / amber 50–74% / red <50%), Source Serif 4 + Public Sans
typography, accessibility-forward contrast and focus states. The signature element
is the **quality-of-life domain scorecard**. Both tools share the same data,
regional filtering model, and analytical story (including the wage–turnover
relationship that speaks to the CMS Access Rule 80% direct-care provision).

© CC-BY Dr. Zia U. Ahmed · github.com/zia207
