"""
Fase 1 — Exploración de la API de la EIA (ruta STEO).

Qué hace:
  1. Lista las facetas disponibles de la ruta `steo` (para confirmar la estructura).
  2. Baja el catálogo completo de series del STEO.
  3. Filtra las que mencionan "Permian" y las imprime (id + nombre + unidad).

Uso:
  1. pip install requests python-dotenv
  2. Conseguí tu API key gratis en https://www.eia.gov/opendata/
  3. Creá un archivo .env al lado de este script con:
        EIA_API_KEY=tu_clave_aca
  4. python explore_eia.py
  5. Pasame la salida (la lista de series Permian) y escribo el ETL.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("EIA_API_KEY")
if not API_KEY:
    sys.exit("Falta EIA_API_KEY. Crealo en un archivo .env (ver instrucciones arriba).")

BASE = "https://api.eia.gov/v2"


def get(path, params=None):
    params = dict(params or {})
    params["api_key"] = API_KEY
    r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    # 1) Metadata de la ruta steo: qué facetas y frecuencias tiene
    print("=" * 70)
    print("METADATA DE LA RUTA /steo")
    print("=" * 70)
    meta = get("steo").get("response", {})
    facets = [f.get("id") for f in meta.get("facets", [])]
    freqs = [f.get("id") for f in meta.get("frequency", [])]
    print("Facetas disponibles :", facets)
    print("Frecuencias         :", freqs)
    print("Rango de fechas      :", meta.get("startPeriod"), "->", meta.get("endPeriod"))

    # 2) Catálogo de series (la faceta suele llamarse 'seriesId')
    facet_name = "seriesId" if "seriesId" in facets else (facets[0] if facets else None)
    if not facet_name:
        sys.exit("No se encontraron facetas en la ruta steo; revisar la respuesta cruda.")

    print("\n" + "=" * 70)
    print(f"BUSCANDO SERIES DE LA PERMIAN EN LA FACETA '{facet_name}'")
    print("=" * 70)
    catalog = get(f"steo/facet/{facet_name}").get("response", {})
    items = catalog.get("facets", catalog.get("data", []))

    permian = []
    for it in items:
        name = (it.get("name") or it.get("description") or "").strip()
        sid = it.get("id") or it.get(facet_name)
        if "permian" in name.lower():
            permian.append((sid, name))

    if not permian:
        print("No aparecieron series con 'Permian' en el nombre.")
        print("Muestro las primeras 20 series para inspeccionar el patrón de nombres:")
        for it in items[:20]:
            print("  ", it.get("id"), "-", it.get("name"))
        return

    print(f"\nEncontradas {len(permian)} series de la Permian:\n")
    for sid, name in sorted(permian):
        print(f"  {sid:<20}  {name}")

    print("\nListo. Copiá esta lista y pasámela para escribir el ETL.")


if __name__ == "__main__":
    main()
