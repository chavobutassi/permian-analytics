"""
Permian Basin Analytics — Análisis
==================================
Gemelo US-facing de Vaca Muerta Analytics, con la misma arquitectura.
Corre sobre data/processed/permian.csv (salida de etl.py) y produce KPIs
por consola, un resumen en JSON y cuatro figuras en charts/.

Flujo
-----
    cargar()                       Lee el tablero procesado.
    separar_historico_pronostico() Divide dato real vs. pronóstico del STEO.
    kpis()                         Métricas del último mes real (+ variación i/a).
    graf_*()                       Cuatro lecturas del sistema (ver más abajo).
    guardar_kpis()                 Persiste charts/_kpis.json (trazabilidad).

Salida
------
    charts/01_petroleo.png      Producción de petróleo (crudo + tight).
    charts/02_eficiencia.png    Rigs vs. producción (la historia de eficiencia).
    charts/03_declinacion.png   Pozos nuevos (+) vs. declinación de base (−).
    charts/04_ducs.png          Inventario de DUCs y ritmo perforación/completación.
    charts/_kpis.json           KPIs del último mes real.

Nota de dominio
---------------
A nivel cuenca (STEO) NO hay curvas de declinación por pozo (Arps): la
declinación aparece agregada en `existing_oil_change` (caída de la base),
compensada por `newwell_oil_prod`. El análisis por pozo (Arps, water cut,
GOR) es la v2, con datos de Texas RRC / New Mexico OCD.

Uso
---
    python etl.py                          # genera data/processed/permian.csv
    pip install pandas numpy matplotlib
    python analysis.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA   = Path("data/processed/permian.csv")
CHARTS = Path("charts")

plt.rcParams.update({
    "figure.figsize": (10, 5), "axes.grid": True,
    "grid.alpha": 0.3, "font.size": 11,
})

# Paleta de marca (coherente con el dashboard: petróleo ámbar, gas/datos petróleo, base rojo)
NAVY, AMBER, TEAL, RED = "#1f3a5f", "#b45309", "#0d7d7d", "#b3261e"

# KPIs a reportar: columna → (etiqueta, decimales)
KPIS: dict[str, tuple[str, int]] = {
    "crude_oil_prod":      ("Crude oil (M bbl/d)", 2),
    "tight_oil_prod":      ("Tight oil (M bbl/d)", 2),
    "shale_gas_prod":      ("Shale gas (Bcf/d)", 1),
    "active_rigs":         ("Rigs activos", 0),
    "new_wells_drilled":   ("Pozos perforados/mes", 0),
    "new_wells_completed": ("Pozos completados/mes", 0),
    "ducs":                ("DUCs (inventario real)", 0),
    "newwell_oil_prod":    ("Prod. petróleo pozos nuevos (k bbl/d)", 0),
    "existing_oil_change": ("Cambio de base petróleo (k bbl/d)", 0),
    "net_oil_change":      ("Neto: nuevos + base (k bbl/d)", 0),
}

# ─── CARGA Y PREPARACIÓN ─────────────────────────────────────────────────────

def cargar() -> pd.DataFrame:
    """Lee el tablero procesado y lo devuelve ordenado por período."""
    if not DATA.exists():
        raise SystemExit(f"No existe {DATA}. Corré etl.py primero.")
    df = pd.read_csv(DATA, parse_dates=["period"]).sort_values("period").reset_index(drop=True)
    log.info("Cargadas %d filas (%s → %s)", len(df),
             df["period"].min().strftime("%Y-%m"),
             df["period"].max().strftime("%Y-%m"))
    return df


def separar_historico_pronostico(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Divide el tablero en (histórico, pronóstico, último_mes_real).

    El último mes real es el último con rigs cargados: la actividad de
    perforación no se pronostica, pero la producción del STEO sí.
    """
    if "active_rigs" in df.columns and df["active_rigs"].notna().any():
        ultimo_real = df.loc[df["active_rigs"].notna(), "period"].max()
    else:
        ultimo_real = df["period"].max()
    hist = df[df["period"] <= ultimo_real].copy()
    fcst = df[df["period"] > ultimo_real].copy()
    return hist, fcst, ultimo_real


def _yoy(serie: pd.Series) -> float:
    """Variación interanual (12 meses) del último dato disponible."""
    s = serie.dropna()
    if len(s) < 13:
        return float("nan")
    return (s.iloc[-1] / s.iloc[-13] - 1) * 100

# ─── KPIs ────────────────────────────────────────────────────────────────────

def kpis(hist: pd.DataFrame, ultimo_real: pd.Timestamp) -> dict:
    """Registra y devuelve los KPIs del último mes real, con variación i/a."""
    log.info("KPIs — último mes real: %s", ultimo_real.strftime("%Y-%m"))
    resumen: dict[str, dict] = {}
    for col, (label, dec) in KPIS.items():
        if col in hist.columns and hist[col].notna().any():
            valor = float(hist[col].dropna().iloc[-1])
            chg = _yoy(hist[col])
            chg_txt = f"{chg:+.1f}% i/a" if pd.notna(chg) else "s/d"
            log.info("  %-40s %12.1f   (%s)", label, valor, chg_txt)
            resumen[col] = {"label": label, "valor": round(valor, dec),
                            "yoy_pct": None if pd.isna(chg) else round(chg, 1)}
    return resumen

# ─── GRÁFICOS ────────────────────────────────────────────────────────────────

def _sombrear_pronostico(ax, ultimo_real: pd.Timestamp, df: pd.DataFrame) -> None:
    """Sombrea la franja de pronóstico (posterior al último mes real)."""
    if df["period"].max() > ultimo_real:
        ax.axvspan(ultimo_real, df["period"].max(), color="grey", alpha=0.08)
        ax.axvline(ultimo_real, color="grey", ls="--", lw=1)


