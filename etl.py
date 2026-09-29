"""
Permian Basin Analytics — ETL
==============================
Gemelo US-facing de Vaca Muerta Analytics, con la misma arquitectura.

Fuente
------
U.S. Energy Information Administration (EIA), API v2, ruta STEO
(Short-Term Energy Outlook). Serie mensual, nivel cuenca/región; los
valores posteriores al último mes real son PRONÓSTICO de la EIA.

Flujo
-----
    extraer()      Descarga las series del STEO (con caché local en data/raw/).
    transformar()  Normaliza el período y calcula métricas derivadas.
    validar()      Control de calidad por serie (cobertura, nulos, rango).
    guardar()      Persiste el tablero ancho + metadata reproducible.

Salida
------
    data/processed/permian.csv       Tablero ancho (lo consume export_web.py).
    data/processed/permian.parquet   Mismo tablero, columnar.
    data/processed/_metadata.json    Trazabilidad de la corrida.

Uso
---
    pip install requests pandas python-dotenv pyarrow tqdm
    echo "EIA_API_KEY=tu_clave" > .env          # clave gratuita: eia.gov/opendata
    python etl.py                                # (borrá data/raw para forzar rebaja)
"""

from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import pandas as pd
from dotenv import load_dotenv

try:                                   # barra de progreso opcional (como Vaca Muerta)
    from tqdm import tqdm
except ImportError:                    # pragma: no cover
    def tqdm(it, **_):                 # type: ignore
        return it

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv()

BASE = "https://api.eia.gov/v2"        # EIA API v2
RUTA = "steo/data"                     # Short-Term Energy Outlook
START = "2014-01"                      # el shale de la Permian despega ~2014

CARPETA_CACHE  = Path("data/raw")
CARPETA_OUTPUT = Path("data/processed")

# ─── SERIES DE LA PERMIAN (EIA STEO) ─────────────────────────────────────────
# clave = seriesId de la EIA ; valor = nombre de columna legible.
SERIES: dict[str, str] = {
    # Producción — petróleo
    "COPRPM":  "crude_oil_prod",       # Crude Oil Production: Permian (región, headline)
    "TOPRPM":  "tight_oil_prod",       # Tight oil (formaciones Permian)
    # Producción — gas
    "SNGPRPM": "shale_gas_prod",       # Shale natural gas (formaciones Permian)
    "NGMPPM":  "gas_marketed_prod",    # Natural gas marketed production (región)
    # Actividad de perforación
    "RIGSPM":  "active_rigs",          # Equipos de perforación activos
    "NWDPM":   "new_wells_drilled",    # Pozos nuevos perforados / mes
    "NWCPM":   "new_wells_completed",  # Pozos nuevos completados / mes
    "NWRPM":   "wells_drilled_per_rig",# Pozos perforados por rig
    "DUCSPM":  "ducs",                 # Drilled but Uncompleted Wells (inventario real)
    # Productividad y declinación de base — petróleo
    "CONWPM":  "newwell_oil_prod",     # Producción de petróleo de pozos nuevos
    "CONWRPM": "newwell_oil_per_rig",  # ... por rig
    "COEOPPM": "existing_oil_change",  # Cambio de producción de pozos existentes (base)
    # Productividad y declinación de base — gas
    "NGNWPM":  "newwell_gas_prod",     # Producción de gas de pozos nuevos
    "NGNWRPM": "newwell_gas_per_rig",  # ... por rig
    "NGEOPPM": "existing_gas_change",  # Cambio de producción de pozos existentes (gas)
    # Precio de referencia (serie NACIONAL del STEO, no exclusiva de la Permian)
    "WTIPUUS": "wti",                  # WTI spot average
}

