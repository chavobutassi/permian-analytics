# Permian Basin Production Analytics

**Automated analytics on U.S. shale oil & gas production, built on public U.S. Energy Information Administration (EIA) data.**

🔴 **Live dashboard:** https://chavobutassi.github.io/permian-analytics/
📦 **Repository:** https://github.com/chavobutassi/permian-analytics
👤 **Author:** Claudio Julián Butassi — Data & Business Intelligence Analyst

---

## Why this matters for the United States

Energy independence and the resilience of critical infrastructure are national priorities for the United States. The Permian Basin, spanning West Texas and New Mexico, is the single most important contributor to that goal: its shale and tight formations produce roughly **6 million barrels of crude oil per day — about 44% of total U.S. crude output** (EIA Short-Term Energy Outlook).

Faster, more transparent, and reproducible production analytics support better decisions on resource allocation, transport capacity, and supply continuity — benefits that extend well beyond any single operator. This project demonstrates that capability end to end: it ingests official production data, models basin dynamics, and publishes an automatically refreshed dashboard, using the same public datasets that operators, regulators, and analysts rely on.

## What it does

- **Crude & tight oil production** trends for the Permian, with the EIA forecast horizon clearly marked.
- **Efficiency analysis** — production against active rig count, showing how the basin grows output with fewer rigs.
- **New wells vs. base decline** — the central shale dynamic: new-well additions offsetting the natural decline of existing wells, with the resulting net change.
- **Drilled-but-uncompleted (DUC) inventory** alongside drilling and completion pace.

## Data source

All data comes from the **EIA Short-Term Energy Outlook (STEO)**, accessed programmatically through the [EIA API v2](https://www.eia.gov/opendata/) — no manual downloads. Fifteen Permian series are used, including crude oil production (`COPRPM`), tight oil and shale gas by formation (`TOPRPM`, `SNGPRPM`), active rigs (`RIGSPM`), DUC inventory (`DUCSPM`), and new-well / existing-well production changes (`CONWPM`, `COEOPPM`).

## Methodology & scope

- Data is **monthly, at basin/region granularity**. Values beyond the latest actual month are **EIA forecasts** (shaded in the dashboard).
- Units: crude and tight oil in **million bbl/day**; new-well and base-change series in **thousand bbl/day**; gas in **Bcf/day**.
- A note on scope: at basin granularity, well-level **decline-curve modeling (Arps), water cut, and gas-oil ratio are not available** — those require well-level data (Texas Railroad Commission / New Mexico OCD) and are planned for a v2. At this level, base decline is represented in aggregate via the existing-well production-change series.
- "Permian by formation" (~6.0 Mbbl/d) and "geographic Permian region" (~6.6 Mbbl/d) are distinct EIA series; this project is consistent about which it uses.

## How it works

```
explore_eia.py   →  discovers the Permian series available in the EIA API
etl.py           →  extracts the 15 series (with caching) → data/processed/permian.csv
analysis.py      →  KPIs + charts (PNG) for quick inspection
export_web.py    →  writes docs/data.js for the dashboard
docs/index.html  →  self-contained Plotly dashboard (GitHub Pages)
```

## Run it yourself

```bash
# 1. Get a free EIA API key at https://www.eia.gov/opendata/
# 2. Create a .env file with:  EIA_API_KEY=your_key
# 3. Install dependencies
pip install requests pandas numpy matplotlib python-dotenv pyarrow

# 4. Run the pipeline
python etl.py          # download data
python analysis.py     # KPIs + charts
python export_web.py   # build dashboard data
# open docs/index.html (or serve docs/ with: python -m http.server)
```

The `.env` file holds the API key and is excluded from version control via `.gitignore`.

## Roadmap

- **v2 — well-level analytics:** integrate Texas RRC and New Mexico OCD data for true per-well decline curves, water cut, and GOR.
- **Automation:** weekly refresh via GitHub Actions (CI/CD) to keep the dashboard current with no manual steps.

## Tech stack

Python (pandas, requests) · EIA API v2 · Plotly · GitHub Pages

---

## Resumen (Español)

Proyecto de analítica automatizada sobre la producción de petróleo y gas de la cuenca **Permian** (EE.UU.), construido sobre datos públicos de la **U.S. Energy Information Administration (EIA)**. Toma los datos directo de la API (sin descargas manuales), modela producción, actividad de perforación y la dinámica de pozos nuevos vs. declinación de base, y publica un **dashboard actualizado** en GitHub Pages.

**Dashboard en vivo:** https://chavobutassi.github.io/permian-analytics/

**Cómo correrlo:** conseguir una API key gratis en eia.gov/opendata, ponerla en un archivo `.env`, instalar dependencias (`pip install requests pandas numpy matplotlib python-dotenv pyarrow`) y correr en orden `etl.py` → `analysis.py` → `export_web.py`, y abrir `docs/index.html`.

**Alcance:** los datos del STEO son mensuales y a nivel cuenca; las curvas de declinación por pozo, el water cut y el GOR necesitan datos por pozo (Texas RRC / Nuevo México OCD) y quedan para la v2.
