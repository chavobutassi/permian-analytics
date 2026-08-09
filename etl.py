"""
Permian Basin Analytics — ETL (Fase 2)
Fuente: EIA API v2, ruta STEO (Short-Term Energy Outlook).

Flujo: Extract (API + cache) -> Transform (tidy + derivadas) -> Load (parquet/csv).

Uso:
  1. pip install requests pandas python-dotenv pyarrow
  2. .env con:  EIA_API_KEY=tu_clave
  3. rm -rf data/raw data/processed   (para forzar rebajar todo)
  4. python etl.py
  Salida: data/processed/permian.csv  y  data/processed/permian.parquet
"""

import os
import json
import sys
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
if not API_KEY:
    sys.exit("Falta EIA_API_KEY en .env")

BASE = "https://api.eia.gov/v2"
RAW = Path("data/raw")
PROC = Path("data/processed")
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)

# --- Series confirmadas de la Permian (EIA STEO) ---
# clave = seriesId EIA ; valor = nombre corto y legible para las columnas
SERIES = {
    # Producción — petróleo
    "COPRPM":  "crude_oil_prod",       # Crude oil production, región Permian (headline)
    "TOPRPM":  "tight_oil_prod",       # Tight oil (formaciones)
    # Producción — gas
    "SNGPRPM": "shale_gas_prod",       # Shale gas production (formaciones)
    "NGMPPM":  "gas_marketed_prod",    # Natural gas marketed production (región)
    # Actividad de perforación
    "RIGSPM":  "active_rigs",
    "NWDPM":   "new_wells_drilled",
    "NWCPM":   "new_wells_completed",
    "NWRPM":   "wells_drilled_per_rig",
    "DUCSPM":  "ducs",                 # DUCs reales (ya no proxy)
    # Productividad y declinación de base — petróleo
    "CONWPM":  "newwell_oil_prod",     # Prod. de petróleo de pozos nuevos (tendencia 1 anio)
    "CONWRPM": "newwell_oil_per_rig",  # ... por rig
    "COEOPPM": "existing_oil_change",  # Cambio de prod. de pozos existentes (declinacion base)
    # Productividad y declinación de base — gas
    "NGNWPM":  "newwell_gas_prod",
    "NGNWRPM": "newwell_gas_per_rig",
    "NGEOPPM": "existing_gas_change",  # Cambio de prod. de pozos existentes (gas)
}

START = "2014-01"  # el shale de la Permian despega ~2014; ajustable


def fetch_series(series_id: str) -> pd.DataFrame:
    """Trae una serie mensual del STEO, con cache local en data/raw/."""
    cache = RAW / f"{series_id}.json"
    if cache.exists():
        payload = json.loads(cache.read_text())
    else:
        params = {
            "api_key": API_KEY,
            "frequency": "monthly",
            "data[0]": "value",
            "facets[seriesId][]": series_id,
            "start": START,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": 5000,
        }
        r = requests.get(f"{BASE}/steo/data/", params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        cache.write_text(json.dumps(payload))

    rows = payload.get("response", {}).get("data", [])
    if not rows:
        print(f"  [aviso] {series_id}: sin datos")
        return pd.DataFrame(columns=["period", SERIES[series_id]])

    df = pd.DataFrame(rows)
    unit = df["unit"].iloc[0] if "unit" in df else "?"
    print(f"  {series_id:<9} {SERIES[series_id]:<22} {len(df):>4} filas  [{unit}]")
    df = df[["period", "value"]].rename(columns={"value": SERIES[series_id]})
    df[SERIES[series_id]] = pd.to_numeric(df[SERIES[series_id]], errors="coerce")
    return df


def extract() -> pd.DataFrame:
    print("EXTRACT — bajando series del STEO Permian:")
    merged = None
    for sid in SERIES:
        df = fetch_series(sid)
        merged = df if merged is None else merged.merge(df, on="period", how="outer")
    return merged.sort_values("period").reset_index(drop=True)


def transform(df: pd.DataFrame) -> pd.DataFrame:
    print("TRANSFORM — calculando metricas derivadas:")
    df["period"] = pd.PeriodIndex(df["period"], freq="M").to_timestamp()

    # DUCs: ahora viene la serie real DUCSPM; ya no calculamos proxy.
    if "ducs" in df.columns:
        print("  + DUCs reales (serie DUCSPM)")

    # Ratio de completacion: que porcion de lo perforado se completa.
    if {"new_wells_completed", "new_wells_drilled"} <= set(df.columns):
        df["completion_ratio"] = (
            df["new_wells_completed"] / df["new_wells_drilled"]
        ).round(3)
        print("  + completion_ratio")

    # Produccion neta de pozos nuevos menos declinacion de la base (petroleo).
    # Si el neto es positivo, los pozos nuevos ganan a la caida de los viejos.
    if {"newwell_oil_prod", "existing_oil_change"} <= set(df.columns):
        df["net_oil_change"] = df["newwell_oil_prod"] + df["existing_oil_change"]
        print("  + net_oil_change (pozos nuevos + cambio base)")

    return df


def load(df: pd.DataFrame) -> None:
    csv_path = PROC / "permian.csv"
    pq_path = PROC / "permian.parquet"
    df.to_csv(csv_path, index=False)
    try:
        df.to_parquet(pq_path, index=False)
    except Exception as e:
        print(f"  [aviso] no se pudo escribir parquet ({e}); queda el CSV")
    print(f"LOAD — {len(df)} filas -> {csv_path}")


def main():
    df = extract()
    df = transform(df)
    load(df)
    print("\nListo. Ultimas filas:")
    cols = [c for c in ["period", "crude_oil_prod", "active_rigs", "ducs"] if c in df.columns]
    print(df[cols].tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
