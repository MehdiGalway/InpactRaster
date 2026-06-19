# Ireland GHG Policy Impact Explorer — Django + Vercel

A minimal Django platform that serves the INPACT / Ireland Greenhouse Gas
Policy Impact Explorer single-page app. Built to deploy on Vercel's
zero-configuration Django runtime.

## Project layout

```
inpact-explorer/
├── manage.py
├── requirements.txt
├── .gitignore
├── data/
│   ├── ghg_inventory.csv     # ← editable emissions dataset (real EPA values)
│   └── policies.csv          # ← editable climate-policy timeline (jurisdiction, dates, detail)
├── inpact_platform/          # Django project (settings, urls, wsgi/asgi)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py               # Vercel reads `application` from here
│   └── asgi.py
└── explorer/                 # Django app that serves the page
    ├── views.py              # reads the CSV + page/index.html, injects data
    ├── urls.py
    └── page/
        └── index.html        # the self-contained Explorer page
```

## Editing the data

All emissions values come from **`data/ghg_inventory.csv`**. Edit that file and
reload the page in the browser — the time-series chart, the indicator switcher
(Total GHG / CO₂ / CH₄ / …), the no-policy baseline, the projection band and the
headline KPIs all recompute automatically. No code change or migration needed.

The CSV is wide format: the first column is `year`, and each remaining column is
one gas series in **kt CO₂-equivalent**. Column headers must match the indicator
keys used by the page (e.g. `All greenhouse gases`, `CO2`,
`CH4 - (CO2 equivalent)`, …). A blank cell means "no data" for that year (the
chart draws a gap). Add rows to extend the timeline (e.g. a `2025` row) and the
observed window updates on its own.

The *observed* line is your CSV data. The baseline counterfactual,
policy-adjusted pathway, forecast and 95% confidence band are computed **from**
those observed values by the model in `index.html`; the map markers remain
illustrative placeholders.

## Tabbed dashboard

The platform is organised into three tabs (a bar sits directly under the
header):

* **Explorer** — the full analytical dashboard (filters sidebar, emissions
  chart, map, policy intelligence, roadmap, climate-targets cards). Unchanged
  from before, just wrapped in its own tab.
* **About INPACT** — a content page describing the project (mission, what we do,
  why it matters, data sources, the full team, and a closing statement). The
  copy mirrors the project's *About INPACT* document.
* **Feedback** — a public-participation form whose submissions are written to an
  Excel workbook (see below).

## Feedback → Excel on GitHub

Submissions from the **Feedback** tab POST to `/api/feedback/`. Each one is
appended as a row to an Excel workbook (`data/feedback.xlsx`). Because Vercel's
serverless filesystem is **read-only**, the workbook is persisted by committing
it back to the GitHub repository through the GitHub Contents API — so the repo
itself is the durable store and the `.xlsx` can be downloaded straight from
GitHub at `data/feedback.xlsx`.

Behaviour is controlled by environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `GITHUB_TOKEN` | PAT with `contents: write` on the repo. **If unset, feedback is written to local disk instead** (handy for local dev). | _(none)_ |
| `GITHUB_REPO` | `owner/name` to commit into. | `MehdiGalway/INPACT_V2` |
| `GITHUB_BRANCH` | Branch to commit to. | `main` |
| `FEEDBACK_PATH` | Path of the workbook inside the repo. | `data/feedback.xlsx` |

**Local development:** don't set `GITHUB_TOKEN`. Submit feedback and open the
generated `data/feedback.xlsx` directly.

**Production (Vercel):** create a fine-grained Personal Access Token scoped to
this repo with **Contents: Read and write**, then add it as the `GITHUB_TOKEN`
environment variable in your Vercel project settings. Submissions will then be
committed to `data/feedback.xlsx` in the repo automatically.

Two routes back the feature:

* `POST /api/feedback/` — record a submission (JSON or form-encoded).
* `GET  /api/feedback/download/` — download the current workbook as
  `inpact_feedback.xlsx` (pulls from GitHub when a token is set, else local
  disk). There is also a **Download .xlsx** button on the Feedback tab.

