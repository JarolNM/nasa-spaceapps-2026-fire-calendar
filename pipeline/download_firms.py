# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Descarga hotspots MODIS y VIIRS S-NPP de NASA FIRMS (API 'area') para el AOI
y los agrega a grilla de 0,25 grados por semana.

Uso (desde la raiz del repo):
    pip install pandas requests
    python pipeline/download_firms.py --start 2019            # año de prueba
    python pipeline/download_firms.py --start 2000 --end 2025 # todo (reanuda si se corta)

La clave se lee de la variable FIRMS_MAP_KEY o del archivo .env (NO subirlo al repo).
Salida: data/raw/<sensor>_<anio>.csv  y  data/weekly/<sensor>_<anio>.csv
"""
import argparse
import io
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from config import WEST, SOUTH, EAST, NORTH, STEP  # AOI en pipeline/config.py

DAYS_PER_REQUEST = 5          # confirmar el maximo en la pagina de la API 'area'
SOURCES = {"modis": "MODIS_SP", "viirs": "VIIRS_SNPP_SP"}
BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def load_key():
    """Busca la clave en: variable de entorno, MAP_KEY.txt (solo la clave) o .env."""
    key = os.environ.get("FIRMS_MAP_KEY")
    txt = Path("MAP_KEY.txt")
    env = Path(".env")
    if not key and txt.exists():
        key = txt.read_text().strip()
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key or key.startswith("PEGA_AQUI"):
        sys.exit("Falta la clave: abre MAP_KEY.txt, pega tu MAP_KEY de FIRMS y guarda.")
    return key


def fetch_chunk(key, source, start):
    url = f"{BASE}/{key}/{source}/{WEST},{SOUTH},{EAST},{NORTH}/{DAYS_PER_REQUEST}/{start.isoformat()}"
    for attempt in range(4):
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and not r.text.lstrip().startswith(("Invalid", "You have")):
            return pd.read_csv(io.StringIO(r.text)) if r.text.strip() else pd.DataFrame()
        time.sleep(5 * (attempt + 1))
    print(f"  aviso: fallo {source} {start}: {r.status_code} {r.text[:80]!r}")
    return pd.DataFrame()


def download_year(key, name, source, year, out_raw):
    frames, d = [], date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        df = fetch_chunk(key, source, d)
        if len(df):
            frames.append(df)
        d += timedelta(days=DAYS_PER_REQUEST)
        time.sleep(0.3)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    df.to_csv(out_raw, index=False)
    return df


def to_weekly(df, year):
    """Agrega a celda 0,25 grados x semana (0-52). Cuenta hotspots y suma FRP."""
    if df.empty:
        return pd.DataFrame(columns=["year", "week", "row", "col", "count", "frp"])
    df = df.drop_duplicates(subset=["latitude", "longitude", "acq_date", "acq_time"])
    # Filtro de calidad: MODIS 'confidence' es numerico 0-100; VIIRS es l/n/h
    conf = df["confidence"].astype(str)
    if conf.str.isnumeric().all():
        df = df[conf.astype(int) >= 30]
    else:
        df = df[conf.str.lower().isin(["n", "h", "nominal", "high"])]
    d = pd.to_datetime(df["acq_date"])
    out = pd.DataFrame({
        "year": year,
        "week": ((d.dt.dayofyear - 1) // 7).clip(upper=52),
        "row": ((NORTH - df["latitude"]) // STEP).astype(int),
        "col": ((df["longitude"] - WEST) // STEP).astype(int),
        "frp": df["frp"],
    })
    g = out.groupby(["year", "week", "row", "col"]).agg(count=("frp", "size"), frp=("frp", "sum"))
    return g.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2019)
    ap.add_argument("--end", type=int, default=None, help="por defecto = --start")
    args = ap.parse_args()
    end = args.end or args.start
    key = load_key()
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/weekly").mkdir(parents=True, exist_ok=True)
    for year in range(args.start, end + 1):
        for name, source in SOURCES.items():
            if name == "viirs" and year < 2012:
                continue
            wk_path = Path(f"data/weekly/{name}_{year}.csv")
            if wk_path.exists():          # permite reanudar si se corta
                print(f"{name} {year}: ya existe, se omite")
                continue
            print(f"{name} {year} ...", flush=True)
            raw = download_year(key, name, source, year, f"data/raw/{name}_{year}.csv")
            wk = to_weekly(raw, year)
            wk.to_csv(wk_path, index=False)
            print(f"  {len(raw)} hotspots -> {len(wk)} filas semana-celda", flush=True)


if __name__ == "__main__":
    main()
