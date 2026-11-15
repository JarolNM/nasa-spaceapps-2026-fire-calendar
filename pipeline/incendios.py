"""Agrupa hotspots en incendios (eventos) y les asigna cobertura, severidad y área aproximada.

Uso:  python pipeline/incendios.py
Entrada: data/hotspots.json
Salida:  data/incendios.json

Método
- Solo hotspots de confianza nominal/alta y tipo 0 (vegetación; sin volcán ni fuentes fijas).
- Dos hotspots pertenecen al mismo incendio si están a ≤ 1,5 km y a ≤ 2 días uno del otro
  (enlace simple: las cadenas de puntos cercanos forman un solo evento).
- Cobertura: MODIS Land Cover Type (IGBP, MCD12Q1, NASA GIBS) del año del incendio, en su centro.
- Área aproximada: píxeles únicos con detección (VIIRS 375 m ≈ 14 ha; MODIS 1 km ≈ 100 ha).
  Es el área con detección térmica, no el área quemada medida (suele sobreestimarla).
- Severidad: según la energía radiativa total (suma de FRP), en percentiles de todos los incendios
  del Tolima: baja < P50, moderada P50–P80, alta P80–P95, muy alta ≥ P95.
"""
import io
import json
import math
import re
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

IGBP = {1: 'evergreen needleleaf forest', 2: 'evergreen broadleaf forest', 3: 'deciduous needleleaf forest', 4: 'deciduous broadleaf forest', 5: 'mixed forest', 6: 'closed shrubland', 7: 'open shrubland', 8: 'woody savanna', 9: 'savanna', 10: 'grassland', 11: 'wetland', 12: 'cropland', 13: 'urban area', 14: 'cropland/natural vegetation mosaic', 15: 'snow and ice', 16: 'barren land', 17: 'water'}
GRUPO = {1: "bosque", 2: "bosque", 3: "bosque", 4: "bosque", 5: "bosque", 6: "arbustal", 7: "arbustal",
         8: "sabana", 9: "sabana", 10: "pastizal", 11: "humedal", 12: "cultivo", 13: "urbano",
         14: "cultivo", 15: "otro", 16: "otro", 17: "agua"}
CMAP_URL = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/MODIS_IGBP_Land_Cover_Type.xml"
Z = 8


