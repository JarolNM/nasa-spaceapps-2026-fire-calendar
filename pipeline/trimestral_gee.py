"""Serie histórica trimestral (por temporada) de imágenes del Tolima, 2000–2025, con Google Earth Engine.

Uso (una sola vez):  earthengine authenticate      (cuenta Google con Earth Engine habilitado)
Luego:               python pipeline/trimestral_gee.py --project MI-PROYECTO-GCP
Opcional:            --drive   además exporta la serie completa a 30 m a Google Drive (GeoTIFF, para análisis)
                     --desde 2000 --hasta 2025

Método
- Trimestres por temporada del Tolima (no de calendario):
    DEF = dic (año anterior)–feb  · seca      MAM = mar–may · lluvias
    JJA = jun–ago · seca                      SON = sep–nov · lluvias
- Colecciones de reflectancia de superficie (nivel 2):
    Landsat 5 TM (2000–2011), Landsat 7 ETM+ (2000–2025, con franjas desde 2003),
    Landsat 8/9 OLI (2013–), Sentinel-2 MSI (2017–, con Cloud Score+).
- Máscara de nubes y sombras (QA_PIXEL en Landsat; Cloud Score+ ≥ 0,6 en Sentinel-2).
- Armonización de sensores hacia Landsat 8 OLI:
    TM/ETM+ → OLI con los coeficientes de Roy et al. (2016, Remote Sens. Environ. 185);
    Sentinel-2 → OLI con los coeficientes de HLS (Claverie et al., 2018).
- Composición = mediana de todas las observaciones despejadas del trimestre (rellena las franjas de Landsat 7).
- Índices: NDVI (vegetación), NBR (quemado) y dNBR = NBR del trimestre anterior − NBR actual
  (en la app solo > 0,2 para quitar el cambio estacional; > 0,27 moderada; > 0,44 alta, Key & Benson 2006).
- Salidas
    data/trimestral/AAAA-T_rgb.webp  color natural, ~130 m, EPSG:3857 (para la app)
    data/trimestral/AAAA-T_dnbr.webp dNBR coloreado (transparente donde no hay cambio)
    data/trimestral/index.json       lista de trimestres, nº de imágenes y % del Tolima con dato
"""
import argparse
import io
import json
import math
import time
import urllib.request
from pathlib import Path

import ee
from PIL import Image, ImageChops, ImageDraw

OUT = Path("data/trimestral")
BBOX = [-76.24378, 2.82, -74.32622, 5.37]   # mismo encuadre que la imagen Landsat 2000 de la app
DIM = 2200                                    # lado mayor en píxeles (≈ 130 m en el Tolima)
TRIM = [("DEF", -1, 12, 3, "seca"), ("MAM", 0, 3, 6, "lluvias"), ("JJA", 0, 6, 9, "seca"), ("SON", 0, 9, 12, "lluvias")]
BANDS = ["blue", "green", "red", "nir", "swir1", "swir2"]

# Roy et al. 2016, tabla 2 (OLS ETM+ → OLI): pendiente, intercepto
ROY = {"blue": (0.8474, 0.0003), "green": (0.8483, 0.0088), "red": (0.9047, 0.0061),
       "nir": (0.8462, 0.0412), "swir1": (0.8937, 0.0254), "swir2": (0.9071, 0.0172)}
# HLS v2 (Claverie et al. 2018), MSI (S2A) → OLI
HLS = {"blue": (0.9778, -0.004), "green": (1.0053, -0.0009), "red": (0.9765, 0.0009),
       "nir": (0.9983, -0.0001), "swir1": (0.9987, -0.0011), "swir2": (1.003, -0.0012)}


def tolima():
    D = json.loads(Path("data/tolima.json").read_text(encoding="utf-8"))
    polys = [ee.Geometry.Polygon([r]) for m in D["municipios"] for r in m["rings"]]
    return ee.FeatureCollection([ee.Feature(p) for p in polys]).geometry().dissolve(maxError=100)


def ajustar(img, coef):
    return ee.Image.cat([img.select(b).multiply(coef[b][0]).add(coef[b][1]).rename(b) for b in BANDS])


