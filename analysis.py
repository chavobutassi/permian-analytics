"""
Permian Basin Analytics — Analisis (Fase 3)
Corre sobre data/processed/permian.csv (salida de etl.py).

Novedades de esta version:
  - Separa HISTORICO de FORECAST (los datos del STEO llegan hasta 2027).
  - Petroleo (crude_oil_prod) como protagonista.
  - Grafico "pozos nuevos vs. declinacion de base" (net_oil_change).
  - Usa DUCs reales (serie DUCSPM).

Uso:
  1. python etl.py   (genera data/processed/permian.csv)
  2. pip install pandas numpy matplotlib
  3. python analysis.py

NOTA de dominio: a nivel cuenca (STEO) no hay curvas de declinacion por pozo
(Arps). La declinacion aparece agregada como existing_oil_change (caida de la
base) y se compensa con newwell_oil_prod. El analisis por pozo va a la v2
(Texas RRC / New Mexico OCD).
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = Path("data/processed/permian.csv")
CHARTS = Path("charts")
CHARTS.mkdir(exist_ok=True)

plt.rcParams.update({"figure.figsize": (10, 5), "axes.grid": True,
                     "grid.alpha": 0.3, "font.size": 11})
NAVY, AMBER, TEAL, RED = "#1f3a5f", "#b45309", "#0d7d7d", "#b3261e"


def load() -> pd.DataFrame:
    if not DATA.exists():
        raise SystemExit(f"No existe {DATA}. Correr etl.py primero.")
    return pd.read_csv(DATA, parse_dates=["period"]).sort_values("period").reset_index(drop=True)


def split_hist_forecast(df: pd.DataFrame):
    """El ultimo mes historico = ultimo periodo donde active_rigs tiene dato
    (las series de actividad no se pronostican; produccion si)."""
    if "active_rigs" in df.columns and df["active_rigs"].notna().any():
        last_hist = df.loc[df["active_rigs"].notna(), "period"].max()
    else:
        last_hist = df["period"].max()
    hist = df[df["period"] <= last_hist].copy()
    fcst = df[df["period"] > last_hist].copy()
    return hist, fcst, last_hist


def yoy(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 13:
        return float("nan")
    return (s.iloc[-1] / s.iloc[-13] - 1) * 100


def kpis(hist: pd.DataFrame, last_hist) -> None:
    print("=" * 64)
    print("KPIs — ultimo mes HISTORICO:", pd.Timestamp(last_hist).strftime("%Y-%m"))
    print("=" * 64)
    labels = {
        "crude_oil_prod": "Crude oil (Mbbl/d)",
        "tight_oil_prod": "Tight oil (Mbbl/d)",
        "shale_gas_prod": "Shale gas (Bcf/d)",
        "active_rigs": "Rigs activos",
        "new_wells_drilled": "Pozos perforados/mes",
        "new_wells_completed": "Pozos completados/mes",
        "ducs": "DUCs (inventario real)",
        "newwell_oil_prod": "Prod. petroleo pozos nuevos (kbbl/d)",
        "existing_oil_change": "Cambio base petroleo (kbbl/d)",
        "net_oil_change": "Neto: nuevos + base (kbbl/d)",
    }
    for col, label in labels.items():
        if col in hist.columns and hist[col].notna().any():
            last = hist[col].dropna().iloc[-1]
            chg = yoy(hist[col])
            chg_s = f"{chg:+.1f}% i/a" if pd.notna(chg) else "s/d"
            print(f"  {label:<38} {last:>10,.1f}   ({chg_s})")


def _shade_forecast(ax, last_hist, df):
    """Sombrea la zona de pronostico."""
    if df["period"].max() > last_hist:
        ax.axvspan(last_hist, df["period"].max(), color="grey", alpha=0.08)
        ax.axvline(last_hist, color="grey", ls="--", lw=1)


def chart_oil(df, last_hist):
    if "crude_oil_prod" not in df.columns:
        return
    fig, ax = plt.subplots()
    ax.plot(df["period"], df["crude_oil_prod"], color=NAVY, lw=2.2, label="Crude oil (Mbbl/d)")
    if "tight_oil_prod" in df:
        ax.plot(df["period"], df["tight_oil_prod"], color=TEAL, lw=1.3, ls="--", label="Tight oil (Mbbl/d)")
    _shade_forecast(ax, last_hist, df)
    ax.set_ylabel("Millones bbl/dia"); ax.legend(loc="upper left")
    ax.set_title("Permian — Produccion de petroleo (zona gris = pronostico)")
    fig.tight_layout(); fig.savefig(CHARTS / "01_petroleo.png", dpi=120); plt.close(fig)


def chart_efficiency(df, last_hist):
    if "active_rigs" not in df.columns:
        return
    fig, ax1 = plt.subplots()
    ax1.plot(df["period"], df["active_rigs"], color=NAVY, lw=2, label="Rigs activos")
    ax1.set_ylabel("Rigs activos", color=NAVY)
    if "crude_oil_prod" in df:
        ax2 = ax1.twinx()
        ax2.plot(df["period"], df["crude_oil_prod"], color=AMBER, lw=2, label="Crude oil")
        ax2.set_ylabel("Crude oil (Mbbl/d)", color=AMBER)
    _shade_forecast(ax1, last_hist, df)
    ax1.set_title("Permian — Mas produccion con menos rigs (eficiencia)")
    fig.tight_layout(); fig.savefig(CHARTS / "02_eficiencia.png", dpi=120); plt.close(fig)


def chart_decline(df, last_hist):
    """La historia central del shale: pozos nuevos vs. caida de la base."""
    if not {"newwell_oil_prod", "existing_oil_change"} <= set(df.columns):
        return
    fig, ax = plt.subplots()
    ax.bar(df["period"], df["newwell_oil_prod"], width=20, color=TEAL, label="Pozos nuevos (+)")
    ax.bar(df["period"], df["existing_oil_change"], width=20, color=RED, label="Declinacion base (-)")
    if "net_oil_change" in df:
        ax.plot(df["period"], df["net_oil_change"], color=NAVY, lw=2, label="Neto")
    ax.axhline(0, color="black", lw=0.8)
    _shade_forecast(ax, last_hist, df)
    ax.set_ylabel("Miles bbl/dia"); ax.legend(loc="upper left")
    ax.set_title("Permian — Pozos nuevos vs. declinacion de la base (petroleo)")
    fig.tight_layout(); fig.savefig(CHARTS / "03_declinacion.png", dpi=120); plt.close(fig)


def chart_ducs(df, last_hist):
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
    _shade_forecast(ax1, last_hist, df)
    ax1.set_title("Permian — Inventario de DUCs y ritmo de perforacion/completacion")
    fig.tight_layout(); fig.savefig(CHARTS / "04_ducs.png", dpi=120); plt.close(fig)


def main():
    df = load()
    hist, fcst, last_hist = split_hist_forecast(df)
    print(f"Cargadas {len(df)} filas — historico hasta {pd.Timestamp(last_hist):%Y-%m}, "
          f"forecast {len(fcst)} meses.\n")
    kpis(hist, last_hist)
    chart_oil(df, last_hist)
    chart_efficiency(df, last_hist)
    chart_decline(df, last_hist)
    chart_ducs(df, last_hist)
    print("\nGraficos en charts/: 01_petroleo, 02_eficiencia, 03_declinacion, 04_ducs.")


if __name__ == "__main__":
    main()