> ⚠️ Never commit your `GITHUB_TOKEN`. Keep it in environment variables only.

### Policy timeline — `data/policies.csv`

The climate-policy layer comes from **`data/policies.csv`**; edit it and reload.
Columns: `year, name, level, agency, sector, type, instrument, description,
direction, outcome`.

* **`level`** is one of `International`, `EU`, `National` or `Target`, and drives
  the colour everywhere (navy / teal / emerald / amber) plus the sidebar
  **Policy Interventions** checkboxes. Ticking a jurisdiction shows that group's
  dashed guide-lines on the chart, each annotated with a vertical (rotated)
  label; years with several policies show the lead one plus a `+N` badge. The
  `Target` rows (2030 / 2050) are always shown in amber.
* The same records build the **Climate Policy Roadmap** timeline and populate the
  **Policy Intelligence Panel** (direction, lead body, instrument, outcome,
  description) when a node is clicked — so one CSV feeds the whole page.
* Add, remove or re-date rows freely; counts, timeline and chart update on reload.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000

## Deploy on Vercel

Vercel auto-detects `manage.py`, reads `WSGI_APPLICATION` from settings, and
runs `collectstatic` automatically. No `vercel.json` is required.

In your Vercel project settings add an environment variable:

- `SECRET_KEY` — any long random string (used by Django).

Then connect the GitHub repo and deploy. See the full walkthrough you were
given alongside this project.

## Raster overlays — Spatial Environmental Mapping

The map panel (tab **Explorer → 2B**) can overlay raster (`.tif`) layers on the
Leaflet map, driven by three **cascading dropdowns**: Year → Sector → Parameter.

### Where the files live and how they're named

Drop GeoTIFFs into **`data/Raster/`** using the convention:

```
<Year>_<Sector>_<Parameter>.tif
```

e.g. `2019_B_Industry_pbenzoA.tif` → Year `2019`, Sector `B_Industry`,
Parameter `pbenzoA`. The Year is the first token, the Parameter is the last
token, and the Sector is everything in between (so a sector may itself contain
an underscore, like `B_Industry`).

The folder is **re-scanned on every request**, so new files appear in the
dropdowns automatically — no code change or server restart needed. Files that
don't match the convention are ignored.

### What the overlay does

* Reprojects the raster (any CRS, e.g. Irish Grid EPSG:29902) to Web-Mercator so
  it lines up with the basemap.
* Applies a **rainbow** colour map on a **logarithmic** scale (these emission
  rasters span several orders of magnitude), with robust 2nd/98th-percentile
  endpoints.
* **Masks zero and nodata cells** — they are fully transparent and never drawn.
* Draws a matching **colour-bar legend** (bottom-left of the map) with the value
  range.
* Selecting a new Year/Sector/Parameter **replaces** the previous overlay.
* An all-zero raster is detected and reported instead of drawing a blank layer.

### Endpoints

| Route | Purpose |
|-------|---------|
| `GET /api/rasters/` | Nested catalogue `{year:{sector:{parameter:filename}}}` for the dropdowns |
| `GET /api/raster/meta/?year=&sector=&parameter=` | Bounds (WGS84), value range, colour stops, scale, all-zero flag |
| `GET /api/raster/image/?year=&sector=&parameter=` | The rendered RGBA PNG (rainbow, zeros transparent) |

Rendering lives in `explorer/rasters.py`; the endpoints are in
`explorer/views.py`; the dropdowns, overlay logic and legend are in
`explorer/page/index.html`.

### Extra dependencies

`rasterio`, `numpy` and `Pillow` (added to `requirements.txt`). `rasterio`
ships self-contained binary wheels (bundled GDAL) on PyPI, so a plain
`pip install -r requirements.txt` is enough for local development. For Vercel,
note that GDAL-backed wheels are large; if the serverless bundle exceeds limits,
pre-render the PNGs or host the raster API separately.