def landsat(cid, bandas, coef):
    def prep(img):
        qa = img.select("QA_PIXEL")
        ok = qa.bitwiseAnd(0b11111).eq(0)           # relleno, nube dilatada, cirro, nube, sombra
        sr = img.select(bandas, BANDS).multiply(0.0000275).add(-0.2)
        sr = ajustar(sr, coef) if coef else sr
        return sr.toFloat().updateMask(ok).copyProperties(img, ["system:time_start"])
    return ee.ImageCollection(cid).map(prep)


def sentinel2():
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")

    def prep(img):
        sr = img.select(["B2", "B3", "B4", "B8A", "B11", "B12"], BANDS).divide(10000)
        return ajustar(sr, HLS).toFloat().updateMask(img.select("cs").gte(0.6)).copyProperties(img, ["system:time_start"])
    return (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .linkCollection(cs, ["cs"]).map(prep))


def coleccion(region):
    tm = ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"]
    oli = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
    return (landsat("LANDSAT/LT05/C02/T1_L2", tm, ROY)
            .merge(landsat("LANDSAT/LE07/C02/T1_L2", tm, ROY))
            .merge(landsat("LANDSAT/LC08/C02/T1_L2", oli, None))
            .merge(landsat("LANDSAT/LC09/C02/T1_L2", oli, None))
            .merge(sentinel2())
            .filterBounds(region))


def rango(y, t):
    """[inicio, fin) del trimestre; DEF empieza el 1 dic del año anterior."""
    _, dy, m0, m1, _ = TRIM[t]
    return ee.Date.fromYMD(y + dy, m0, 1), ee.Date.fromYMD(y, m1, 1)


def compuesto(col, y, t):
    ini, fin = rango(y, t)
    c = col.filterDate(ini, fin)
    med = c.median()
    nbr = med.normalizedDifference(["nir", "swir2"]).rename("nbr")
    ndvi = med.normalizedDifference(["nir", "red"]).rename("ndvi")
    return med.addBands([nbr, ndvi]), c.size()


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def lat_de(y):
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


W0, S0, E0, N0 = BBOX
X0, X1, Y0, Y1 = math.radians(W0), math.radians(E0), merc_y(S0), merc_y(N0)
H = DIM if (Y1 - Y0) >= (X1 - X0) else round(DIM * (Y1 - Y0) / (X1 - X0))
W = DIM if (X1 - X0) > (Y1 - Y0) else round(DIM * (X1 - X0) / (Y1 - Y0))


def mascara():
    """Máscara del Tolima en píxeles de la imagen (proyección Mercator, igual que Leaflet)."""
    D = json.loads(Path("data/tolima.json").read_text(encoding="utf-8"))
    m = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(m)
    for mu in D["municipios"]:
        for r in mu["rings"]:
            dr.polygon([((math.radians(x) - X0) / (X1 - X0) * W, (Y1 - merc_y(y)) / (Y1 - Y0) * H) for x, y in r], fill=255)
    return m


