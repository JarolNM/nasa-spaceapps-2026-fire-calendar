"""Catálogo de industrias y fuentes fijas del Tolima para el mapa (data/fuentes_fijas.json).

Uso:  python pipeline/fuentes_fijas.py
Entrada: data/hotspots.json (de points.py)

1. CATALOGO: instalaciones ubicadas con coordenadas exactas (Google Maps / OSM) e
   información de fuentes públicas. Para cada una se cuentan los hotspots que FIRMS
   marca como fuente fija o volcán (type 1/2) dentro de un radio.
2. Los grupos de hotspots fijos que no caen cerca de ninguna instalación del catálogo
   se agregan como "fuente fija sin identificar".

identificacion: "confirmada" (instalación a ≤ 300 m de las detecciones),
                "probable"   (instalación cercana del tipo esperado, ≤ 1 km),
                "contexto"   (industria cercana sin detección fija propia).
"""
import json
import math
from pathlib import Path

CATALOGO = [
    {"id": "caracolito", "tipo": "cemento", "identificacion": "confirmada",
     "nombre": "Planta de cemento Caracolito", "lat": 4.30856, "lon": -75.10133, "radio_km": 1.0,
     "empresa": "Cemex Colombia (acuerdo de venta a Holcim, 2026). Construida por Cementos Diamante.",
     "produce": "Cemento y clínker", "desde": "1993 (primera fase, Cementos Diamante)",
     "datos": ["Capacidad reportada de ~2,8 millones de toneladas/año", "Caliza de la mina La Esmeralda (Payandé, San Luis)", "Usa energía solar de Celsia desde 2025"],
     "porque": "El horno de clínker trabaja a más de 1.400 °C de forma continua: el satélite lo ve como un punto caliente todos los días.",
     "fuentes": [["ANLA – Payandé", "https://www.anla.gov.co/01_anla/index.php/noticias/849-este-mecanismo-de-participacion-ciudadana-se-realizo-en-el-corregimiento-payande-tolima-donde-la-multinacional-cemex-opera-la-mina-la-esmeralda-que-produce-materia-prima-para-la-produccion-de-cemento"],
                 ["Global Cement", "https://www.globalcement.com/news/item/10713-cemex-resumes-colombian-production"],
                 ["Las2orillas – historia", "https://www.las2orillas.co/?p=995226"]]},
    {"id": "matachin_sur", "tipo": "petroleo", "identificacion": "confirmada",
     "nombre": "Estación de Producción Matachín Sur", "lat": 3.83317, "lon": -74.87162, "radio_km": 0.8,
     "empresa": "Hocol (Grupo Ecopetrol)", "produce": "Petróleo y gas (bloque Espinal)", "desde": "Campo descubierto en 1994",
     "datos": ["Pico de producción hacia 2014", "Gas reportado: ~4 millones m³/año (2019)"],
     "porque": "Las teas queman el gas que sale con el petróleo: una llama permanente que el satélite detecta. Las detecciones se concentran en 2012–2013.",
     "fuentes": [["Global Energy Monitor", "https://www.gem.wiki/Matach%C3%ADn_Sur_(Prado)_Oil_and_Gas_Field_(Tolima,_Colombia)"],
                 ["Offshore Technology", "https://www.offshore-technology.com/?p=130905"]]},
    {"id": "matachin_norte", "tipo": "petroleo", "identificacion": "confirmada",
     "nombre": "Estación de Producción Matachín Norte", "lat": 3.85995, "lon": -74.86035, "radio_km": 0.8,
     "empresa": "Hocol (Grupo Ecopetrol)", "produce": "Petróleo y gas (bloque Espinal)", "desde": "—",
     "datos": ["Campo vecino de Matachín Sur, en Purificación"],
     "porque": "Tea de gas de la estación de producción.",
     "fuentes": [["WoodMac – bloque Espinal", "https://www.woodmac.com/reports/upstream-oil-and-gas-espinal-426625/"]]},
    {"id": "ruiz", "tipo": "volcan", "identificacion": "confirmada",
     "nombre": "Volcán Nevado del Ruiz", "lat": 4.892, "lon": -75.324, "radio_km": 3.0,
     "empresa": "Vigilado por el Servicio Geológico Colombiano (SGC)", "produce": "Actividad volcánica (cráter Arenas)", "desde": "Volcán activo; erupción de 1985",
     "datos": ["Altura: 5.321 m", "El calor viene del cráter activo Arenas, ~1 km al norte de la cumbre", "Límite entre Tolima y Caldas"],
     "porque": "FIRMS marca estos puntos como volcán activo: es calor volcánico, no un incendio.",
     "fuentes": [["Servicio Geológico Colombiano", "https://www2.sgc.gov.co/volcanes/index.html"],
                 ["Smithsonian GVP", "https://volcano.si.edu/volcano.cfm?vn=351020"]]},
    {"id": "trilladora_chaparral", "tipo": "cafe", "identificacion": "probable",
     "nombre": "Trilladora Tolima (Chaparral)", "lat": 3.72193, "lon": -75.48388, "radio_km": 1.0,
     "empresa": "Trilladora de café", "produce": "Café pergamino trillado", "desde": "—",
     "datos": ["A ~70 m del centro de las detecciones fijas de MODIS", "Chaparral es zona cafetera del sur del Tolima"],
     "porque": "Las trilladoras y secadores queman cisco (cascarilla de café) para secar el grano. MODIS (píxel de 1 km) no permite asegurar cuál edificio es la fuente.",
     "fuentes": [["Google Maps", "https://www.google.com/maps/search/Trilladora+Tolima+Chaparral"]]},
    {"id": "molino_colombia_venadillo", "tipo": "arroz", "identificacion": "probable",
     "nombre": "Inversiones Molino Colombia (Venadillo)", "lat": 4.71548, "lon": -74.93255, "radio_km": 1.2,
     "empresa": "Molino de arroz", "produce": "Arroz blanco y subproductos", "desde": "—",
     "datos": ["A ~700 m de las detecciones fijas de MODIS en Venadillo"],
     "porque": "Los molinos queman cascarilla de arroz en hornos para secar el grano.",
     "fuentes": [["Google Maps", "https://www.google.com/maps/search/Inversiones+Molino+Colombia+Venadillo"]]},
    {"id": "paisa_arroz_guamo", "tipo": "arroz", "identificacion": "probable",
     "nombre": "Paisa Arroz (Guamo)", "lat": 4.02983, "lon": -74.96673, "radio_km": 1.0,
     "empresa": "Empresa arrocera", "produce": "Arroz", "desde": "—",
     "datos": ["A ~400 m de las detecciones fijas de MODIS en Guamo"],
     "porque": "Probable horno de cascarilla de un molino de arroz; MODIS no permite confirmarlo.",
     "fuentes": [["Google Maps", "https://www.google.com/maps/search/Paisa+Arroz+Guamo"]]},
    # contexto: agroindustria del arroz en El Espinal (las detecciones fijas caen 1–1,4 km, en el casco urbano)
    {"id": "diana_espinal", "tipo": "arroz", "identificacion": "contexto",
     "nombre": "Molino Diana Corporación (El Espinal)", "lat": 4.14710, "lon": -74.89743, "radio_km": 1.5,
     "empresa": "Grupo Diana (Arroz Diana)", "produce": "Arroz blanco, aceites y otros alimentos", "desde": "1964 (Molino Murra, origen del grupo)",
     "datos": ["Plantas del grupo en Espinal, Saldaña, Lérida, Venadillo, Ibagué, Doima y Mariquita", "Uno de los mayores comercializadores de arroz del país"],
     "porque": "Molino que quema cascarilla para secar arroz. Las detecciones fijas de MODIS en El Espinal se centran a ~1,3 km, en el casco urbano.",
     "fuentes": [["Valora Analitik", "https://www.valoraanalitik.com/?p=446213"], ["Semana", "https://www.semana.com/economia/articulo/solidaridad-que-crecio-como-arroz/202000/"]]},
    {"id": "diana_espinal_p1", "tipo": "arroz", "identificacion": "contexto",
     "nombre": "Molino Diana Espinal – Planta I", "lat": 4.15873, "lon": -74.90114, "radio_km": 1.5,
     "empresa": "Grupo Diana", "produce": "Arroz", "desde": "—", "datos": [],
     "porque": "Molino de arroz cercano a las detecciones fijas de El Espinal.",
     "fuentes": [["Google Maps", "https://www.google.com/maps/search/MOLINO+DIANA+ESPINAL+PLANTA+I"]]},
    {"id": "molino_espinal", "tipo": "arroz", "identificacion": "contexto",
     "nombre": "Molino Espinal", "lat": 4.14891, "lon": -74.89653, "radio_km": 1.5,
     "empresa": "Molino de arroz", "produce": "Arroz", "desde": "—", "datos": [],
     "porque": "Molino de arroz cercano a las detecciones fijas de El Espinal.",
     "fuentes": [["Google Maps", "https://www.google.com/maps/search/Molino+Espinal"]]},
    {"id": "supremo_espinal", "tipo": "arroz", "identificacion": "contexto",
     "nombre": "Unión de Arroceros – Molino San Joaquín", "lat": 4.15687, "lon": -74.90119, "radio_km": 1.5,
     "empresa": "Unión de Arroceros S.A.S. (Arroz Supremo)", "produce": "Arroz", "desde": "Empresa con unas seis décadas (plantas en Venadillo, El Espinal e Ibagué)",
     "datos": ["Fundada por agricultores arroceros tolimenses"],
     "porque": "Molino de arroz cercano a las detecciones fijas de El Espinal.",
     "fuentes": [["Portafolio", "https://www.portafolio.co/negocios/empresas/la-arrocera-supremo-cumple-60-anos-y-lo-celebra-con-un-nuevo-producto-lanzo-arroz-ecoamigable-482846"]]},
]


