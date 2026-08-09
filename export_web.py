"""
Permian Basin Analytics — Exportador web (para GitHub Pages)
Lee data/processed/permian.csv y escribe docs/data.js, que el index.html
del dashboard consume del lado del cliente (sin servidor).

Uso:
  python etl.py          # genera el CSV
  python export_web.py   # genera docs/data.js
  # subir la carpeta docs/ al repo y activar GitHub Pages (branch main, /docs)
"""
import json
from pathlib import Path
import pandas as pd

SRC = Path("data/processed/permian.csv")
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "data.js"

# Columnas que el dashboard usa (si alguna falta, se exporta lo que haya)
COLS = [
    "period", "crude_oil_prod", "tight_oil_prod", "shale_gas_prod",
    "gas_marketed_prod", "active_rigs", "new_wells_drilled", "new_wells_completed",
    "ducs", "newwell_oil_prod", "existing_oil_change", "net_oil_change",
    "completion_ratio",
]


def main():
    if not SRC.exists():
        raise SystemExit(f"No existe {SRC}. Corré etl.py primero.")
    df = pd.read_csv(SRC, parse_dates=["period"]).sort_values("period")
    keep = [c for c in COLS if c in df.columns]
    df = df[keep]
    df["period"] = df["period"].dt.strftime("%Y-%m-%d")

    # último mes histórico = último período con rigs (la actividad no se pronostica)
    updated = None
    if "active_rigs" in df.columns and df["active_rigs"].notna().any():
        updated = df.loc[df["active_rigs"].notna(), "period"].max()

    rows = [{k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in df.to_dict(orient="records")]

    payload = {"updated": updated, "rows": rows}
    OUT.write_text("window.PERMIAN = " + json.dumps(payload) + ";", encoding="utf-8")
    print(f"OK — {len(rows)} filas -> {OUT}  (último histórico: {updated})")


if __name__ == "__main__":
    main()