def graf_petroleo(df: pd.DataFrame, ultimo_real: pd.Timestamp) -> None:
    """Producción de crudo y tight oil de la cuenca."""
    if "crude_oil_prod" not in df.columns:
        return
    fig, ax = plt.subplots()
    ax.plot(df["period"], df["crude_oil_prod"], color=NAVY, lw=2.2, label="Crude oil (M bbl/d)")
    if "tight_oil_prod" in df.columns:
        ax.plot(df["period"], df["tight_oil_prod"], color=TEAL, lw=1.3, ls="--", label="Tight oil (M bbl/d)")
    _sombrear_pronostico(ax, ultimo_real, df)
    ax.set_ylabel("Millones bbl/día"); ax.legend(loc="upper left")
    ax.set_title("Permian — Producción de petróleo (zona gris = pronóstico)")
    fig.tight_layout(); fig.savefig(CHARTS / "01_petroleo.png", dpi=120); plt.close(fig)


def graf_eficiencia(df: pd.DataFrame, ultimo_real: pd.Timestamp) -> None:
    """Rigs vs. producción: más barriles con menos equipos."""
    if "active_rigs" not in df.columns:
        return
    fig, ax1 = plt.subplots()
    ax1.plot(df["period"], df["active_rigs"], color=NAVY, lw=2, label="Rigs activos")
    ax1.set_ylabel("Rigs activos", color=NAVY)
    if "crude_oil_prod" in df.columns:
        ax2 = ax1.twinx()
        ax2.plot(df["period"], df["crude_oil_prod"], color=AMBER, lw=2, label="Crude oil")
        ax2.set_ylabel("Crude oil (M bbl/d)", color=AMBER)
    _sombrear_pronostico(ax1, ultimo_real, df)
    ax1.set_title("Permian — Más producción con menos rigs (eficiencia)")
    fig.tight_layout(); fig.savefig(CHARTS / "02_eficiencia.png", dpi=120); plt.close(fig)


def graf_declinacion(df: pd.DataFrame, ultimo_real: pd.Timestamp) -> None:
    """La historia central del shale: pozos nuevos (+) vs. caída de la base (−)."""
    if not {"newwell_oil_prod", "existing_oil_change"} <= set(df.columns):
        return
    fig, ax = plt.subplots()
    ax.bar(df["period"], df["newwell_oil_prod"], width=20, color=TEAL, label="Pozos nuevos (+)")
    ax.bar(df["period"], df["existing_oil_change"], width=20, color=RED, label="Declinación base (−)")
    if "net_oil_change" in df.columns:
        ax.plot(df["period"], df["net_oil_change"], color=NAVY, lw=2, label="Neto")
    ax.axhline(0, color="black", lw=0.8)
    _sombrear_pronostico(ax, ultimo_real, df)
    ax.set_ylabel("Miles bbl/día"); ax.legend(loc="upper left")
    ax.set_title("Permian — Pozos nuevos vs. declinación de la base (petróleo)")
    fig.tight_layout(); fig.savefig(CHARTS / "03_declinacion.png", dpi=120); plt.close(fig)


def graf_ducs(df: pd.DataFrame, ultimo_real: pd.Timestamp) -> None:
    """Inventario de DUCs junto al ritmo de perforación y completación."""
    if "ducs" not in df.columns:
        return
    fig, ax1 = plt.subplots()
    ax1.plot(df["period"], df["ducs"], color=TEAL, lw=2, label="DUCs (inventario)")
    ax1.set_ylabel("DUCs", color=TEAL)
    if {"new_wells_drilled", "new_wells_completed"} <= set(df.columns):
        ax2 = ax1.twinx()
        ax2.plot(df["period"], df["new_wells_drilled"], color=NAVY, lw=1.2, label="Perforados")
        ax2.plot(df["period"], df["new_wells_completed"], color=AMBER, lw=1.2, label="Completados")
        ax2.set_ylabel("Pozos/mes")
    _sombrear_pronostico(ax1, ultimo_real, df)
    ax1.set_title("Permian — Inventario de DUCs y ritmo de perforación/completación")
    fig.tight_layout(); fig.savefig(CHARTS / "04_ducs.png", dpi=120); plt.close(fig)

# ─── PERSISTENCIA ────────────────────────────────────────────────────────────

def guardar_kpis(resumen: dict, ultimo_real: pd.Timestamp) -> None:
    """Escribe charts/_kpis.json con los KPIs del último mes real (trazabilidad)."""
    payload = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ultimo_mes_real": ultimo_real.strftime("%Y-%m"),
        "kpis": resumen,
    }
    (CHARTS / "_kpis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("  + charts/_kpis.json")

# ─── ORQUESTACIÓN ────────────────────────────────────────────────────────────

def main() -> None:
    CHARTS.mkdir(exist_ok=True)
    df = cargar()
    hist, fcst, ultimo_real = separar_historico_pronostico(df)
    log.info("Histórico hasta %s; %d meses de pronóstico.",
             ultimo_real.strftime("%Y-%m"), len(fcst))

    resumen = kpis(hist, ultimo_real)

    graf_petroleo(df, ultimo_real)
    graf_eficiencia(df, ultimo_real)
    graf_declinacion(df, ultimo_real)
    graf_ducs(df, ultimo_real)
    guardar_kpis(resumen, ultimo_real)

    log.info("Listo. Figuras en charts/: 01_petroleo, 02_eficiencia, 03_declinacion, 04_ducs.")


if __name__ == "__main__":
    main()
