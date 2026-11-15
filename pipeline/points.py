# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Exporta cada hotspot del Tolima (resolucion nativa) para la web.

Uso:    python pipeline/points.py RUTA/AL/TOLIMA.gpkg
Entrada: data/raw/modis_<anio>.csv, data/raw/viirs_<anio>.csv (de download_firms.py)
         GeoPackage de municipios del DANE (MGN) del Tolima
Salida:  data/hotspots.json  (columnar, compacto)
         data/validation.json (k y R2 del solapamiento, filtro nominal+alta)

Pasos:
  1. Une todos los CSV crudos y elimina duplicados exactos (sensor, lat, lon, fecha, hora).
  2. Confianza en 3 clases como FIRMS: VIIRS l/n/h; MODIS <30 baja, 30-79 nominal, >=80 alta.
  3. Conserva 'type' de FIRMS: 0 fuego de vegetacion presunto, 1 volcan activo,
     2 otra fuente fija terrestre, 3 costa afuera.
  4. Asigna municipio con los poligonos completos del DANE; descarta puntos fuera del Tolima.

Formato data/hotspots.json:
  {"meta":{"y0":2000,"y1":2025,"viirs_start":2012,"band_cuts":[4.5,3.75],"n":N},
   "mpios":[{"n":nombre,"area":km2,"lat":centroide,"rings":[[[lon,lat],...]]}],
   "s":[0=MODIS,1=VIIRS], "sat":[0=Terra,1=Aqua,2=S-NPP], "y":[anio-2000], "j":[dia del anio],
   "hm":[hora UTC HHMM], "la":[lat*1e5], "lo":[lon*1e5], "c":[0 baja,1 nominal,2 alta],
   "f":[FRP*10], "t":[type], "m":[indice de municipio], "dn":[0 dia,1 noche]}
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from tolima_mask import parse_gpkg_geom, simplify, SIMPLIFY_TOL  # noqa: E402
from config import BAND_CUTS  # noqa: E402

Y0, Y1, VIIRS_START = 2000, 2025, 2012


def load_raw():
    frames = []
    for f in sorted(Path("data/raw").glob("*.csv")):
        sensor = f.stem.split("_")[0]
        df = pd.read_csv(f, dtype={"confidence": str})
        if df.empty:
            continue
        df["s"] = 1 if sensor == "viirs" else 0
        frames.append(df[["s", "latitude", "longitude", "acq_date", "acq_time", "satellite",
                          "confidence", "frp", "type", "daynight"]])
    df = pd.concat(frames, ignore_index=True)
    n0 = len(df)
    df = df.drop_duplicates(subset=["s", "latitude", "longitude", "acq_date", "acq_time"])
    print(f"Hotspots crudos: {n0} | duplicados eliminados: {n0 - len(df)}")
    return df.reset_index(drop=True)


def conf_class(df):
    c = np.zeros(len(df), np.int8)
    v = df.s.values == 1
    cv = df.confidence.str.lower().str[0]
    c[v & (cv == "n").values] = 1
    c[v & (cv == "h").values] = 2
    cm = pd.to_numeric(df.confidence, errors="coerce").fillna(0).values
    c[~v & (cm >= 30)] = 1
    c[~v & (cm >= 80)] = 2
    return c


