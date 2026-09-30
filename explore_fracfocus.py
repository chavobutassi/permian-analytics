"""
Permian Analytics v2 — Exploración de FracFocus
===============================================
Primer paso de la v2: qué pozos de la Permian hay en FracFocus
(coordenadas reales, operadora, condado, fecha de fractura).

CÓMO USARLO (simple):
  1. Bajá el CSV masivo de FracFocus (ZIP) de https://fracfocus.org/data-download
     ("Oil and Gas Data" → CSV) y descomprimilo.
  2. Poné este script EN LA MISMA CARPETA que esos .csv.
  3. pip install pandas
  4. python explore_fracfocus.py
     (o pasále la carpeta:  python explore_fracfocus.py "C:\\ruta\\a\\los\\csv")
"""

from __future__ import annotations
import sys, glob, logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

AQUI = Path(__file__).resolve().parent
# Dónde buscar los CSV: 1) lo que pases por línea de comando, 2) al lado del script,
# 3) subcarpeta fracfocus junto al script, 4) data/raw/fracfocus desde donde corras.
CANDIDATAS = ([Path(sys.argv[1])] if len(sys.argv) > 1 else []) + [
    AQUI, AQUI / "fracfocus", Path.cwd() / "data" / "raw" / "fracfocus", Path.cwd(),
]

PERMIAN_TX = {"ANDREWS","BORDEN","CRANE","CROCKETT","CULBERSON","DAWSON","ECTOR","GAINES",
    "GLASSCOCK","HOWARD","IRION","LOVING","MARTIN","MIDLAND","PECOS","REAGAN","REEVES",
    "STERLING","UPTON","WARD","WINKLER","YOAKUM","TERRY","HOCKLEY"}
PERMIAN_NM = {"LEA","EDDY"}

ALIAS = {
    "operator": ["OperatorName","operator_name","Operator"],
    "well":     ["WellName","well_name","WellNameNo"],
    "api":      ["APINumber","api_number","API10","APINo"],
    "state":    ["StateName","state_name","State"],
    "county":   ["CountyName","county_name","County"],
    "lat":      ["Latitude","latitude","SurfaceLatitude"],
    "lon":      ["Longitude","longitude","SurfaceLongitude"],
    "fecha":    ["JobStartDate","job_start_date","JobEndDate","DateInserted"],
}

def _mapa_columnas(cols):
    ren = {}
    for canon, posibles in ALIAS.items():
        for c in posibles:
            if c in cols:
                ren[c] = canon; break
    return ren

def _buscar_csv():
    for carpeta in CANDIDATAS:
        try:
            arch = [a for a in glob.glob(str(carpeta / "*.csv"))]
        except Exception:
            arch = []
        if arch:
            log.info("Usando CSV de: %s", carpeta)
            return arch
    log.error("No encontré ningún .csv de FracFocus. Busqué en:")
    for c in CANDIDATAS: log.error("   - %s", c)
    log.error("Descargá y descomprimí FracFocus, y poné los .csv en una de esas carpetas.")
    sys.exit(1)

def _filtrar_permian(df):
    df = df.rename(columns=_mapa_columnas(df.columns))
    if not {"state","county","lat","operator"} <= set(df.columns):
        return None
    df["state"]  = df["state"].astype(str).str.strip().str.lower()
    df["county"] = df["county"].astype(str).str.strip().str.upper()
    return df[
        ((df["state"] == "texas")      & (df["county"].isin(PERMIAN_TX))) |
        ((df["state"] == "new mexico") & (df["county"].isin(PERMIAN_NM)))
    ].copy()

def main():
    archivos = _buscar_csv()
    log.info("Leyendo %d archivo(s) por bloques (para no llenar la memoria)…", len(archivos))
    trozos = []
    for a in archivos:
        try:
            for chunk in pd.read_csv(a, low_memory=False, chunksize=200_000, on_bad_lines="skip"):
                permian = _filtrar_permian(chunk)
                if permian is not None and len(permian):
                    trozos.append(permian)
        except Exception as e:
            log.warning("  no pude leer %s (%s)", Path(a).name, e)
    if not trozos:
        log.error("Leí los CSV pero no encontré pozos de la Permian (revisá columnas/condados).")
        sys.exit(1)

    permian = pd.concat(trozos, ignore_index=True)
    pozos = permian.drop_duplicates(subset="api") if "api" in permian.columns \
            else permian.drop_duplicates(subset=["lat","lon","well"])

    log.info("=" * 60)
    log.info("Registros Permian: %s  |  pozos únicos: %s", f"{len(permian):,}", f"{len(pozos):,}")
    if "fecha" in pozos.columns:
        f = pd.to_datetime(pozos["fecha"], errors="coerce").dropna()
        if len(f): log.info("Rango de fechas: %s → %s", f.min().date(), f.max().date())
    log.info("Cobertura de coordenadas: %.1f %%", 100*pd.to_numeric(pozos["lat"], errors="coerce").notna().mean())

    log.info("\nTop 15 operadoras (por pozos):")
    for op, n in pozos["operator"].value_counts().head(15).items():
        log.info("  %-45s %5d", str(op)[:45], n)
    log.info("\nPozos por estado/condado (top 10):")
    for (st, co), n in pozos.groupby(["state","county"]).size().sort_values(ascending=False).head(10).items():
        log.info("  %-12s %-12s %6d", st, co, n)

    salida = AQUI / "permian_wells.csv"
    cols = [c for c in ["api","operator","well","state","county","lat","lon","fecha"] if c in pozos.columns]
    pozos[cols].to_csv(salida, index=False)
    log.info("\nGuardado: %s  (%d pozos)", salida, len(pozos))

if __name__ == "__main__":
    main()