def bajar(vis, path, mask):
    """Descarga en 2x2 piezas (límite de memoria de Earth Engine), une, recorta al Tolima y guarda WebP con transparencia.
    Devuelve la fracción del Tolima con dato, o None si falla."""
    out = Image.new("RGBA", (W, H))
    xs, ys = [0, W // 2, W], [0, H // 2, H]
    for i in range(2):
        for j in range(2):
            px0, px1, py0, py1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            lon0, lon1 = W0 + (E0 - W0) * px0 / W, W0 + (E0 - W0) * px1 / W
            lat1, lat0 = lat_de(Y1 - (Y1 - Y0) * py0 / H), lat_de(Y1 - (Y1 - Y0) * py1 / H)
            reg = ee.Geometry.Rectangle([lon0, lat0, lon1, lat1], None, False)
            url = vis.getThumbURL({"region": reg, "dimensions": f"{px1 - px0}x{py1 - py0}", "crs": "EPSG:3857", "format": "png"})
            for k in range(4):
                try:
                    im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=300).read())).convert("RGBA")
                    out.paste(im.resize((px1 - px0, py1 - py0)), (px0, py0))
                    break
                except Exception as e:
                    print("   reintento", k + 1, e)
                    time.sleep(5 * (k + 1))
            else:
                return None
    al = ImageChops.multiply(out.getchannel("A"), mask)
    out.putalpha(al)
    out.save(path, "WEBP", quality=80, method=6)
    tot = sum(mask.histogram()[128:])
    return sum(al.histogram()[128:]) / tot if tot else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="proyecto de Google Cloud registrado en Earth Engine")
    ap.add_argument("--desde", type=int, default=2000)
    ap.add_argument("--hasta", type=int, default=2025)
    ap.add_argument("--drive", action="store_true", help="exportar también la serie a 30 m a Google Drive")
    a = ap.parse_args()
    ee.Initialize(project=a.project)
    OUT.mkdir(parents=True, exist_ok=True)
    region = tolima()
    caja = ee.Geometry.Rectangle(BBOX, None, False)
    col = coleccion(caja)
    mask = mascara()
    idx_path = OUT / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"items": []}
    # cada trimestre deja su ficha en _items/ (permite varios procesos en paralelo por rangos de años)
    IT = OUT / "_items"
    IT.mkdir(exist_ok=True)
    for i in idx["items"]:
        if not (IT / f"{i['id']}.json").exists():
            (IT / f"{i['id']}.json").write_text(json.dumps(i, ensure_ascii=False), encoding="utf-8")
    hechos = {f.stem for f in IT.glob("*.json")}
    prev_nbr = compuesto(col, a.desde - 1, 3)[0].select("nbr") if a.desde > 2000 else None
    vis_rgb = {"bands": ["red", "green", "blue"], "min": 0.0, "max": 0.28, "gamma": 1.3}
    pal = ["ffffcc", "fd8d3c", "e31a1c", "7f0000"]
    for y in range(a.desde, a.hasta + 1):
        for t, (nom, _, _, _, temp) in enumerate(TRIM):
            if y == 2000 and t == 0:
                prev_nbr = None
                continue                                # dic 1999 sin cobertura útil
            tid = f"{y}-{nom}"
            img, n = compuesto(col, y, t)
            dnbr = prev_nbr.subtract(img.select("nbr")).rename("dnbr") if prev_nbr is not None else None
            prev_nbr = img.select("nbr")
            if tid in hechos or (IT / f"{tid}.json").exists():
                continue
            n = n.getInfo()
            cov = bajar(img.visualize(**vis_rgb), OUT / f"{tid}_rgb.webp", mask)
            ok = cov is not None
            cov = cov or 0
            print(tid, temp, n, "imágenes", round(cov * 100), "% con dato", flush=True)
            dok = False
            if dnbr is not None and ok:
                vis_d = dnbr.updateMask(dnbr.gt(0.2)).visualize(min=0.2, max=0.66, palette=pal)
                dok = bajar(vis_d, OUT / f"{tid}_dnbr.webp", mask) is not None
            if a.drive:
                ee.batch.Export.image.toDrive(
                    image=img.select(BANDS + ["ndvi", "nbr"]).addBands(dnbr if dnbr is not None else ee.Image(0).rename("dnbr")).toFloat(),
                    description=f"tolima_{tid}", folder="tolima_trimestral", region=region, scale=30,
                    crs="EPSG:3116", maxPixels=1e10).start()
            if ok and tid not in hechos:
                (IT / f"{tid}.json").write_text(json.dumps({"id": tid, "y": y, "t": t, "temp": temp, "n": n, "cob": round(cov * 100), "dnbr": dok},
                                                           ensure_ascii=False), encoding="utf-8")
                hechos.add(tid)
                idx["items"] = sorted((json.loads(f.read_text(encoding="utf-8")) for f in IT.glob("*.json")), key=lambda i: (i["y"], i["t"]))
                idx["bounds"] = [[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]]
                idx["metodo"] = ("Mediana sin nubes por temporada (DEF, MAM, JJA, SON) de Landsat 5/7/8/9 y Sentinel-2, "
                                 "armonizados a Landsat 8 (Roy 2016; HLS). dNBR = NBR trimestre anterior − actual.")
                idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
    print("listo:", len(idx["items"]), "trimestres en", OUT)


if __name__ == "__main__":
    main()