# ─── UNIDADES DE REFERENCIA ──────────────────────────────────────────────────
# Fuente del dato: EIA STEO. Documentadas para no mezclar magnitudes al graficar.
#   Petróleo (cuenca)      → millones de barriles/día   (M bbl/d)
#   Pozos nuevos / base    → miles de barriles/día      (k bbl/d)
#   Gas (cuenca)           → miles de millones pie³/día  (Bcf/d)
#   Gas nuevos / base      → millones de pie³/día        (MMcf/d)
#   Rigs, pozos, DUCs      → conteos
#   WTI                    → US$/bbl
UNIDADES: dict[str, str] = {
    "crude_oil_prod": "M bbl/d", "tight_oil_prod": "M bbl/d",
    "shale_gas_prod": "Bcf/d",   "gas_marketed_prod": "Bcf/d",
    "active_rigs": "rigs", "new_wells_drilled": "pozos/mes",
    "new_wells_completed": "pozos/mes", "wells_drilled_per_rig": "pozos/rig",
    "ducs": "pozos", "newwell_oil_prod": "k bbl/d", "newwell_oil_per_rig": "k bbl/d",
    "existing_oil_change": "k bbl/d", "newwell_gas_prod": "MMcf/d",
    "newwell_gas_per_rig": "MMcf/d", "existing_gas_change": "MMcf/d",
    "wti": "US$/bbl", "completion_ratio": "ratio", "net_oil_change": "k bbl/d",
}

# ─── EXTRACCIÓN ──────────────────────────────────────────────────────────────

def _api_key() -> str:
    """Lee la clave de la EIA de forma perezosa (permite importar el módulo sin ella)."""
    key = os.getenv("EIA_API_KEY")
    if not key:
        sys.exit("Falta EIA_API_KEY en .env (clave gratuita en eia.gov/opendata).")
    return key


