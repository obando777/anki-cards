#!/usr/bin/env python3
"""Resuelve las imágenes que faltan en el módulo de Cultura.

    uv run --group images scripts/fetch_cultura.py            # descarga
    uv run --group images scripts/fetch_cultura.py --sheets D # hojas para revisar

Tres fuentes, en este orden: la guía oficial (ya extraída y verificada), una
búsqueda en Wikimedia Commons, y solo como último recurso una ilustración
generada — que nunca se usa para un símbolo patrio, un billete, un mapa ni el
rostro de una persona real. A Grok se le pidió el escudo nacional de prueba y
devolvió uno con cuatro cuarteles, un capibara y caña de azúcar.

La tabla de abajo es explícita a propósito: emparejar por parecido de texto puso
«río Magdalena» en la tarjeta del mapalé solo porque ambos nombran el Magdalena.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from ankicards import images as IM  # noqa: E402
from ankicards.loader import MEDIA_DIR  # noqa: E402

CULTURA = Path("decks/colombia/01-cultura-y-sociedad.yaml")

# card_id -> consulta de búsqueda en Commons. Entidades y eventos reales.
COMMONS = {
    # deporte
    "cul-kid-pambele": "Antonio Cervantes Kid Pambelé boxeador",
    "cul-juan-pablo-montoya": "Juan Pablo Montoya driver",
    "cul-fabiola-zuluaga": "Fabiola Zuluaga tennis",
    "cul-cochise-rodriguez": "Martín Cochise Rodríguez ciclista",
    "cul-rafael-nino": "Rafael Antonio Niño ciclista",
    "cul-nairo-quintana": "Nairo Quintana cyclist",
    "cul-coldeportes": "Carlos Lleras Restrepo presidente Colombia",
    # literatura
    "cul-garcia-marquez": "Gabriel García Márquez writer",
    "cul-jorge-isaacs": "Jorge Isaacs escritor",
    "cul-tomas-carrasquilla": "Tomás Carrasquilla escritor",
    "cul-jose-eustasio-rivera": "José Eustasio Rivera escritor",
    # música
    "cul-musicos-destacados": "Shakira singer Colombia",
    "cul-musica-caribe": "vallenato acordeón Colombia",
    "cul-musica-andina": "tiple bambuco Colombia música andina",
    "cul-musica-pacifica": "marimba de chonta Pacífico Colombia",
    "cul-musica-llanera": "arpa llanera joropo",
    "cul-bambuco-origen": "bambuco baile Colombia",
    # festivales
    "cul-fest-vallenato": "Festival de la Leyenda Vallenata Valledupar",
    "cul-fest-blancos-negros": "Carnaval de Negros y Blancos Pasto",
    "cul-fest-feria-cali": "Feria de Cali",
    "cul-fest-feria-manizales": "Feria de Manizales",
    "cul-fest-carnaval-riosucio": "Carnaval de Riosucio Caldas",
    "cul-fest-gaitas": "gaita colombiana instrumento",
    "cul-fest-cultura-wayuu": "cultura wayuu La Guajira",
    "cul-fest-joropo": "joropo baile llanero",
    "cul-fest-mapale": "mapalé danza Colombia",
    "cul-fest-bambuco-neiva": "Festival del Bambuco Neiva Huila",
    "cul-fest-san-francisco-quibdo": "fiestas San Pacho Quibdó Chocó",
    "cul-fest-arepa-huevo": "arepa de huevo Colombia",
    "cul-fest-girara-oro": "música llanera Arauca",
    "cul-fest-bambuco-patiano": "Patía Cauca Colombia",
    "cul-fest-amazonica-lista": "Leticia Amazonas Colombia festival",
    "cul-ibague-capital-musical": "Ibagué Tolima Colombia",
    # símbolos
    "cul-ruana-region": "Ruana Colombia",
    "cul-mochilas-guajira": "Mochilas wayuu",
    "cul-carriel-region": "carriel antioqueño arriero",
    "cul-himno-musica": "Oreste Sindici",
    "cul-himno-coro": "Primera partitura del Himno Nacional de Colombia",
    "cul-himno-primera-estrofa": "Primera partitura del Himno Nacional de Colombia",
    "cul-himno-proclamacion": "Marco Fidel Suárez",
    "cul-nombre-quien": "Congreso de Angostura",
    "cul-escudo-representa": "Escudo de Colombia",
    "cul-escudo-composicion": "Escudo de Colombia",
    "cul-bandera-amarillo": "Flag of Colombia",
    # gastronomía
    "cul-rondon": "rondón San Andrés plato",
    "cul-gastronomia-pacifico-platos": "sancocho de gallina Colombia",
    "cul-gastronomia-ingredientes": "maíz yuca Colombia alimentos",
    "cul-gastronomia-andina-ingredientes": "papa criolla Colombia",
    "cul-gastronomia-pacifico-ingredientes": "pescado Pacífico Colombia cocina",
    "cul-gastronomia-pacifico-deptos": "Chocó Colombia paisaje",
    "cul-region-andina-conforman": "Cordillera de los Andes Colombia",
    # turismo, radio y TV
    "cul-eje-cafetero-turismo": "plantación de café Colombia eje cafetero",
    "cul-amazonia-turismo": "selva amazónica Colombia Leticia",
    "cul-turismo-ciudades-pacifico": "Buenaventura puerto Colombia",
    "cul-turismo-ciudades-principales": "Bogotá skyline",
    "cul-turismo-rural": "agroturismo finca cafetera Colombia",
    "cul-radio-sutatenza": "Radio Sutatenza",
    "cul-television-llegada": "Gustavo Rojas Pinilla",
    "cul-radio-decada": "radio antigua receptor 1920",
}

# Solo conceptos sin referente visual que equivocar.
GROK = {
    "cul-festivales-que-son": "una fiesta popular con música, baile y colores",
    "cul-teatro-etapas": "las etapas del teatro a lo largo del tiempo, de lo clásico a lo contemporáneo",
    "cul-cine-epoca-oro": "una cámara de cine antigua y una claqueta",
    "cul-turismo-cnt": "una oficina de turismo atendiendo viajeros",
    "cul-fest-dulce-bocadillo": "dulces y bocadillos tradicionales en un puesto de feria",
    "cul-nombre-fecha": "un calendario histórico marcando una fecha",
    "cul-nombre-1886": "una constitución antigua sobre un escritorio con pluma",
}

# Reutilizar una imagen de la guía ya verificada, por su número de hoja.
GUIA = {"cul-billete-100mil": 21, "cul-otros-simbolos-culturales": 20}


def _buscar(consulta: str, n: int = 4) -> list[str]:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "list": "search",
        "srnamespace": 6, "srlimit": n, "srsearch": consulta})
    req = urllib.request.Request(url, headers={"User-Agent": IM.UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        hits = json.loads(r.read())["query"]["search"]
    return [h["title"] for h in hits
            if h["title"].lower().endswith((".jpg", ".jpeg", ".png", ".svg"))]


def _info(titulo: str, ancho: int = 520) -> dict | None:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": ancho, "titles": titulo})
    req = urllib.request.Request(url, headers={"User-Agent": IM.UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        pages = json.loads(r.read())["query"]["pages"]
    p = next(iter(pages.values()))
    ii = (p.get("imageinfo") or [{}])[0]
    if not ii.get("thumburl"):
        return None
    import re
    em = ii.get("extmetadata", {})
    autor = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
    return {"url": ii["thumburl"].split("?")[0], "titulo": p["title"],
            "autor": (autor or "desconocido")[:60],
            "licencia": em.get("LicenseShortName", {}).get("value", "?")}


def hojas(manifiesto, ids, destino: Path, por_hoja: int = 12) -> int:
    destino.mkdir(parents=True, exist_ok=True)
    ids = [i for i in ids if i in manifiesto]
    n = 0
    for i in range(0, len(ids), por_hoja):
        lote = ids[i:i + por_hoja]
        rutas, etiq = [], []
        for cid in lote:
            arch = manifiesto[cid]["archivo"]
            ruta = IM.CACHE_DIR / arch
            if not ruta.is_file():
                ruta = MEDIA_DIR / arch
            if ruta.is_file():
                rutas.append(ruta)
                etiq.append(cid[:40])
        if rutas and IM.hoja_contacto(rutas, etiq, destino / f"cul-{i // por_hoja + 1:02d}.jpg"):
            n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheets", type=Path, help="componer hojas de revisión y salir")
    parser.add_argument("--only", help="solo este card id (para probar)")
    args = parser.parse_args()

    manifiesto = yaml.safe_load(IM.MANIFEST.read_text("utf-8")) or {}
    cabecera = IM.MANIFEST.read_text("utf-8").split("\ncon-")[0] + "\n"

    if args.sheets:
        objetivo = list(COMMONS) + list(GROK) + list(GUIA)
        print(f"{hojas(manifiesto, objetivo, args.sheets)} hoja(s) en {args.sheets}/")
        return 0

    IM.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    catalogo = json.load(open("/tmp/catalogo_guia.json")) if Path("/tmp/catalogo_guia.json").is_file() else []

    nuevos = fallos = 0
    for cid, n in GUIA.items():
        if cid in manifiesto or not catalogo:
            continue
        origen = Path(catalogo[n - 1]["archivo"])
        if origen.is_file():
            manifiesto[cid] = {"origen": "guia-oficial", "archivo": origen.name,
                               "muestra": "imagen de la guía oficial",
                               "pagina_guia": catalogo[n - 1]["pagina"], "verificada": False}
            nuevos += 1

    objetivo = {k: v for k, v in COMMONS.items() if not args.only or k == args.only}
    for cid, consulta in objetivo.items():
        if cid in manifiesto:
            continue
        titulos = _buscar(consulta)
        elegido = None
        for t in titulos:
            info = _info(t)
            if info:
                elegido = info
                break
        if not elegido:
            print(f"  sin resultado: {cid}  «{consulta}»", file=sys.stderr)
            fallos += 1
            continue
        destino = IM.CACHE_DIR / f"cul-{cid}.jpg"
        if destino.is_file() or IM.descargar(elegido["url"], destino):
            manifiesto[cid] = {"origen": "commons", "archivo": destino.name,
                               "muestra": elegido["titulo"].replace("File:", "")[:70],
                               "autor": elegido["autor"], "licencia": elegido["licencia"],
                               "verificada": False}
            nuevos += 1
        else:
            fallos += 1

    IM.MANIFEST.write_text(
        cabecera + yaml.safe_dump(manifiesto, allow_unicode=True, sort_keys=True), encoding="utf-8")
    print(f"\n{nuevos} imágenes nuevas, {fallos} sin resolver; manifiesto: {len(manifiesto)}")
    print("Todas quedan verificada: false — revísalas con --sheets antes de darlas por buenas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
