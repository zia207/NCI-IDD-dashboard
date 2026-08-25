"""
build_dashboard.py
==================
Reads the three simulated NCI-IDD CSVs and generates a single, self-contained,
GitHub-Pages-ready interactive dashboard: nci_idd_dashboard.html

Interactivity is client-side (Plotly.js via CDN + vanilla JS): a global region
selector filters KPIs and outcome charts; regional-comparison charts stay full.
No server required. All data are simulated.
"""

import json
import datetime as dt
import numpy as np
import pandas as pd

ips = pd.read_csv("nci_ips.csv")
fam = pd.read_csv("nci_family.csv")
wf = pd.read_csv("nci_workforce.csv")

REGIONS = ["Western New York", "Finger Lakes", "Central New York", "Southern Tier",
           "Mohawk Valley", "North Country", "Capital Region", "Hudson Valley",
           "New York City", "Long Island"]
ALL = "Statewide"

# Reported response/participation rates (simulated program metrics)
RESP = {"ips": 72, "family": 41, "workforce": 63}

IPS_DOMAINS = {
    "choice_where_lives": "Chose where they live",
    "choice_who_lives_with": "Chose who they live with",
    "choice_daily_schedule": "Decides own daily schedule",
    "community_participation": "Participates in community as wanted",
    "has_close_friends": "Has close friends / relationships",
    "health_has_pcp": "Has a primary care doctor",
    "health_dental_pastyear": "Dental visit in past year",
    "health_screenings_current": "Health screenings up to date",
    "safety_feels_safe_home": "Feels safe at home",
    "safety_knows_who_to_tell": "Knows who to tell if abused/mistreated",
    "rights_privacy_respected": "Privacy is respected",
    "self_direction_uses": "Uses self-directed services",
    "case_mgmt_satisfied": "Satisfied with case management",
}
FAM_INDICATORS = {
    "satisfied_with_services": "Satisfied with services overall",
    "satisfied_case_management": "Satisfied with case management",
    "involved_in_service_planning": "Involved in service planning",
    "gets_needed_information": "Gets the information they need",
    "services_meet_needs": "Services meet the person's needs",
    "respite_access_adequate": "Adequate access to respite",
    "community_connections_support": "Supported to build community connections",
    "would_recommend_services": "Would recommend services",
}


def pct(series):
    return round(float(series.mean()) * 100, 1)


def ips_agg(df):
    out = {"n": int(len(df))}
    out["domains"] = {k: pct(df[k]) for k in IPS_DOMAINS}
    out["emp_has"] = pct(df["employment_has_community_job"])
    nojob = df[df["employment_has_community_job"] == 0]
    out["emp_wants"] = pct(nojob["employment_wants_job"]) if len(nojob) else 0.0
    res = (df["residence_type"].value_counts(normalize=True) * 100).round(1)
    out["residence"] = res.to_dict()
    return out


def fam_agg(df):
    out = {"n": int(len(df))}
    out["indicators"] = {k: pct(df[k]) for k in FAM_INDICATORS}
    return out


def wf_agg(df):
    out = {"n_agencies": int(len(df)), "n_dsp": int(df["num_dsp"].sum())}
    w = df["num_dsp"]
    for col, key in [("dsp_turnover_rate", "turnover"), ("dsp_vacancy_rate", "vacancy"),
                     ("avg_hourly_wage", "wage"), ("starting_hourly_wage", "start_wage"),
                     ("avg_tenure_months", "tenure"), ("pct_overtime_hours", "overtime")]:
        out[key] = round(float(np.average(df[col], weights=w)), 1)
    for col, key in [("offers_health_insurance", "health"),
                     ("offers_retirement_plan", "retirement"),
                     ("offers_paid_time_off", "pto"),
                     ("uses_signon_bonus", "signon")]:
        out[key] = pct(df[col])
    return out


# ---- Build region-keyed aggregates ----------------------------------------
def by_region(df, fn):
    d = {ALL: fn(df)}
    for r in REGIONS:
        d[r] = fn(df[df["region"] == r])
    return d


DATA = {
    "regions": REGIONS,
    "responseRates": RESP,
    "ipsDomainLabels": IPS_DOMAINS,
    "famIndicatorLabels": FAM_INDICATORS,
    "ips": by_region(ips, ips_agg),
    "family": by_region(fam, fam_agg),
    "workforce": by_region(wf, wf_agg),
    # By family survey type (static)
    "familyByType": {
        t: {k: pct(fam[fam["survey_type"] == t][k]) for k in FAM_INDICATORS}
        for t in ["Child Family Survey", "Adult Family Survey", "Family/Guardian Survey"]
    },
    # Region comparison series (static)
    "counts": {
        "ips": {r: int((ips["region"] == r).sum()) for r in REGIONS},
        "family": {r: int((fam["region"] == r).sum()) for r in REGIONS},
    },
    "turnoverByRegion": {
        r: round(float(np.average(
            wf[wf["region"] == r]["dsp_turnover_rate"],
            weights=wf[wf["region"] == r]["num_dsp"])), 1) for r in REGIONS
    },
    "respiteByRegion": {r: pct(fam[fam["region"] == r]["respite_access_adequate"])
                        for r in REGIONS},
    # Agency-level points for the wage/turnover scatter
    "agencies": [
        {"region": row.region, "size": row.agency_size,
         "wage": float(row.avg_hourly_wage), "turnover": float(row.dsp_turnover_rate),
         "dsp": int(row.num_dsp)}
        for row in wf.itertuples()
    ],
}

# Headline KPIs (statewide)
DATA["kpi"] = {
    "ips_n": DATA["ips"][ALL]["n"],
    "fam_n": DATA["family"][ALL]["n"],
    "agencies": DATA["workforce"][ALL]["n_agencies"],
    "dsp": DATA["workforce"][ALL]["n_dsp"],
}

