# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Armoniza MODIS y VIIRS: calibra MODIS contra VIIRS en el solapamiento y
exporta data/harmonized.json para la web.

Entrada : data/weekly/modis_<anio>.csv, data/weekly/viirs_<anio>.csv
          (opcional) data/urban_mask.csv con columnas row,col  -> celdas a excluir
Salida  : data/harmonized.json, data/validation.json

Metodo:
  1. Matrices M[anio,semana,fila,col] (MODIS) y V[...] (VIIRS), conteos de hotspots.
  2. Fuentes fijas: celdas con deteccion en >60 % de las semanas VIIRS se marcan
     como 'urban' (industriales/gas) junto con la mascara manual.
  3. Factor k = sum(VIIRS)/sum(MODIS) en el solapamiento (VIIRS_START..fin),
     por banda de latitud (norte/centro/sur) y mes; con respaldo a k de banda y global.
  4. Armonizado = MODIS*k antes de VIIRS_START y VIIRS despues (la web lo calcula).
  5. Validacion: R2 y sesgo semanal de MODIS*k vs VIIRS por banda.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

Y0, Y1, VIIRS_START = 2000, 2025, 2012
NW = 53
from config import WEST, SOUTH, EAST, NORTH, STEP, BAND_CUTS, BAND_NAMES
NR, NC = int((NORTH - SOUTH) / STEP), int((EAST - WEST) / STEP)
NY = Y1 - Y0 + 1


def load(sensor):
    A = np.zeros((NY, NW, NR, NC))
    years = []
    for f in sorted(Path("data/weekly").glob(f"{sensor}_*.csv")):
        y = int(f.stem.split("_")[1])
        if not (Y0 <= y <= Y1):
            continue
        df = pd.read_csv(f)
        df = df[(df.row >= 0) & (df.row < NR) & (df.col >= 0) & (df.col < NC)]
        np.add.at(A, (y - Y0, df.week.values, df.row.values, df["col"].values), df["count"].values)
        years.append(y)
    return A, years


def band_of(r):  # 0 = norte, 1 = centro, 2 = sur (limites en config.py)
    lat = NORTH - (r + 0.5) * STEP
    return 0 if lat >= BAND_CUTS[0] else (1 if lat >= BAND_CUTS[1] else 2)


def main():
    M, ym = load("modis")
    V, yv = load("viirs")
    if not ym or not yv:
        raise SystemExit("Faltan CSV en data/weekly (ejecuta download_firms.py).")
    print(f"MODIS anios: {min(ym)}-{max(ym)} ({len(ym)}) | VIIRS: {min(yv)}-{max(yv)} ({len(yv)})")

    # --- fuentes fijas / mascara urbana ---
    vy = [y - Y0 for y in yv]
    frac = (V[vy] > 0).reshape(len(vy) * NW, NR, NC).mean(axis=0)
    urban = frac > 0.6
    mask_file = Path("data/urban_mask.csv")
    if mask_file.exists():
        m = pd.read_csv(mask_file)
        urban[m.row.values, m.col.values] = True
    print(f"Celdas marcadas como urbanas/fuente fija: {int(urban.sum())}")
    use = ~urban
    tol_file = Path("data/tolima.json")  # generado por pipeline/tolima_mask.py
    inside = np.ones((NR, NC), bool)
    if tol_file.exists():
        inside[:] = False
        for t in json.loads(tol_file.read_text(encoding="utf-8"))["cells"]:
            if t["frac"] >= 0.25:
                inside[t["r"], t["c"]] = True
        use &= inside
        print(f"Recorte al Tolima: {int(inside.sum())} celdas dentro (>=25 % de area)")

    # --- calibracion k por banda x mes ---
    bands = np.array([band_of(r) for r in range(NR)])
    month_of_week = np.minimum(11, ((np.arange(NW) * 7 + 3) / 30.44).astype(int))
    ov = [y - Y0 for y in sorted(set(ym) & set(yv))]
    sv_tot, sm_tot = V[ov][..., use].sum(), M[ov][..., use].sum()
    k_glob = float(sv_tot / sm_tot) if sm_tot > 0 else 1.0
    k = np.full((3, 12), k_glob)
    for b in range(3):
        cells_b = use & (bands[:, None] == b)
        sv, sm = V[ov][..., cells_b].sum(), M[ov][..., cells_b].sum()
        kb = float(sv / sm) if sm > 50 else k_glob
        for mth in range(12):
            wk = np.where(month_of_week == mth)[0]
            sv = V[ov][:, wk][..., cells_b].sum()
            sm = M[ov][:, wk][..., cells_b].sum()
            k[b, mth] = float(sv / sm) if sm > 50 else kb
    print(f"k global = {k_glob:.2f}")

    # --- validacion (solapamiento) ---
    val = {"k_global": k_glob, "bands": {}}
    for b, name in enumerate(BAND_NAMES):
        cells_b = use & (bands[:, None] == b)
        mk = np.zeros((len(ov), NW))
        vv = np.zeros((len(ov), NW))
        for w in range(NW):
            kk = k[b, month_of_week[w]]
            mk[:, w] = M[ov][:, w][:, cells_b].sum(axis=1) * kk
            vv[:, w] = V[ov][:, w][:, cells_b].sum(axis=1)
        a, c = mk.ravel(), vv.ravel()
        r2 = float(np.corrcoef(a, c)[0, 1] ** 2) if a.std() > 0 and c.std() > 0 else None
        bias = float((a.sum() - c.sum()) / c.sum()) if c.sum() > 0 else None
        val["bands"][name] = {"r2_semanal": r2, "sesgo_relativo": bias}
        print(f"  banda {name}: R2={r2 if r2 is None else round(r2, 3)} sesgo={bias if bias is None else round(bias, 3)}")
    Path("data/validation.json").write_text(json.dumps(val, indent=2))

    # --- exportar ---
    cells = []
    for r in range(NR):
        for c in range(NC):
            m = M[:, :, r, c].ravel().astype(int).tolist()
            v = V[:, :, r, c].ravel().astype(int).tolist()
            if not inside[r, c] or (sum(m) == 0 and sum(v) == 0 and not urban[r, c]):
                continue
            cells.append({"r": r, "c": c, "urban": bool(urban[r, c]), "m": m, "v": v})
    out = {
        "meta": {"y0": Y0, "y1": Y1, "viirs_start": VIIRS_START, "nw": NW,
                 "bbox": [WEST, SOUTH, EAST, NORTH], "step": STEP,
                 "k_global": k_glob, "k_banda_mes": k.tolist(),
                 "bandas": list(BAND_NAMES), "band_cuts": list(BAND_CUTS)},
        "cells": cells,
    }
    Path("data/harmonized.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"Exportado data/harmonized.json con {len(cells)} celdas")


if __name__ == "__main__":
    main()
