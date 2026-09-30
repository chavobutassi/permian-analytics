"""
Permian Analytics v2 — ETL de pozos (FracFocus)
===============================================
Toma permian_wells.csv (salida de explore_fracfocus.py: ~157k pozos reales de
la Permian con coordenadas, operadora, condado y fecha) y genera un paquete
web compacto para el dashboard v2 — sin mandar 157k filas al navegador.

Salida
------
  wells_web.js       window.PERMIAN_WELLS = { kpis, top_operators, by_year,
                     by_county, grid }  (compacto: la grilla representa TODOS
                     los pozos por densidad, no una muestra).
  wells_summary.json Mismo contenido, para inspección/trazabilidad.

Uso
---
  # con permian_wells.csv en la misma carpeta que este script:
  pip install pandas
  python etl_v2.py
"""

from __future__ import annotations
import json, logging
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

AQUI = Path(__file__).resolve().parent
ENTRADA = AQUI / "permian_wells.csv"

# Caja geográfica de la Permian: descarta coordenadas basura (0,0 o fuera de región)
BBOX = dict(lat_min=28.0, lat_max=36.0, lon_min=-106.5, lon_max=-99.5)
GRID = 0.05          # tamaño de celda en grados (~5.5 km) para la densidad
ANIO_MIN = 2010      # FracFocus arranca ~2011; años previos son errores de carga

def cargar() -> pd.DataFrame:
    if not ENTRADA.exists():
        raise SystemExit(f"No existe {ENTRADA}. Corré explore_fracfocus.py primero.")
    df = pd.read_csv(ENTRADA, low_memory=False)
    log.info("Cargados %s pozos de %s", f"{len(df):,}", ENTRADA.name)
    return df

def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    antes = len(df)
    df = df[
        df["lat"].between(BBOX["lat_min"], BBOX["lat_max"]) &
        df["lon"].between(BBOX["lon_min"], BBOX["lon_max"])
    ].copy()
    log.info("Coordenadas válidas dentro de la Permian: %s (descartadas %s)",
             f"{len(df):,}", f"{antes-len(df):,}")
    if "fecha" in df.columns:
        df["anio"] = pd.to_datetime(df["fecha"], errors="coerce").dt.year
    return df

def construir_payload(df: pd.DataFrame) -> dict:
    # Top operadoras
    top = (df["operator"].fillna("(sin dato)").value_counts().head(12)
           .rename_axis("operator").reset_index(name="wells"))
    # Pozos por año (solo años plausibles)
    by_year = []
    if "anio" in df.columns:
        yv = df[df["anio"].between(ANIO_MIN, datetime.now().year)]["anio"].value_counts().sort_index()
        by_year = [{"year": int(y), "wells": int(n)} for y, n in yv.items()]
    # Pozos por condado
    by_county = (df.groupby(["state", "county"]).size().sort_values(ascending=False)
                 .head(15).reset_index(name="wells"))
    by_county["state"] = by_county["state"].str.title()
    # Grilla de densidad (representa TODOS los pozos, no una muestra)
    g = df.copy()
    g["glat"] = (g["lat"] / GRID).round() * GRID
    g["glon"] = (g["lon"] / GRID).round() * GRID
    grid = (g.groupby(["glat", "glon"]).size().reset_index(name="n"))
    grid = [{"lat": round(float(r.glat), 3), "lon": round(float(r.glon), 3), "n": int(r.n)}
            for r in grid.itertuples()]

    payload = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": "FracFocus — registro de fracturas (pozos con coordenadas reales)",
        "kpis": {
            "total_wells": int(len(df)),
            "operators": int(df["operator"].nunique()),
            "counties": int(df.groupby(["state", "county"]).ngroups),
            "first_year": int(df["anio"].dropna()[df["anio"] >= ANIO_MIN].min()) if "anio" in df.columns and df["anio"].notna().any() else None,
            "last_year": int(df["anio"].dropna().max()) if "anio" in df.columns and df["anio"].notna().any() else None,
        },
        "center": {"lat": round(float(df["lat"].median()), 3), "lon": round(float(df["lon"].median()), 3)},
        "top_operators": top.to_dict(orient="records"),
        "by_year": by_year,
        "by_county": by_county.to_dict(orient="records"),
        "grid": grid,
    }
    return payload

def guardar(payload: dict) -> None:
    (AQUI / "wells_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (AQUI / "wells_web.js").write_text("window.PERMIAN_WELLS = " + json.dumps(payload) + ";", encoding="utf-8")
    kb = (AQUI / "wells_web.js").stat().st_size / 1024
    log.info("Guardado wells_web.js (%.0f KB) y wells_summary.json", kb)
    log.info("  celdas de grilla: %d  |  operadoras top: %d  |  años: %d",
             len(payload["grid"]), len(payload["top_operators"]), len(payload["by_year"]))

def main() -> None:
    df = cargar()
    df = limpiar(df)
    payload = construir_payload(df)
    k = payload["kpis"]
    log.info("KPIs — pozos: %s | operadoras: %s | condados: %s | %s–%s",
             f"{k['total_wells']:,}", k["operators"], k["counties"], k["first_year"], k["last_year"])
    guardar(payload)

if __name__ == "__main__":
    main()