# --- Geospatial: NYS region polygons + per-region workforce map metrics --------
_geo = json.load(open("nys_regions.geojson"))
wfR = DATA["workforce"]
DATA["mapMetrics"] = {
    "turnover": {"label": "DSP turnover", "suffix": "%", "prefix": "", "better": "low",
                 "vals": {r: DATA["turnoverByRegion"][r] for r in REGIONS}},
    "wage":     {"label": "Avg hourly wage", "suffix": "", "prefix": "$", "better": "high",
                 "vals": {r: wfR[r]["wage"] for r in REGIONS}},
    "vacancy":  {"label": "Vacancy rate", "suffix": "%", "prefix": "", "better": "low",
                 "vals": {r: wfR[r]["vacancy"] for r in REGIONS}},
    "tenure":   {"label": "Avg tenure (mo)", "suffix": "", "prefix": "", "better": "high",
                 "vals": {r: wfR[r]["tenure"] for r in REGIONS}},
}

# Draw regions as filled polygons on a plain cartesian plot (no geo module, so it
# works fully offline). Longitude is pre-scaled by cos(lat) for a correct local
# aspect ratio; each region's rings are one x/y array separated by nulls.
import math
from shapely.geometry import shape
COSLAT = math.cos(math.radians(42.9))  # NY mean latitude


def rings_xy(geom):
    xs, ys = [], []
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            for lon, lat in ring.coords:
                xs.append(round(lon * COSLAT, 4)); ys.append(round(lat, 4))
            xs.append(None); ys.append(None)  # break between rings
    return xs, ys


DATA["mapShapes"] = {}
for feat in _geo["features"]:
    r = feat["properties"]["region"]
    g = shape(feat["geometry"])
    xs, ys = rings_xy(g)
    c = g.representative_point()  # a point guaranteed inside the polygon
    DATA["mapShapes"][r] = {"x": xs, "y": ys,
                            "cx": round(c.x * COSLAT, 4), "cy": round(c.y, 4)}

gendate = dt.date.today().strftime("%B %d, %Y")

# Self-contained if a local plotly.min.js sits next to this script; else CDN.
import os
CDN_TAG = ('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" '
           'charset="utf-8"></script>')
if os.path.exists("plotly.min.js"):
    with open("plotly.min.js", encoding="utf-8") as pf:
        plotly_tag = "<script>\n" + pf.read() + "\n</script>"
    print("Inlining local plotly.min.js -> fully self-contained (works offline).")
else:
    plotly_tag = CDN_TAG
    print("No local plotly.min.js found -> using CDN (needs internet). "
          "Place plotly.min.js next to this script for a self-contained file.")

