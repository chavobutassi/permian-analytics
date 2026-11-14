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
import re
from pathlib import Path
import pandas as pd

SRC = Path("data/processed/permian.csv")
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "data.js"

# Columnas que el dashboard usa (si alguna falta, se exporta lo que haya)
COLS = [
    "period", "crude_oil_prod", "us_crude_prod", "tight_oil_prod", "shale_gas_prod",
    "gas_marketed_prod", "active_rigs", "new_wells_drilled", "new_wells_completed",
    "ducs", "newwell_oil_prod", "existing_oil_change", "net_oil_change",
    "completion_ratio", "wti",
]

README = Path("README.md")


def _permian_share(df, updated):
    """Permian crude ÷ U.S. crude en el último mes real, como % entero.

    Devuelve (share_pct, crude_latest) o (None, None) si no se puede calcular
    o si el ratio cae fuera de un rango sensato (guarda contra cambios de unidad).
    """
    if not updated or not {"crude_oil_prod", "us_crude_prod"} <= set(df.columns):
        return None, None
    row = df.loc[df["period"] == updated]
    if row.empty:
        return None, None
    c, u = row["crude_oil_prod"].iloc[0], row["us_crude_prod"].iloc[0]
    if pd.isna(c) or pd.isna(u) or not u:
        return None, None
    r = c / u
    if not (0.2 <= r <= 0.8):        # ambas series en M bbl/d → ~0.49; si no, algo cambió
        return None, None
    return round(r * 100), round(float(c), 1)


def _actualizar_readme(share_pct, crude_latest):
    """Reescribe el número entre marcadores del README, sin tocar nada más."""
    if share_pct is None or not README.exists():
        return
    txt = README.read_text(encoding="utf-8")
    txt = re.sub(r"(<!--SHARE_PCT-->).*?(<!--/SHARE_PCT-->)",
                 rf"\g<1>{share_pct}\g<2>", txt)
    if crude_latest is not None:
        txt = re.sub(r"(<!--CRUDE-->).*?(<!--/CRUDE-->)",
                     rf"\g<1>{crude_latest}\g<2>", txt)
    README.write_text(txt, encoding="utf-8")


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

    share_pct, crude_latest = _permian_share(df, updated)

    rows = [{k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in df.to_dict(orient="records")]

    payload = {"updated": updated, "share_pct": share_pct,
               "crude_latest": crude_latest, "rows": rows}
    OUT.write_text("window.PERMIAN = " + json.dumps(payload) + ";", encoding="utf-8")
    _actualizar_readme(share_pct, crude_latest)
    print(f"OK — {len(rows)} filas -> {OUT}  (último histórico: {updated}; "
          f"Permian ≈ {share_pct}% de EE.UU.)")


if __name__ == "__main__":
    main()