def _fetch_serie(series_id: str, columna: str) -> pd.DataFrame:
    """Devuelve una serie mensual del STEO como DataFrame [period, <columna>].

    Cachea la respuesta cruda en data/raw/<series_id>.json para no repegar la API.
    """
    cache = CARPETA_CACHE / f"{series_id}.json"
    if cache.exists():
        payload = json.loads(cache.read_text())
    else:
        params = {
            "api_key": _api_key(),
            "frequency": "monthly",
            "data[0]": "value",
            "facets[seriesId][]": series_id,
            "start": START,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": 5000,
        }
        r = requests.get(f"{BASE}/{RUTA}/", params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        cache.write_text(json.dumps(payload))

    filas = payload.get("response", {}).get("data", [])
    if not filas:
        log.warning("%s (%s): la API no devolvió datos", series_id, columna)
        return pd.DataFrame(columns=["period", columna])

    df = pd.DataFrame(filas)[["period", "value"]].rename(columns={"value": columna})
    df[columna] = pd.to_numeric(df[columna], errors="coerce")
    return df


def extraer() -> pd.DataFrame:
    """Descarga y une todas las series de SERIES en un tablero ancho por período."""
    log.info("EXTRACCIÓN — %d series del STEO Permian (%s → hoy)", len(SERIES), START)
    tablero: Optional[pd.DataFrame] = None
    for sid, col in tqdm(SERIES.items(), desc="Series", unit="serie"):
        df = _fetch_serie(sid, col)
        tablero = df if tablero is None else tablero.merge(df, on="period", how="outer")
    if tablero is None or tablero.empty:
        sys.exit("No se obtuvo ninguna serie; abortando.")
    return tablero.sort_values("period").reset_index(drop=True)

# ─── TRANSFORMACIÓN ──────────────────────────────────────────────────────────

def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el período a fecha y agrega las métricas derivadas del tablero."""
    log.info("TRANSFORMACIÓN — normalizando período y derivando métricas")
    df = df.copy()
    df["period"] = pd.PeriodIndex(df["period"].astype(str), freq="M").to_timestamp()

    # Ratio de completación: porción de lo perforado que efectivamente se completa.
    if {"new_wells_completed", "new_wells_drilled"} <= set(df.columns):
        df["completion_ratio"] = (
            df["new_wells_completed"] / df["new_wells_drilled"]
        ).round(3)
        log.info("  + completion_ratio")

    # Balance neto de petróleo: pozos nuevos (+) contra declinación de la base (−).
    # Positivo ⇒ los pozos nuevos superan la caída natural y la cuenca crece.
    if {"newwell_oil_prod", "existing_oil_change"} <= set(df.columns):
        df["net_oil_change"] = df["newwell_oil_prod"] + df["existing_oil_change"]
        log.info("  + net_oil_change (pozos nuevos + cambio de base)")

    return df

# ─── VALIDACIÓN / CALIDAD ────────────────────────────────────────────────────

def validar(df: pd.DataFrame) -> pd.DataFrame:
    """Control de calidad por columna: cobertura, nulos, rango. Registra avisos."""
    log.info("VALIDACIÓN — control de calidad por serie")
    filas = []
    for col in df.columns:
        if col == "period":
            continue
        s = df[col]
        no_nulos = int(s.notna().sum())
        cobertura = round(100 * no_nulos / len(df), 1) if len(df) else 0.0
        filas.append({
            "columna": col,
            "unidad": UNIDADES.get(col, "?"),
            "filas": no_nulos,
            "cobertura_pct": cobertura,
            "nulos": int(s.isna().sum()),
            "min": None if s.dropna().empty else round(float(s.min()), 3),
            "max": None if s.dropna().empty else round(float(s.max()), 3),
        })
        if cobertura < 50:
            log.warning("  cobertura baja en %s: %.1f %%", col, cobertura)
    calidad = pd.DataFrame(filas)
    faltantes = [s for s, c in SERIES.items() if c not in df.columns]
    if faltantes:
        log.warning("  series ausentes en el tablero: %s", ", ".join(faltantes))
    return calidad

# ─── PERSISTENCIA ────────────────────────────────────────────────────────────

def _ultimo_mes_real(df: pd.DataFrame) -> Optional[str]:
    """Último período con rigs cargados: la actividad no se pronostica, la producción sí."""
    if "active_rigs" in df.columns and df["active_rigs"].notna().any():
        return df.loc[df["active_rigs"].notna(), "period"].max().strftime("%Y-%m")
    return None


def generar_metadata(df: pd.DataFrame, calidad: pd.DataFrame) -> None:
    """Escribe _metadata.json con la trazabilidad de la corrida (fuente, rango, calidad)."""
    meta = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": "EIA API v2 — Short-Term Energy Outlook (STEO)",
        "series": len(SERIES),
        "filas": len(df),
        "periodo_min": df["period"].min().strftime("%Y-%m"),
        "periodo_max": df["period"].max().strftime("%Y-%m"),
        "ultimo_mes_real": _ultimo_mes_real(df),
        "unidades": UNIDADES,
        "calidad": calidad.to_dict(orient="records"),
    }
    (CARPETA_OUTPUT / "_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("  + _metadata.json (último mes real: %s)", meta["ultimo_mes_real"])


def guardar(df: pd.DataFrame, calidad: pd.DataFrame) -> None:
    """Persiste el tablero ancho (csv + parquet) y la metadata reproducible."""
    csv = CARPETA_OUTPUT / "permian.csv"
    df.to_csv(csv, index=False)
    try:
        df.to_parquet(CARPETA_OUTPUT / "permian.parquet", index=False)
    except Exception as e:                                   # pragma: no cover
        log.warning("no se pudo escribir parquet (%s); queda el CSV", e)
    generar_metadata(df, calidad)
    log.info("PERSISTENCIA — %d filas → %s", len(df), csv)

# ─── ORQUESTACIÓN ────────────────────────────────────────────────────────────

def main() -> None:
    CARPETA_CACHE.mkdir(parents=True, exist_ok=True)
    CARPETA_OUTPUT.mkdir(parents=True, exist_ok=True)

    df = extraer()
    df = transformar(df)
    calidad = validar(df)
    guardar(df, calidad)

    cols = [c for c in ["period", "crude_oil_prod", "active_rigs", "ducs"] if c in df.columns]
    log.info("Listo. Últimas filas:\n%s", df[cols].tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