# ===========================================================================
# HTML TEMPLATE  (design + Plotly.js). __DATA__ / __GENDATE__ injected below.
# ===========================================================================
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NCI-IDD Outcomes & Workforce Dashboard — NYS (Simulated)</title>
__PLOTLY_JS__
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#14202E; --navy:#1C3A5E; --navy-d:#132a44; --teal:#0F7C8C; --teal-b:#17A2B8;
    --amber:#E0952A; --bg:#EEF2F6; --card:#FFFFFF; --line:#DCE3EC; --muted:#5C6B7E;
    --good:#2E8B6F; --mid:#E0952A; --low:#C6553F;
    --shadow:0 1px 2px rgba(20,32,46,.06),0 4px 16px rgba(20,32,46,.06);
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Public Sans",system-ui,-apple-system,sans-serif;line-height:1.5;
    -webkit-font-smoothing:antialiased}
  h1,h2,h3{font-family:"Source Serif 4",Georgia,serif;font-weight:600;line-height:1.15;margin:0}
  a{color:var(--teal)}
  .wrap{max-width:1200px;margin:0 auto;padding:0 24px}

  /* Header */
  header{background:linear-gradient(180deg,var(--navy) 0%,var(--navy-d) 100%);color:#fff;
    position:sticky;top:0;z-index:50;box-shadow:0 2px 14px rgba(19,42,68,.25)}
  .hbar{display:flex;align-items:center;gap:18px;padding:14px 24px;max-width:1200px;margin:0 auto;flex-wrap:wrap}
  .logo{flex:0 0 auto;display:block;height:68px;width:auto;border-radius:8px;background:#fff;
    box-shadow:0 1px 3px rgba(0,0,0,.18)}
  .brand{display:flex;flex-direction:column}
  .brand .eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:#9FC0D8;font-weight:700}
  .brand h1{font-size:20px;color:#fff}
  .spacer{flex:1}
  .region-pick{display:flex;align-items:center;gap:8px}
  .region-pick label{font-size:12px;color:#C6D8E6;text-transform:uppercase;letter-spacing:.08em;font-weight:600}
  select#region{font-family:inherit;font-size:14px;font-weight:600;color:var(--ink);
    background:#fff;border:1px solid #2c5580;border-radius:8px;padding:8px 12px;min-width:190px;cursor:pointer}
  select#region:focus-visible{outline:3px solid var(--amber);outline-offset:2px}
  nav.tabs{display:flex;gap:2px;max-width:1200px;margin:0 auto;padding:0 16px;flex-wrap:wrap}
  nav.tabs button{font-family:inherit;font-size:13.5px;font-weight:600;color:#BcCfe0;color:#B9CDDE;
    background:transparent;border:0;border-bottom:3px solid transparent;padding:11px 16px;cursor:pointer}
  nav.tabs button:hover{color:#fff}
  nav.tabs button.active{color:#fff;border-bottom-color:var(--amber)}
  nav.tabs button:focus-visible{outline:2px solid var(--amber);outline-offset:-2px;border-radius:4px}

  /* Simulated-data banner */
  .banner{background:#FBE7D2;border-bottom:1px solid #EBC98F;color:#7A4E12}
  .banner .wrap{display:flex;gap:10px;align-items:flex-start;padding:10px 24px;font-size:13px}
  .banner strong{font-weight:800;letter-spacing:.02em}
  .banner .dot{flex:0 0 auto;width:18px;height:18px;border-radius:50%;background:var(--amber);color:#fff;
    font-weight:800;font-size:12px;display:grid;place-items:center;margin-top:1px}

  main{padding:26px 0 60px}
  .panel{display:none} .panel.active{display:block;animation:fade .35s ease}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  .scope{display:flex;align-items:baseline;gap:12px;margin:2px 0 18px}
  .scope h2{font-size:23px}
  .scope .tag{font-size:12.5px;color:var(--muted);font-weight:600}
  .intro{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);
    padding:16px 20px;margin-bottom:20px;font-size:14.5px;color:var(--ink);line-height:1.55}
  .intro p{margin:0}
  .intro strong{color:var(--navy);font-weight:700}

  /* KPI cards */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:14px;margin-bottom:22px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 14px;
    box-shadow:var(--shadow);position:relative;overflow:hidden}
  .kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--teal)}
  .kpi.alt::before{background:var(--amber)} .kpi.good::before{background:var(--good)}
  .kpi .label{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em}
  .kpi .val{font-size:30px;font-weight:800;font-family:"Public Sans";margin-top:6px;letter-spacing:-.02em}
  .kpi .sub{font-size:12px;color:var(--muted);margin-top:3px}

  .grid{display:grid;gap:18px}
  .g2{grid-template-columns:1fr 1fr} .g3{grid-template-columns:2fr 1fr}
  @media(max-width:860px){.g2,.g3{grid-template-columns:1fr}}
  .chartcard{background:var(--card);border:1px solid var(--line);border-radius:12px;
    box-shadow:var(--shadow);padding:18px 18px 8px}
  .chartcard h3{font-size:16px;margin-bottom:2px}
  .chartcard .hint{font-size:12.5px;color:var(--muted);margin:2px 0 8px}
  .plot{width:100%;height:340px}
  .plot.tall{height:430px}
  .metric-toggle{display:inline-flex;background:#EAF0F5;border-radius:8px;padding:3px;flex-wrap:wrap}
  .metric-toggle button{font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);
    background:transparent;border:0;border-radius:6px;padding:6px 11px;cursor:pointer}
  .metric-toggle button:hover{color:var(--ink)}
  .metric-toggle button.active{background:#fff;color:var(--navy);box-shadow:0 1px 2px rgba(20,32,46,.12)}
  .metric-toggle button:focus-visible{outline:2px solid var(--amber);outline-offset:1px}
  .cardhead{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:10px}

  /* Signature: domain scorecard */
  .scorecard{background:var(--card);border:1px solid var(--line);border-radius:12px;
    box-shadow:var(--shadow);padding:20px 20px 10px;margin-bottom:22px}
  .scorecard .head{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:4px}
  .scorecard h3{font-size:17px}
  .legend{display:flex;gap:16px;font-size:12px;color:var(--muted);font-weight:600}
  .legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:baseline}
  .lg-good::before{background:var(--good)} .lg-mid::before{background:var(--mid)} .lg-low::before{background:var(--low)}
  .sc-row{display:grid;grid-template-columns:1fr;gap:9px;margin-top:12px}
  .sc-item{display:grid;grid-template-columns:270px 1fr 52px;align-items:center;gap:14px}
  @media(max-width:680px){.sc-item{grid-template-columns:1fr;gap:2px}}
  .sc-item .name{font-size:13.5px;font-weight:600;color:var(--ink)}
  .sc-track{background:#EAF0F5;border-radius:6px;height:16px;overflow:hidden}
  .sc-fill{height:100%;border-radius:6px;transition:width .5s ease}
  .sc-item .num{font-weight:800;font-size:14px;text-align:right;font-variant-numeric:tabular-nums}

  /* Methodology */
  .method{display:grid;gap:18px}
  .mcard{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:22px 24px}
  .mcard h3{font-size:19px;color:var(--navy);margin-bottom:4px}
  .mcard .who{font-size:12.5px;font-weight:700;color:var(--teal);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
  .mcard h4{font-family:"Public Sans";font-size:13px;text-transform:uppercase;letter-spacing:.05em;
    color:var(--muted);margin:16px 0 6px}
  .mcard p{margin:0 0 10px;font-size:14.5px}
  .mcard ul{margin:0 0 10px;padding-left:20px;font-size:14.5px}
  .mcard li{margin-bottom:5px}
  .glossary{display:grid;grid-template-columns:minmax(108px,168px) 1fr;gap:10px 20px;margin:8px 0 0}
  .glossary dt{font-weight:800;color:var(--navy);font-size:13.5px;letter-spacing:.01em}
  .glossary dd{margin:0;font-size:14.5px;color:var(--ink)}
  @media(max-width:560px){.glossary{grid-template-columns:1fr;gap:2px}
    .glossary dt{margin-top:10px}.glossary dt:first-child{margin-top:0}}

  footer{border-top:1px solid var(--line);background:#fff;padding:22px 0;margin-top:20px}
  footer .wrap{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;
    font-size:13px;color:var(--muted)}
  footer a{font-weight:600;text-decoration:none}
  .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
</style>
</head>
<body>
<header>
  <div class="hbar">
    <img class="logo" src="upatta_logo.png" alt="Upatta Data Analytics" width="68" height="68">
    <div class="brand">
      <span class="eyebrow">NYS OPWDD &middot; Bureau of Population Health</span>
      <h1>NCI-IDD Outcomes &amp; Workforce Dashboard</h1>
    </div>
    <div class="spacer"></div>
    <div class="region-pick">
      <label for="region">Region</label>
      <select id="region" aria-label="Filter dashboard by region"></select>
    </div>
  </div>
  <nav class="tabs" role="tablist">
    <button class="active" data-tab="overview" role="tab">Overview</button>
    <button data-tab="ips" role="tab">In-Person Survey</button>
    <button data-tab="family" role="tab">Family Surveys</button>
    <button data-tab="workforce" role="tab">Workforce Survey</button>
    <button data-tab="method" role="tab">Methodology &amp; Uses</button>
  </nav>
</header>

<div class="banner">
  <div class="wrap">
    <span class="dot">!</span>
    <div><strong>SIMULATED DATA — DEMONSTRATION ONLY.</strong> All figures are synthetic and generated
    for a technical demonstration of an NCI-IDD reporting dashboard. They do not represent any real
    individuals, families, provider agencies, or OPWDD program results.</div>
  </div>
</div>

<main class="wrap">

  <!-- OVERVIEW -->
  <section class="panel active" id="overview">
    <div class="intro">
      <p><strong>National Core Indicators – Intellectual and Developmental Disabilities (NCI-IDD)</strong>
      is a voluntary national effort (sponsored by NASDDDS and HSRI) to measure and improve the
      performance of state developmental-disabilities agencies using standardized indicators, so
      states can benchmark against each other. Nearly all states participate; states don't run
      every survey every year.</p>
    </div>
    <div class="scope"><h2>Statewide performance at a glance</h2><span class="tag" id="scope-ov"></span></div>
    <div class="kpis" id="kpis-ov"></div>

    <div class="scorecard">
      <div class="head">
        <h3>Quality-of-life domain scorecard <span style="font-family:'Public Sans';font-weight:600;font-size:13px;color:var(--muted)">— In-Person Survey, % favorable</span></h3>
        <div class="legend">
          <span class="lg-good">&ge;75% favorable</span>
          <span class="lg-mid">50–74%</span>
          <span class="lg-low">&lt;50%</span>
        </div>
      </div>
      <div class="sc-row" id="scorecard"></div>
    </div>

    <div class="grid g2">
      <div class="chartcard"><h3>Survey responses by region</h3>
        <p class="hint">In-Person and Family survey completions across NYS regions.</p>
        <div id="c-counts" class="plot"></div></div>
      <div class="chartcard"><h3>Where participants live</h3>
        <p class="hint">Residence type of In-Person Survey respondents.</p>
        <div id="c-residence" class="plot"></div></div>
    </div>
  </section>

  <!-- IPS -->
  <section class="panel" id="ips">
    <div class="scope"><h2>In-Person Survey — quality of life &amp; service experience</h2><span class="tag" id="scope-ips"></span></div>
    <div class="kpis" id="kpis-ips"></div>
    <div class="grid g2">
      <div class="chartcard"><h3>Outcome indicators, % favorable</h3>
        <p class="hint">Share of adult respondents reporting favorable outcomes across NCI domains.</p>
        <div id="c-ips-domains" class="plot tall"></div></div>
      <div class="chartcard"><h3>Health &amp; safety access</h3>
        <p class="hint">Key access indicators for the selected scope.</p>
        <div id="c-ips-health" class="plot tall"></div></div>
    </div>
  </section>

  <!-- FAMILY -->
  <section class="panel" id="family">
    <div class="scope"><h2>Family Surveys — family &amp; guardian experience</h2><span class="tag" id="scope-fam"></span></div>
    <div class="kpis" id="kpis-fam"></div>
    <div class="grid g2">
      <div class="chartcard"><h3>Family experience by survey type</h3>
        <p class="hint">% favorable across the three family survey instruments (statewide).</p>
        <div id="c-fam-type" class="plot tall"></div></div>
      <div class="chartcard"><h3>Family indicators for selected scope</h3>
        <p class="hint">% favorable for the region chosen above.</p>
        <div id="c-fam-ind" class="plot tall"></div></div>
    </div>
    <div class="chartcard" style="margin-top:18px"><h3>Adequate respite access by region</h3>
      <p class="hint">Respite is a common access gap — lower values flag priority regions.</p>
      <div id="c-fam-respite" class="plot"></div></div>
  </section>

  <!-- WORKFORCE -->
  <section class="panel" id="workforce">
    <div class="scope"><h2>State of the Workforce — Direct Support Professionals</h2><span class="tag" id="scope-wf"></span></div>
    <div class="kpis" id="kpis-wf"></div>
    <div class="chartcard" style="margin-bottom:18px">
      <div class="cardhead">
        <div>
          <h3>Workforce map — DSP metrics by region</h3>
          <p class="hint">Choropleth of the 10 NYS regions. Switch the metric with the toggle; hover a region for its value.</p>
        </div>
        <div class="metric-toggle" id="map-toggle" role="group" aria-label="Map metric"></div>
      </div>
      <div id="c-wf-map" class="plot" style="height:470px"></div>
    </div>
    <div class="grid g2">
      <div class="chartcard"><h3>DSP turnover by region</h3>
        <p class="hint">Annual turnover (DSP-weighted). Dashed line = statewide average.</p>
        <div id="c-wf-turnover" class="plot"></div></div>
      <div class="chartcard"><h3>Wages vs. turnover, by agency</h3>
        <p class="hint">Each point is a provider agency; size = number of DSPs.</p>
        <div id="c-wf-scatter" class="plot"></div></div>
    </div>
    <div class="chartcard" style="margin-top:18px"><h3>Benefits offered by agencies</h3>
      <p class="hint">% of agencies offering each benefit, for the selected scope.</p>
      <div id="c-wf-benefits" class="plot" style="height:260px"></div></div>
  </section>

  <!-- METHODOLOGY -->
  <section class="panel" id="method">
    <div class="scope"><h2>Survey methodology, data &amp; analysis uses</h2></div>
    <div class="method">
      <div class="mcard">
        <h3>In-Person Survey (IPS)</h3>
        <div class="who">Adults 18+ receiving case management + at least one paid service</div>
        <h4>Methodology</h4>
        <p>A trained interviewer holds a structured, face-to-face or HIPAA-compliant remote conversation
        with each participant, who may be supported by staff or family for scheduling and access.
        Participation is voluntary and does not affect a person's services. A random sample is drawn from
        the eligible OPWDD service population and stratified so that regions and residential settings are
        represented. In this demonstration, a completed-interview response rate of <b id="m-ips-rr"></b>
        is assumed.</p>
        <h4>Data collected</h4>
        <p>Standardized NCI indicators across choice and decision-making, community participation,
        relationships, competitive/community employment, health and wellness, safety, rights and respect,
        self-direction, and satisfaction with case management — plus demographics (age, gender,
        race/ethnicity, residence type, level of I/DD, communication mode).</p>
        <h4>Analysis uses</h4>
        <ul>
          <li>Benchmark NYS quality-of-life outcomes against national NCI averages and prior cycles.</li>
          <li>Surface disparities by region, residential setting, and level of disability for targeted action.</li>
          <li>Evidence for CMS Access Rule person-centered-planning and HCBS quality-measure reporting.</li>
          <li>Apply nonresponse weighting / poststratification so estimates reflect the full population.</li>
        </ul>
      </div>

      <div class="mcard">
        <h3>Family Surveys</h3>
        <div class="who">Child Family &middot; Adult Family &middot; Family/Guardian</div>
        <h4>Methodology</h4>
        <p>Three mail/online instruments capture the experience of families and guardians. The
        <b>Child Family Survey</b> reaches families of children (3–17) with I/DD living at home; the
        <b>Adult Family Survey</b> reaches families of adults living at home; and the
        <b>Family/Guardian Survey</b> reaches guardians of adults living outside the family home. Mailed
        surveys typically yield lower response than in-person interviews; this demonstration assumes a
        <b id="m-fam-rr"></b> response rate, making nonresponse analysis essential.</p>
        <h4>Data collected</h4>
        <p>Satisfaction with services and case management, involvement in service planning, access to
        information, whether services meet needs, respite access, support for community connections, and
        likelihood to recommend.</p>
        <h4>Analysis uses</h4>
        <ul>
          <li>Compare family-reported access and satisfaction across survey type and region.</li>
          <li>Identify service gaps (e.g., respite) that drive family strain and unmet need.</li>
          <li>Triangulate family perspective against participant (IPS) outcomes for the same system.</li>
        </ul>
      </div>

      <div class="mcard">
        <h3>State of the Workforce Survey</h3>
        <div class="who">Completed by provider agencies about their DSP workforce</div>
        <h4>Methodology</h4>
        <p>Voluntary provider agencies report agency-level workforce metrics for a defined reporting year.
        Eligible agencies employ Direct Support Professionals (staff spending ≥50% of their role supporting
        adults with I/DD) and have operated at least six continuous months. This demonstration assumes a
        <b id="m-wf-rr"></b> agency participation rate; statewide rates are <b>weighted by the number of
        DSPs</b> each agency employs so larger workforces count proportionally.</p>
        <h4>Data collected</h4>
        <p>DSP turnover and vacancy rates, average and starting hourly wage, average tenure, overtime
        reliance, benefits offered (health, retirement, paid time off), and use of sign-on bonuses, by
        region and agency size.</p>
        <h4>Analysis uses</h4>
        <ul>
          <li>Monitor the DSP workforce crisis — turnover, vacancy, and wage adequacy — over time.</li>
          <li>Directly informs the CMS Access Rule 80% direct-care compensation provision.</li>
          <li>Model wage–turnover relationships to target retention investment where it moves outcomes.</li>
        </ul>
      </div>

      <div class="mcard">
        <h3>Acronyms used in this dashboard</h3>
        <p>Short forms that appear in titles, KPIs, charts, and narrative throughout this demonstration.</p>
        <dl class="glossary">
          <dt>CMS</dt>
          <dd>Centers for Medicare &amp; Medicaid Services — the federal agency whose Access Rule (including the 80% direct-care compensation provision) is referenced in analysis uses.</dd>
          <dt>DSP</dt>
          <dd>Direct Support Professional — staff who spend at least half their role supporting adults with I/DD; the unit of analysis for the Workforce Survey.</dd>
          <dt>HCBS</dt>
          <dd>Home and Community-Based Services — Medicaid-funded supports delivered outside institutions; NCI indicators inform HCBS quality-measure reporting.</dd>
          <dt>HIPAA</dt>
          <dd>Health Insurance Portability and Accountability Act — the privacy standard referenced for remote In-Person Survey interviews.</dd>
          <dt>HSRI</dt>
          <dd>Human Services Research Institute — co-sponsor of NCI-IDD with NASDDDS.</dd>
          <dt>I/DD</dt>
          <dd>Intellectual and/or Developmental Disabilities — the population served by the NCI-IDD program and by OPWDD.</dd>
          <dt>ICF</dt>
          <dd>Intermediate Care Facility — a certified residential setting that appears in the “Where participants live” breakdown.</dd>
          <dt>IPS</dt>
          <dd>In-Person Survey — the NCI-IDD interview of adults 18+ who receive case management and at least one paid service.</dd>
          <dt>IRA</dt>
          <dd>Individualized Residential Alternative — an OPWDD-certified group living setting shown as “Certified Group Home/IRA.”</dd>
          <dt>NASDDDS</dt>
          <dd>National Association of State Directors of Developmental Disabilities Services — co-sponsor of NCI-IDD with HSRI.</dd>
          <dt>NCI</dt>
          <dd>National Core Indicators — the standardized performance measures used across participating states.</dd>
          <dt>NCI-IDD</dt>
          <dd>National Core Indicators – Intellectual and Developmental Disabilities — the voluntary national program this dashboard demonstrates.</dd>
          <dt>NYS</dt>
          <dd>New York State — the geographic scope of this demonstration (ten OPWDD regions).</dd>
          <dt>OPWDD</dt>
          <dd>Office for People With Developmental Disabilities — New York State’s developmental-disabilities agency.</dd>
          <dt>PCP</dt>
          <dd>Primary care provider (primary care doctor) — the health-access indicator shown as “Has PCP” on the In-Person Survey tab.</dd>
        </dl>
      </div>
    </div>
  </section>
</main>

<footer><div class="wrap">
  <div>NCI-IDD demonstration dashboard &middot; Generated __GENDATE__ &middot; Simulated data</div>
  <div>&copy; CC-BY Dr. Zia U. Ahmed &middot;
    <a href="https://github.com/zia207" target="_blank" rel="noopener">GitHub</a> &middot;
    <a href="https://www.linkedin.com/in/zia-ahmed207" target="_blank" rel="noopener">LinkedIn</a></div>
</div></footer>

<script>
const DATA = __DATA__;
const FONT = {family:"Public Sans, sans-serif", color:"#14202E"};
const PAL = {navy:"#1C3A5E", teal:"#0F7C8C", tealB:"#17A2B8", amber:"#E0952A",
             good:"#2E8B6F", mid:"#E0952A", low:"#C6553F", grid:"#E7EDF3"};
const CFG = {displayModeBar:false, responsive:true};
const baseLayout = () => ({
  font:FONT, margin:{l:10,r:16,t:10,b:36}, paper_bgcolor:"rgba(0,0,0,0)",
  plot_bgcolor:"rgba(0,0,0,0)", xaxis:{gridcolor:PAL.grid, zeroline:false},
  yaxis:{gridcolor:PAL.grid, zeroline:false}, hoverlabel:{font:{family:"Public Sans"}}
});
const band = v => v>=75?PAL.good : v>=50?PAL.mid : PAL.low;
let region = "Statewide";

/* ---- KPI helpers ---- */
function kpiCard(label,val,sub,cls){
  return `<div class="kpi ${cls||''}"><div class="label">${label}</div>
    <div class="val">${val}</div><div class="sub">${sub||''}</div></div>`;
}
function scopeTag(n){ return region==="Statewide" ? `Statewide &middot; n = ${n.toLocaleString()}`
    : `${region} &middot; n = ${n.toLocaleString()}`; }

/* ---- Renderers (filterable by region) ---- */
function renderKPIsOverview(){
  const k=DATA.kpi, ips=DATA.ips[region], fam=DATA.family[region], wf=DATA.workforce[region];
  document.getElementById("scope-ov").innerHTML =
    region==="Statewide"?"Simulated 2025–26 reporting cycle":region;
  document.getElementById("kpis-ov").innerHTML =
    kpiCard("In-Person respondents", ips.n.toLocaleString(), `${DATA.responseRates.ips}% response rate`)
    + kpiCard("Family respondents", fam.n.toLocaleString(), `${DATA.responseRates.family}% response rate`,"alt")
    + kpiCard("Community employment", ips.emp_has+"%", "have a community job", ips.emp_has>=18?"good":"")
    + kpiCard("DSP turnover", wf.turnover+"%", "annual, DSP-weighted", wf.turnover<=40?"good":"alt")
    + kpiCard("Case-mgmt satisfaction", ips.domains.case_mgmt_satisfied+"%", "IPS respondents", "good")
    + kpiCard("DSPs represented", wf.n_dsp.toLocaleString(), `${wf.n_agencies} agencies`);
}
function renderScorecard(){
  const d=DATA.ips[region].domains, L=DATA.ipsDomainLabels;
  const rows=Object.keys(L).map(k=>({name:L[k],v:d[k]})).sort((a,b)=>b.v-a.v);
  document.getElementById("scorecard").innerHTML = rows.map(r=>`
    <div class="sc-item"><div class="name">${r.name}</div>
      <div class="sc-track"><div class="sc-fill" style="width:${r.v}%;background:${band(r.v)}"></div></div>
      <div class="num" style="color:${band(r.v)}">${r.v}%</div></div>`).join("");
}
function renderResidence(){
  const r=DATA.ips[region].residence;
  const labels=Object.keys(r), vals=labels.map(k=>r[k]);
  Plotly.react("c-residence",[{type:"pie",labels,values:vals,hole:.55,sort:true,
    marker:{colors:[PAL.navy,PAL.teal,PAL.tealB,PAL.amber,"#8AA6BE","#B9C6D4"]},
    textinfo:"label+percent",textposition:"outside",
    hovertemplate:"%{label}: %{value}%<extra></extra>"}],
    {...baseLayout(),showlegend:false,margin:{l:10,r:10,t:10,b:10}},CFG);
}
function renderIPS(){
  const ips=DATA.ips[region];
  document.getElementById("scope-ips").innerHTML=scopeTag(ips.n);
  document.getElementById("kpis-ips").innerHTML =
    kpiCard("Chose where they live", ips.domains.choice_where_lives+"%","","good")
    + kpiCard("Community participation", ips.domains.community_participation+"%","as much as wanted","alt")
    + kpiCard("Has a community job", ips.emp_has+"%","")
    + kpiCard("Wants a job (not working)", ips.emp_wants+"%","unmet employment interest","alt")
    + kpiCard("Feels safe at home", ips.domains.safety_feels_safe_home+"%","","good")
    + kpiCard("Uses self-direction", ips.domains.self_direction_uses+"%","");
  const L=DATA.ipsDomainLabels, d=ips.domains;
  const rows=Object.keys(L).map(k=>({n:L[k],v:d[k]})).sort((a,b)=>a.v-b.v);
  Plotly.react("c-ips-domains",[{type:"bar",orientation:"h",
    x:rows.map(r=>r.v), y:rows.map(r=>r.n),
    marker:{color:rows.map(r=>band(r.v))},
    text:rows.map(r=>r.v+"%"),textposition:"auto",
    hovertemplate:"%{y}: %{x}%<extra></extra>"}],
    {...baseLayout(),margin:{l:230,r:20,t:6,b:30},xaxis:{range:[0,100],ticksuffix:"%",gridcolor:PAL.grid}},CFG);
  const hk=[["health_has_pcp","Has PCP"],["health_dental_pastyear","Dental (past yr)"],
    ["health_screenings_current","Screenings current"],["safety_feels_safe_home","Feels safe home"],
    ["safety_knows_who_to_tell","Knows who to tell"],["rights_privacy_respected","Privacy respected"]];
  Plotly.react("c-ips-health",[{type:"bar",
    x:hk.map(h=>d[h[0]]), y:hk.map(h=>h[1]),orientation:"h",
    marker:{color:PAL.teal}, text:hk.map(h=>d[h[0]]+"%"),textposition:"auto",
    hovertemplate:"%{y}: %{x}%<extra></extra>"}],
    {...baseLayout(),margin:{l:150,r:20,t:6,b:30},xaxis:{range:[0,100],ticksuffix:"%",gridcolor:PAL.grid}},CFG);
}
function renderFamily(){
  const fam=DATA.family[region];
  document.getElementById("scope-fam").innerHTML=scopeTag(fam.n);
  const ind=fam.indicators;
  document.getElementById("kpis-fam").innerHTML =
    kpiCard("Satisfied with services", ind.satisfied_with_services+"%","","good")
    + kpiCard("Involved in planning", ind.involved_in_service_planning+"%","","good")
    + kpiCard("Gets needed information", ind.gets_needed_information+"%","","alt")
    + kpiCard("Adequate respite access", ind.respite_access_adequate+"%","common gap","alt")
    + kpiCard("Services meet needs", ind.services_meet_needs+"%","")
    + kpiCard("Would recommend", ind.would_recommend_services+"%","","good");
  const types=Object.keys(DATA.familyByType), L=DATA.famIndicatorLabels, keys=Object.keys(L);
  const colors=[PAL.navy,PAL.teal,PAL.amber];
  Plotly.react("c-fam-type", types.map((t,i)=>({type:"bar",name:t,
    x:keys.map(k=>DATA.familyByType[t][k]), y:keys.map(k=>L[k]),orientation:"h",
    marker:{color:colors[i]}, hovertemplate:t+"<br>%{y}: %{x}%<extra></extra>"})),
    {...baseLayout(),barmode:"group",margin:{l:230,r:14,t:6,b:30},
     legend:{orientation:"h",y:1.08,font:{size:11}},xaxis:{range:[0,100],ticksuffix:"%",gridcolor:PAL.grid}},CFG);
  const rows=keys.map(k=>({n:L[k],v:ind[k]})).sort((a,b)=>a.v-b.v);
  Plotly.react("c-fam-ind",[{type:"bar",orientation:"h",
    x:rows.map(r=>r.v),y:rows.map(r=>r.n),marker:{color:rows.map(r=>band(r.v))},
    text:rows.map(r=>r.v+"%"),textposition:"auto",hovertemplate:"%{y}: %{x}%<extra></extra>"}],
    {...baseLayout(),margin:{l:230,r:20,t:6,b:30},xaxis:{range:[0,100],ticksuffix:"%",gridcolor:PAL.grid}},CFG);
}
function renderFamilyStatic(){
  const R=DATA.regions, v=R.map(r=>DATA.respiteByRegion[r]);
  Plotly.react("c-fam-respite",[{type:"bar",x:R,y:v,marker:{color:v.map(x=>band(x))},
    text:v.map(x=>x+"%"),textposition:"outside",hovertemplate:"%{x}: %{y}%<extra></extra>"}],
    {...baseLayout(),margin:{l:40,r:14,t:16,b:70},yaxis:{range:[0,80],ticksuffix:"%",gridcolor:PAL.grid},
     xaxis:{tickangle:-35}},CFG);
}
function renderWorkforce(){
  const wf=DATA.workforce[region];
  document.getElementById("scope-wf").innerHTML =
    (region==="Statewide"?"Statewide":region)+` &middot; ${wf.n_agencies} agencies &middot; ${wf.n_dsp.toLocaleString()} DSPs`;
  document.getElementById("kpis-wf").innerHTML =
    kpiCard("DSP turnover", wf.turnover+"%","annual, DSP-weighted", wf.turnover<=40?"good":"alt")
    + kpiCard("Vacancy rate", wf.vacancy+"%","")
    + kpiCard("Avg hourly wage", "$"+wf.wage.toFixed(2),`start $${wf.start_wage.toFixed(2)}`)
    + kpiCard("Avg tenure", wf.tenure+" mo","")
    + kpiCard("Overtime reliance", wf.overtime+"%","of hours","alt")
    + kpiCard("Offer health insurance", wf.health+"%","of agencies","good");
  // benefits
  Plotly.react("c-wf-benefits",[{type:"bar",
    x:["Health insurance","Retirement plan","Paid time off","Sign-on bonus"],
    y:[wf.health,wf.retirement,wf.pto,wf.signon],
    marker:{color:[PAL.teal,PAL.tealB,PAL.good,PAL.amber]},
    text:[wf.health,wf.retirement,wf.pto,wf.signon].map(x=>x+"%"),textposition:"outside",
    hovertemplate:"%{x}: %{y}%<extra></extra>"}],
    {...baseLayout(),margin:{l:40,r:14,t:16,b:40},yaxis:{range:[0,100],ticksuffix:"%",gridcolor:PAL.grid}},CFG);
  // scatter (filter agencies by region)
  const ag=region==="Statewide"?DATA.agencies:DATA.agencies.filter(a=>a.region===region);
  const sizes={"Small (<50 DSPs)":PAL.tealB,"Medium (50-199)":PAL.navy,"Large (200+)":PAL.amber};
  const traces=Object.keys(sizes).map(s=>{
    const pts=ag.filter(a=>a.size===s);
    return {type:"scatter",mode:"markers",name:s,
      x:pts.map(a=>a.wage),y:pts.map(a=>a.turnover),
      marker:{color:sizes[s],size:pts.map(a=>Math.max(6,Math.sqrt(a.dsp))),opacity:.7,
        line:{color:"#fff",width:.5}},
      text:pts.map(a=>a.region+" · "+a.dsp+" DSPs"),
      hovertemplate:"%{text}<br>$%{x:.2f}/hr · %{y}% turnover<extra></extra>"};
  });
  Plotly.react("c-wf-scatter",traces,{...baseLayout(),margin:{l:46,r:14,t:6,b:44},
    legend:{orientation:"h",y:1.12,font:{size:11}},
    xaxis:{title:{text:"Avg hourly wage ($)",font:{size:12}},gridcolor:PAL.grid,tickprefix:"$"},
    yaxis:{title:{text:"Turnover (%)",font:{size:12}},gridcolor:PAL.grid,ticksuffix:"%"}},CFG);
}
function renderWorkforceStatic(){
  const R=DATA.regions, v=R.map(r=>DATA.turnoverByRegion[r]);
  const avg=DATA.workforce["Statewide"].turnover;
  Plotly.react("c-wf-turnover",[{type:"bar",x:R,y:v,marker:{color:v.map(x=>x>avg?PAL.low:PAL.teal)},
    text:v.map(x=>x+"%"),textposition:"outside",hovertemplate:"%{x}: %{y}%<extra></extra>"}],
    {...baseLayout(),margin:{l:40,r:14,t:16,b:70},yaxis:{range:[0,Math.max(...v)*1.15],ticksuffix:"%",gridcolor:PAL.grid},
     xaxis:{tickangle:-35},
     shapes:[{type:"line",x0:-.5,x1:R.length-.5,y0:avg,y1:avg,line:{color:PAL.ink,width:1.5,dash:"dash"}}],
     annotations:[{x:R.length-1,y:avg,text:`Statewide ${avg}%`,showarrow:false,yshift:12,
       font:{size:11,color:PAL.ink},xanchor:"right"}]},CFG);
}
function renderCountsStatic(){
  const R=DATA.regions;
  Plotly.react("c-counts",[
    {type:"bar",name:"In-Person",x:R,y:R.map(r=>DATA.counts.ips[r]),marker:{color:PAL.navy}},
    {type:"bar",name:"Family",x:R,y:R.map(r=>DATA.counts.family[r]),marker:{color:PAL.teal}}],
    {...baseLayout(),barmode:"group",margin:{l:40,r:14,t:10,b:70},
     legend:{orientation:"h",y:1.12},xaxis:{tickangle:-35},yaxis:{gridcolor:PAL.grid}},CFG);
}

/* ---- Interactive workforce map (filled polygons; fully offline) ---- */
let mapMetric="turnover";
const G=[46,139,111], A=[224,149,42], R_=[198,85,63];
const SCALE_LOW_GOOD=[[0,"rgb(46,139,111)"],[0.5,"rgb(224,149,42)"],[1,"rgb(198,85,63)"]];
const SCALE_HIGH_GOOD=[[0,"rgb(198,85,63)"],[0.5,"rgb(224,149,42)"],[1,"rgb(46,139,111)"]];
function lerp(a,b,t){return "rgb("+Math.round(a[0]+(b[0]-a[0])*t)+","+
  Math.round(a[1]+(b[1]-a[1])*t)+","+Math.round(a[2]+(b[2]-a[2])*t)+")";}
function colorFor(v,min,max,betterLow){
  let t=(max>min)?(v-min)/(max-min):0.5; t=Math.max(0,Math.min(1,t));
  const stops=betterLow?[G,A,R_]:[R_,A,G];
  return t<0.5?lerp(stops[0],stops[1],t/0.5):lerp(stops[1],stops[2],(t-0.5)/0.5);
}
function renderWorkforceMap(){
  const m=DATA.mapMetrics[mapMetric], R=DATA.regions;
  const vals=R.map(r=>m.vals[r]);
  const cmin=Math.min(...vals), cmax=Math.max(...vals);
  const pre=m.prefix||"", suf=m.suffix||"", betterLow=(m.better==="low");
  const fills=R.map(r=>{
    const s=DATA.mapShapes[r], v=m.vals[r];
    return {type:"scatter",mode:"lines",x:s.x,y:s.y,fill:"toself",
      fillcolor:colorFor(v,cmin,cmax,betterLow),line:{color:"#ffffff",width:1.2},
      hoveron:"fills",name:r,text:"<b>"+r+"</b><br>"+m.label+": "+pre+v+suf,
      hoverinfo:"text",hoverlabel:{bgcolor:"#14202E",bordercolor:"#14202E",font:{color:"#fff",family:"Public Sans"}}};
  });
  // centroid trace: carries the colorbar + region labels
  const cx=R.map(r=>DATA.mapShapes[r].cx), cy=R.map(r=>DATA.mapShapes[r].cy);
  const cbar={type:"scatter",mode:"markers",x:cx,y:cy,hoverinfo:"skip",showlegend:false,
    marker:{size:0.1,color:vals,colorscale:(betterLow?SCALE_LOW_GOOD:SCALE_HIGH_GOOD),
      cmin,cmax,showscale:true,colorbar:{title:{text:m.label,side:"right",font:{size:12,family:"Public Sans"}},
      thickness:12,len:.9,x:1,tickprefix:pre,ticksuffix:suf,tickfont:{size:11}}}};
  Plotly.react("c-wf-map",[...fills,cbar],{
    ...baseLayout(),showlegend:false,margin:{l:0,r:0,t:0,b:0},
    xaxis:{visible:false,fixedrange:true},
    yaxis:{visible:false,fixedrange:true,scaleanchor:"x",scaleratio:1}
  },CFG);
}
function buildMapToggle(){
  const t=document.getElementById("map-toggle");
  Object.entries(DATA.mapMetrics).forEach(([k,m])=>{
    const b=document.createElement("button");
    b.textContent=m.label; b.dataset.k=k;
    if(k===mapMetric)b.classList.add("active");
    b.addEventListener("click",()=>{
      mapMetric=k;
      t.querySelectorAll("button").forEach(x=>x.classList.remove("active"));
      b.classList.add("active"); renderWorkforceMap();
    });
    t.appendChild(b);
  });
}

/* ---- Orchestration ---- */
function renderFilterable(){
  renderKPIsOverview(); renderScorecard(); renderResidence();
  renderIPS(); renderFamily(); renderWorkforce();
}
function renderStatic(){
  renderCountsStatic(); renderFamilyStatic(); renderWorkforceStatic();
  renderWorkforceMap();
  document.getElementById("m-ips-rr").textContent=DATA.responseRates.ips+"%";
  document.getElementById("m-fam-rr").textContent=DATA.responseRates.family+"%";
  document.getElementById("m-wf-rr").textContent=DATA.responseRates.workforce+"%";
}

// Region selector
const sel=document.getElementById("region");
["Statewide",...DATA.regions].forEach(r=>{
  const o=document.createElement("option");o.value=r;o.textContent=r;sel.appendChild(o);});
sel.addEventListener("change",e=>{region=e.target.value;renderFilterable();});
buildMapToggle();

// Tabs
document.querySelectorAll("nav.tabs button").forEach(b=>{
  b.addEventListener("click",()=>{
    document.querySelectorAll("nav.tabs button").forEach(x=>x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(x=>x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById(b.dataset.tab).classList.add("active");
    window.dispatchEvent(new Event("resize")); // force Plotly to size hidden charts
  });
});

renderStatic();
renderFilterable();
if (typeof Plotly === "undefined") {
  document.querySelector("main").insertAdjacentHTML("afterbegin",
    '<div style="background:#FBE7D2;border:1px solid #EBC98F;color:#7A4E12;padding:14px 16px;border-radius:10px;margin-bottom:18px;font-weight:600">The chart library did not load. If you opened this file offline, use the self-contained version, or reconnect to the internet and reload.</div>');
}
window.addEventListener("resize",()=>{ /* Plotly responsive handles it */ });
</script>
</body>
</html>
"""

html = (TEMPLATE
        .replace("__PLOTLY_JS__", plotly_tag)
        .replace("__DATA__", json.dumps(DATA))
        .replace("__GENDATE__", gendate))
with open("nci_idd_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"Wrote nci_idd_dashboard.html ({len(html):,} bytes)")