def km(a, b, c, d):
    return math.hypot((a - c) * 111.0, (b - d) * 111.0 * math.cos(math.radians(a)))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "hackathon-fire-calendar/1.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def main():
    D = json.loads(Path("data/hotspots.json").read_text(encoding="utf-8"))
    n = D["meta"]["n"]
    names = [m["n"] for m in D["mpios"]]
    base = date(2000, 1, 1)
    idx = [i for i in range(n) if D["c"][i] >= 1 and D["t"][i] == 0]
    # --- fuera fuentes industriales: (1) radio alrededor de cada fuente fija del catálogo,
    #     (2) celdas de calor persistente (mismo lugar ≥ 4 años y ≥ 8 días distintos; criterio tipo
    #     "persistent thermal anomaly", Liu et al. 2018), típicas de hornos, teas y trilladoras ---
    FF = json.loads(Path("data/fuentes_fijas.json").read_text(encoding="utf-8"))
    rad = lambda f: 5.0 if f["tipo"] == "volcan" else 1.5 if f["tipo"] in ("cemento", "petroleo") else 1.0
    cerca = lambda i: any(km(D["la"][i] / 1e5, D["lo"][i] / 1e5, f["lat"], f["lon"]) <= rad(f) for f in FF)
    C = 0.004
    anios, dias = defaultdict(set), defaultdict(set)
    for i in idx:
        c = (round(D["la"][i] / 1e5 / C), round(D["lo"][i] / 1e5 / C))
        anios[c].add(D["y"][i]); dias[c].add((D["y"][i], D["j"][i]))
    pers = {c for c in anios if len(anios[c]) >= 4 and len(dias[c]) >= 8}
    def persistente(i):
        a, b = round(D["la"][i] / 1e5 / C), round(D["lo"][i] / 1e5 / C)
        return any((a + u, b + v) in pers for u in (-1, 0, 1) for v in (-1, 0, 1))
    n0 = len(idx)
    sacF = [i for i in idx if cerca(i)]
    sF = set(sacF)
    sacP = [i for i in idx if i not in sF and persistente(i)]
    fuera = sF | set(sacP)
    idx = [i for i in idx if i not in fuera]
    print(f"hotspots: {n0}; quitados por fuente fija {len(sacF)}, por calor persistente {len(sacP)} ({len(pers)} celdas); quedan {len(idx)}")
    la = {i: D["la"][i] / 1e5 for i in idx}
    lo = {i: D["lo"][i] / 1e5 for i in idx}
    dy = {i: (date(2000 + D["y"][i], 1, 1) + timedelta(D["j"][i] - 1) - base).days for i in idx}

    # --- unión-búsqueda con rejilla espacio-temporal ---
    par = {i: i for i in idx}

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    G = 0.015
    grid = defaultdict(list)
    for i in idx:
        grid[(int(la[i] / G), int(lo[i] / G), dy[i])].append(i)
    for i in idx:
        gx, gy, d0 = int(la[i] / G), int(lo[i] / G), dy[i]
        for ax in (-1, 0, 1):
            for ay in (-1, 0, 1):
                for dd in (-2, -1, 0, 1, 2):
                    for j in grid.get((gx + ax, gy + ay, d0 + dd), ()):
                        if j > i and km(la[i], lo[i], la[j], lo[j]) <= 1.5:
                            a, b = f(i), f(j)
                            if a != b:
                                par[a] = b
    grupos = defaultdict(list)
    for i in idx:
        grupos[f(i)].append(i)

    # --- cobertura IGBP ---
    cm = {}
    for m in re.finditer(r'rgb="(\d+),(\d+),(\d+)"[^>]*sourceValue="([\d,]+)"', get(CMAP_URL).decode()):
        cm[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = int(m.group(4).split(",")[-1])
    tiles = {}

    def cover(lat, lon, year):
        year = min(2024, max(2001, year))
        nz = 2 ** Z
        x = (lon + 180) / 360 * nz
        s = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * nz
        key = (year, int(x), int(y))
        if key not in tiles:
            u = (f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual/default/"
                 f"{year}-01-01/GoogleMapsCompatible_Level8/{Z}/{int(y)}/{int(x)}.png")
            try:
                tiles[key] = Image.open(io.BytesIO(get(u))).convert("RGBA")
            except Exception:
                tiles[key] = None
        im = tiles[key]
        if im is None:
            return None
        px, py = int((x - int(x)) * 256), int((y - int(y)) * 256)
        # clase más frecuente en una ventana 3x3 (≈ 1,8 km)
        votes = defaultdict(int)
        for ax in (-1, 0, 1):
            for ay in (-1, 0, 1):
                r, g, b, a = im.getpixel((min(255, max(0, px + ax)), min(255, max(0, py + ay))))
                v = cm.get((r, g, b))
                if a and v in IGBP:
                    votes[v] += 1
        return max(votes, key=votes.get) if votes else None

    ev = []
    for g in grupos.values():
        frp = [D["f"][i] / 10 for i in g]
        vi = [i for i in g if D["s"][i] == 1]
        mo = [i for i in g if D["s"][i] == 0]
        cel_v = {(round(la[i] / 0.0034), round(lo[i] / 0.0034)) for i in vi}
        cel_m = {(round(la[i] / 0.009), round(lo[i] / 0.009)) for i in mo}
        area = len(cel_v) * 14 if vi else len(cel_m) * 100
        w = [max(0.1, x) for x in frp]
        cla = sum(la[i] * x for i, x in zip(g, w)) / sum(w)
        clo = sum(lo[i] * x for i, x in zip(g, w)) / sum(w)
        d0, d1 = min(dy[i] for i in g), max(dy[i] for i in g)
        mun = max(set(D["m"][i] for i in g), key=lambda k: sum(D["m"][i] == k for i in g))
        ev.append({"lat": round(cla, 5), "lon": round(clo, 5), "d0": d0, "d1": d1, "n": len(g), "nv": len(vi),
                   "frp": round(sum(frp), 1), "frpmax": round(max(frp), 1), "area": area, "m": mun})
    # severidad por percentiles de energía total
    tot = sorted(e["frp"] for e in ev)
    p = lambda q: tot[min(len(tot) - 1, int(q * len(tot)))]
    p50, p80, p95 = p(.5), p(.8), p(.95)
    for e in ev:
        e["sev"] = 0 if e["frp"] < p50 else 1 if e["frp"] < p80 else 2 if e["frp"] < p95 else 3
    # cobertura solo para incendios con ≥ 2 detecciones (el resto: detección aislada)
    ev.sort(key=lambda e: (-e["frp"]))
    print(f"{len(ev)} incendios; con ≥2 detecciones: {sum(e['n'] >= 2 for e in ev)}; percentiles FRP P50={p50} P80={p80} P95={p95}")
    for k, e in enumerate(ev):
        y = (base + timedelta(e["d0"])).year
        c = cover(e["lat"], e["lon"], y - 1 if y > 2001 else y)  # cobertura del año anterior (antes del fuego)
        e["cob"] = c if c is not None else -1
        if k % 2000 == 0:
            print(k, "…")
    cols = ["lat", "lon", "d0", "d1", "n", "nv", "frp", "frpmax", "area", "m", "sev", "cob"]
    out = {"meta": {"metodo": "≤1.5 km and ≤2 days; nominal/high confidence; excluding fixed industrial sources (catalog radius) and persistent thermal anomalies (≥4 years, ≥8 days)",
                    "excl_fuente": len(sacF), "excl_persistente": len(sacP), "p50": p50, "p80": p80, "p95": p95,
                    "igbp": IGBP, "grupo": GRUPO, "cols": cols},
           **{c: [e[c] for e in ev] for c in cols}}
    Path("data/incendios.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print("coberturas:", Counter(GRUPO.get(e["cob"], "sin dato") for e in ev if e["n"] >= 2).most_common())
    print("tamaño KB", Path("data/incendios.json").stat().st_size // 1024)
    for e in ev[:5]:
        print(base + timedelta(e["d0"]), names[e["m"]], e["n"], "det", e["frp"], "MW", e["area"], "ha", IGBP.get(e["cob"]))


if __name__ == "__main__":
    main()