def points_in_rings(x, y, rings):
    inside = np.zeros(len(x), bool)
    for ring in rings:
        r = np.asarray(ring)
        xi, yi = r[:, 0], r[:, 1]
        xj, yj = np.roll(xi, 1), np.roll(yi, 1)
        for a, b, c, d in zip(xi, yi, xj, yj):
            if b == d:
                continue
            cross = (b > y) != (d > y)
            if cross.any():
                xint = (c - a) * (y - b) / (d - b) + a
                inside ^= cross & (x < xint)
    return inside


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python pipeline/points.py RUTA/AL/TOLIMA.gpkg")
    con = sqlite3.connect(sys.argv[1])
    table, gcol = con.execute("select table_name, column_name from gpkg_geometry_columns").fetchone()
    mpios = []
    for name, area, blob in con.execute(f'select mpio_cnmbr, mpio_narea, "{gcol}" from "{table}"'):
        polys = parse_gpkg_geom(blob)
        allpts = np.array([p for poly in polys for p in poly[0]])
        mpios.append({"n": name.title(), "area": round(float(area), 1), "polys": polys,
                      "bbox": (*allpts.min(0), *allpts.max(0)), "lat": round(float(allpts[:, 1].mean()), 4)})

    df = load_raw()
    x, y = df.longitude.values, df.latitude.values
    mi = np.full(len(df), -1, np.int16)
    for k, m in enumerate(mpios):
        b = m["bbox"]
        cand = np.where((mi < 0) & (x >= b[0]) & (x <= b[2]) & (y >= b[1]) & (y <= b[3]))[0]
        if not len(cand):
            continue
        ins = np.zeros(len(cand), bool)
        for poly in m["polys"]:
            ins |= points_in_rings(x[cand], y[cand], poly)
        mi[cand[ins]] = k
    keep = mi >= 0
    print(f"Dentro del Tolima: {keep.sum()} de {len(df)}")
    df, mi = df[keep].reset_index(drop=True), mi[keep]

    d = pd.to_datetime(df.acq_date)
    c = conf_class(df)
    sat = df.satellite.astype(str).map({"Terra": 0, "T": 0, "Aqua": 1, "A": 1}).fillna(2).astype(int)
    out = {
        "meta": {"y0": Y0, "y1": Y1, "viirs_start": VIIRS_START, "band_cuts": list(BAND_CUTS), "n": int(len(df))},
        "mpios": [{"n": m["n"], "area": m["area"], "lat": m["lat"],
                   "rings": [[[round(px, 4), round(py, 4)] for px, py in
                              (lambda r, k: simplify(r[:k + 1], SIMPLIFY_TOL)[:-1] + simplify(r[k:], SIMPLIFY_TOL))(
                                  p[0], max(range(len(p[0])), key=lambda i: (p[0][i][0] - p[0][0][0]) ** 2 + (p[0][i][1] - p[0][0][1]) ** 2))]
                             for p in m["polys"]]} for m in mpios],
        "s": df.s.astype(int).tolist(),
        "sat": sat.tolist(),
        "y": (d.dt.year - Y0).astype(int).tolist(),
        "j": d.dt.day_of_year.astype(int).tolist(),
        "hm": df.acq_time.astype(int).tolist(),
        "la": np.round(df.latitude.values * 1e5).astype(int).tolist(),
        "lo": np.round(df.longitude.values * 1e5).astype(int).tolist(),
        "c": c.astype(int).tolist(),
        "f": np.round(df.frp.fillna(0).values * 10).astype(int).tolist(),
        "t": df["type"].fillna(0).astype(int).tolist(),
        "m": mi.astype(int).tolist(),
        "dn": (df.daynight.astype(str) == "N").astype(int).tolist(),
    }
    Path("data/hotspots.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Exportado data/hotspots.json ({Path('data/hotspots.json').stat().st_size // 1024} KB)")

    # --- resumen ---
    names = {0: "baja", 1: "nominal", 2: "alta"}
    for s, sn in ((0, "MODIS"), (1, "VIIRS")):
        sel = df.s.values == s
        print(f"{sn}: " + ", ".join(f"{names[k]}={int(((c == k) & sel).sum())}" for k in range(3)))
    tt = df["type"].fillna(0).astype(int).values
    print("type FIRMS:", {int(k): int((tt == k).sum()) for k in np.unique(tt)})
    for k in np.unique(tt):
        if k != 0:
            top = pd.Series([mpios[i]["n"] for i in mi[tt == k]]).value_counts().head(3).to_dict()
            print(f"  type {int(k)} en: {top}")

    # --- validacion con filtro por defecto (nominal+alta, type 0) ---
    ok = (c >= 1) & (tt == 0)
    yr = d.dt.year.values
    wk = np.minimum(52, (d.dt.day_of_year.values - 1) // 7)
    lat = df.latitude.values
    band = np.where(lat >= BAND_CUTS[0], 0, np.where(lat >= BAND_CUTS[1], 1, 2))
    ov = ok & (yr >= VIIRS_START)
    V = np.zeros((3, Y1 - VIIRS_START + 1, 53))
    M = np.zeros_like(V)
    for arr, s in ((M, 0), (V, 1)):
        sel = ov & (df.s.values == s)
        np.add.at(arr, (band[sel], yr[sel] - VIIRS_START, wk[sel]), 1)
    kg = V.sum() / M.sum()
    val = {"filtro": "nominal+alta, type 0", "k_global": round(float(kg), 3), "bandas": {}}
    print(f"k global (nominal+alta, type 0) = {kg:.2f}")
    for b, name in enumerate(("norte", "centro", "sur")):
        kb = V[b].sum() / M[b].sum()
        r2w = np.corrcoef(M[b].ravel(), V[b].ravel())[0, 1] ** 2
        m4 = M[b][:, :52].reshape(-1, 13, 4).sum(2).ravel()
        v4 = V[b][:, :52].reshape(-1, 13, 4).sum(2).ravel()
        r24 = np.corrcoef(m4, v4)[0, 1] ** 2
        val["bandas"][name] = {"k": round(float(kb), 3), "r2_semanal": round(float(r2w), 3), "r2_4semanas": round(float(r24), 3)}
        print(f"  {name}: k={kb:.2f} R2 semanal={r2w:.2f} R2 4 semanas={r24:.2f}")
    Path("data/validation.json").write_text(json.dumps(val, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