def km(a, b, c, d):
    return math.hypot((a - c) * 111, (b - d) * 111 * math.cos(math.radians(a)))


def main():
    D = json.loads(Path("data/hotspots.json").read_text(encoding="utf-8"))
    n = D["meta"]["n"]
    names = [m["n"] for m in D["mpios"]]
    fijos = [i for i in range(n) if D["t"][i] in (1, 2)]
    P = {i: (D["la"][i] / 1e5, D["lo"][i] / 1e5) for i in fijos}
    usados = set()
    out = []
    for f in CATALOGO:
        cerca = [i for i in fijos if km(*P[i], f["lat"], f["lon"]) <= f["radio_km"]
                 and (f["tipo"] == "volcan") == (D["t"][i] == 1)]
        if f["identificacion"] != "contexto":
            usados.update(cerca)
        ys = sorted(2000 + D["y"][i] for i in cerca)
        x = {k: v for k, v in f.items() if k != "radio_km"}
        x.update(n=len(cerca), desde_det=ys[0] if ys else None, hasta_det=ys[-1] if ys else None,
                 viirs=sum(D["s"][i] for i in cerca), municipio=None)
        # municipio: el del hotspot fijo más cercano, o el del hotspot más cercano en general
        ref = min(range(n), key=lambda i: km(D["la"][i] / 1e5, D["lo"][i] / 1e5, f["lat"], f["lon"]))
        x["municipio"] = names[D["m"][ref]]
        out.append(x)
    # grupos restantes (sin identificar)
    resto = [i for i in fijos if i not in usados and D["t"][i] == 2]
    groups = []
    for i in resto:
        la, lo = P[i]
        for g in groups:
            if km(la, lo, g["la"], g["lo"]) < 1.5:
                g["p"].append(i)
                k = len(g["p"])
                g["la"] += (la - g["la"]) / k
                g["lo"] += (lo - g["lo"]) / k
                break
        else:
            groups.append({"la": la, "lo": lo, "p": [i]})
    for g in sorted(groups, key=lambda g: -len(g["p"])):
        if len(g["p"]) < 6:
            continue
        ys = sorted(2000 + D["y"][i] for i in g["p"])
        mi = max(set(D["m"][i] for i in g["p"]), key=lambda k: sum(D["m"][i] == k for i in g["p"]))
        cerca_ctx = [f["nombre"] for f in CATALOGO if km(g["la"], g["lo"], f["lat"], f["lon"]) < 2]
        out.append({"id": f"sinid_{len(out)}", "tipo": "sin_identificar", "identificacion": "sin identificar",
                    "nombre": f"Fuente fija en {names[mi]}", "lat": round(g["la"], 5), "lon": round(g["lon"] if "lon" in g else g["lo"], 5),
                    "empresa": "—", "produce": "Desconocido", "desde": "—",
                    "datos": (["Industrias cercanas: " + ", ".join(cerca_ctx)] if cerca_ctx else []) +
                             [f"Detectada por {'MODIS (píxel de 1 km)' if sum(D['s'][i] for i in g['p']) == 0 else 'MODIS y VIIRS'}: la ubicación exacta tiene un margen de ~1 km"],
                    "porque": "FIRMS detecta calor repetido en el mismo lugar durante años: suele ser un horno, molino, trilladora o ladrillera dentro del casco urbano. Aún no está identificada.",
                    "fuentes": [], "n": len(g["p"]), "desde_det": ys[0], "hasta_det": ys[-1],
                    "viirs": sum(D["s"][i] for i in g["p"]), "municipio": names[mi]})
    Path("data/fuentes_fijas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in out:
        print(f'{x["n"]:4d}  {x["tipo"]:15s} {x["identificacion"]:15s} {x["nombre"][:42]:42s} {x["municipio"]}')


if __name__ == "__main__":
    main()
