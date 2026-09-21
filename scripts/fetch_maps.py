#!/usr/bin/env python3
"""Asigna a cada tarjeta de Geografía el mapa que le corresponde.

    uv run --group images --group extract scripts/fetch_maps.py

Una pregunta de geografía sin mapa deja a medias lo que pregunta: «Antioquia →
Medellín» no dice dónde queda Antioquia. Este script resuelve tres fuentes de
mapas y las reparte por una cascada de reglas, de lo específico a lo general.

Las tarjetas que ya tienen una foto buena la conservan: cambiar el jaguar de la
fauna amazónica por un mapa sería empeorarla.
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
from ankicards.loader import MEDIA_DIR, load_all_decks  # noqa: E402

GEO = Path("decks/colombia/02-geografia.yaml")
GUIA = Path("raw_input/colombia/Guia-oficial-Colombia-nuestra-casa.pdf")

# Páginas de la guía con la infografía-resumen de cada región: mapa coloreado,
# recuadro localizador, departamentos numerados con capitales y datos.
REGIONES = {"amazonica": 63, "andina": 69, "caribe": 75, "pacifica": 81, "orinoquia": 86}

RELIEVE = "File:Colombia relief location map.jpg"


def _commons_urls(titulos: list[str], ancho: int = 520) -> dict[str, str]:
    """thumburl de cada título. Ojo: el prefijo File: es obligatorio."""
    salida: dict[str, str] = {}
    for i in range(0, len(titulos), 12):
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url", "iiurlwidth": ancho, "titles": "|".join(titulos[i:i + 12]),
        })
        req = urllib.request.Request(url, headers={"User-Agent": IM.UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            pages = json.loads(r.read())["query"]["pages"]
        for p in pages.values():
            enlace = (p.get("imageinfo") or [{}])[0].get("thumburl")
            if enlace:
                salida[p["title"]] = enlace.split("?")[0]
    return salida


def descargar_localizadores(cards) -> dict[str, dict]:
    """Un mapa de Colombia con el departamento en rojo, por cada par depto↔capital."""
    pares = {}
    for c in cards:
        if c.id.startswith("geo-cap-"):
            nombre = c.fields["front"].split("(")[0].strip()
            pares[c.id] = f"File:Colombia - {nombre}.svg"
    urls = _commons_urls(list(pares.values()))
    salida = {}
    for cid, titulo in pares.items():
        if titulo not in urls:
            print(f"  sin localizador: {titulo}", file=sys.stderr)
            continue
        destino = IM.CACHE_DIR / f"mapa-{cid}.jpg"
        if destino.is_file() or IM.descargar(urls[titulo], destino):
            salida[cid] = {"origen": "commons-mapa", "archivo": destino.name,
                           "muestra": f"mapa localizador de {pares[cid][11:-4]}",
                           "verificada": True}
    return salida


def extraer_regiones() -> dict[str, dict]:
    """Las infografías-resumen de región, renderizadas desde la guía oficial."""
    import pymupdf  # noqa: PLC0415 — grupo `extract`

    doc = pymupdf.open(GUIA)
    salida = {}
    for region, pagina in REGIONES.items():
        destino = IM.CACHE_DIR / f"mapa-region-{region}.jpg"
        if not destino.is_file():
            IM._comprimir(doc[pagina - 1].get_pixmap(dpi=150).tobytes("png"), destino)
        salida[region] = {"origen": "guia-mapa", "archivo": destino.name,
                          "pagina_guia": pagina,
                          "muestra": f"mapa de la región {region}", "verificada": True}
    return salida


def descargar_relieve() -> dict | None:
    urls = _commons_urls([RELIEVE], ancho=600)
    if RELIEVE not in urls:
        return None
    destino = IM.CACHE_DIR / "mapa-relieve.jpg"
    if destino.is_file() or IM.descargar(urls[RELIEVE], destino):
        return {"origen": "commons-mapa", "archivo": destino.name,
                "muestra": "mapa de relieve de Colombia", "verificada": True}
    return None


def hojas_de_revision(manifiesto, destino: Path, por_hoja: int = 12) -> int:
    """Rejillas rotuladas para revisar los mapas de un vistazo.

    Mirar es el único control que de verdad atrapa errores: así se vio que la
    tarjeta del ave nacional había recibido una foto de capibaras.
    """
    geo = yaml.safe_load(GEO.read_text("utf-8"))
    ids = [c["id"] for c in geo["cards"] if c["id"] in manifiesto]
    destino.mkdir(parents=True, exist_ok=True)
    hechas = 0
    for i in range(0, len(ids), por_hoja):
        lote = ids[i:i + por_hoja]
        rutas, etiquetas = [], []
        for cid in lote:
            archivo = manifiesto[cid]["archivo"]
            ruta = IM.CACHE_DIR / archivo
            if not ruta.is_file():
                ruta = MEDIA_DIR / archivo
            if ruta.is_file():
                rutas.append(ruta)
                etiquetas.append(cid[:40])
        if rutas and IM.hoja_contacto(rutas, etiquetas, destino / f"geo-{i // por_hoja + 1:02d}.jpg"):
            hechas += 1
    return hechas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sheets",
        type=Path,
        help="write labelled contact sheets here instead of resolving maps",
    )
    args = parser.parse_args()

    if args.sheets:
        manifiesto = yaml.safe_load(IM.MANIFEST.read_text("utf-8")) or {}
        print(f"{hojas_de_revision(manifiesto, args.sheets)} hoja(s) en {args.sheets}/")
        return 0

    deck = load_all_decks([GEO])[0]
    manifiesto = yaml.safe_load(IM.MANIFEST.read_text("utf-8")) or {}
    cabecera = IM.MANIFEST.read_text("utf-8").split("\ncon-")[0] + "\n"

    IM.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print("resolviendo mapas…")
    localizadores = descargar_localizadores(deck.cards)
    print(f"  {len(localizadores)} localizadores de departamento")
    regiones = extraer_regiones()
    print(f"  {len(regiones)} infografías de región")
    relieve = descargar_relieve()
    print(f"  relieve: {'ok' if relieve else 'no disponible'}")

    generales = {
        "politico": {"origen": "commons-mapa", "archivo": "mapa-departamentos.png",
                     "muestra": "mapa político de Colombia", "verificada": True},
        "naturales": {"origen": "commons-mapa", "archivo": "mapa-regiones-naturales.png",
                      "muestra": "mapa de las regiones naturales", "verificada": True},
    }

    nuevos = 0
    for card in deck.cards:
        tags = set(card.tags)
        entrada = None
        if card.id in localizadores:
            # El localizador pisa cualquier imagen previa: en un par
            # departamento↔capital, saber dónde queda es la mitad de la pregunta,
            # y una foto del paisaje no la responde.
            entrada = localizadores[card.id]
        elif card.id in manifiesto:        # ya tiene imagen buena: no se pisa
            continue
        else:
            for region in REGIONES:
                if region in tags:
                    entrada = regiones[region]
                    break
            if entrada is None:
                if tags & {"insular", "regiones"}:
                    entrada = generales["naturales"]
                elif tags & {"geografia-fisica", "clima", "pisos-termicos"} and relieve:
                    entrada = relieve
                else:
                    entrada = generales["politico"]
        manifiesto[card.id] = entrada
        nuevos += 1

    IM.MANIFEST.write_text(
        cabecera + yaml.safe_dump(manifiesto, allow_unicode=True, sort_keys=True),
        encoding="utf-8")
    print(f"\n{nuevos} tarjetas de Geografía recibieron mapa; manifiesto: {len(manifiesto)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
