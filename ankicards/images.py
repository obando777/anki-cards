"""Imágenes de referencia: recuperación de Wikimedia, generación con Grok y caché.

La regla que gobierna este módulo salió de una prueba, no de una intuición: se le
pidió a Grok el escudo nacional de Colombia y devolvió uno con cuatro cuarteles
en vez de tres franjas, un capibara inventado y caña de azúcar en lugar de las
banderas. Por eso:

    hecho visual real  ->  SOLO Wikimedia Commons
    concepto abstracto ->  Grok puede ilustrarlo sin nada que equivocar

Nunca se genera un símbolo patrio, un mapa, un billete, un documento ni el rostro
de una persona real, aunque no haya foto disponible.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ankicards.loader import REPO_ROOT

CACHE_DIR = REPO_ROOT / ".image-cache"
MANIFEST = REPO_ROOT / "decks" / "colombia" / "_imagenes.yaml"

ANCHO_MAX = 600          # px; suficiente en un teléfono
CALIDAD = 82             # JPEG
OBJETIVO_KB = 80

UA = ("anki-cards-study-deck/1.0 "
      "(https://github.com/obando777/anki-cards; obando777@gmail.com)")
COMMONS = "https://commons.wikimedia.org/w/api.php"

GROK_MODELO = "grok-imagine-image"
# Coletilla obligatoria: sin ella, Grok mete texto ilegible y símbolos inventados.
GROK_PROHIBIDO = (
    " Estilo ilustración vectorial plana y limpia, fondo claro, sin ningún texto "
    "ni letras ni números, sin banderas, sin escudos, sin mapas, sin logotipos y "
    "sin rostros de personas reales identificables."
)

# Etiquetas cuyo contenido es un concepto sin referente visual que equivocar.
ABSTRACTO = {
    "derechos-fundamentales", "mecanismos-proteccion", "participacion",
    "principios", "ramas", "organismos-control", "organizacion-electoral",
    "organismos-autonomos", "estructura-estado", "defensoria",
}

# Respuestas que son solo una fecha o una cifra: una foto no ayuda a recordarlas.
PURA_CIFRA = re.compile(
    r"^(el |en |entre |aproximadamente |cerca de |alrededor de |desde )?"
    r"(el año |la década de |los años )?"
    r"[\d.,]+\s*(%|km²?|m|metros|millones|horas|días|años|artículos)?"
    r"([\s,y–-]+[\d.,]+\s*(%|km²?|m|metros|millones|horas|días|años)?)*"
    r"[.\s]*$",
    re.I,
)
CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}", re.S)


def _caras(card) -> tuple[str, str]:
    if card.model == "cloze":
        t = card.fields.get("text", "")
        return t, CLOZE.sub(r"\1", t)
    return card.fields.get("front", ""), card.fields.get("back", "")


def clasificar(card) -> str:
    """'real' (necesita foto auténtica) | 'abstracto' (ilustrable) | 'sin-imagen'."""
    pregunta, respuesta = _caras(card)
    if "<img" in pregunta or "<img" in respuesta:
        return "real"                                  # ya curada a mano
    if set(card.tags) & ABSTRACTO:
        return "abstracto"
    if PURA_CIFRA.match(str(respuesta).strip()):
        return "sin-imagen"
    return "real"


# ─── Wikimedia Commons ───────────────────────────────────────────────

def _api(params: dict) -> dict:
    url = COMMONS + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def buscar_commons(consulta: str, limite: int = 6) -> list[dict]:
    """Candidatas para una consulta, con autoría y licencia ya resueltas."""
    try:
        res = _api({"action": "query", "list": "search", "srnamespace": 6,
                    "srlimit": limite, "srsearch": consulta})
    except Exception:
        return []
    titulos = [r["title"] for r in res.get("query", {}).get("search", [])
               if re.search(r"\.(jpe?g|png|svg|webp)$", r["title"], re.I)]
    if not titulos:
        return []
    try:
        info = _api({"action": "query", "prop": "imageinfo",
                     "iiprop": "url|extmetadata", "iiurlwidth": ANCHO_MAX,
                     "titles": "|".join(titulos[:limite])})
    except Exception:
        return []

    salida = []
    for pagina in info.get("query", {}).get("pages", {}).values():
        ii = (pagina.get("imageinfo") or [{}])[0]
        if not ii.get("thumburl"):
            continue
        em = ii.get("extmetadata", {})
        autor = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
        salida.append({
            "titulo": pagina.get("title", ""),
            "url": ii["thumburl"].split("?")[0],
            "pagina": ii.get("descriptionurl", ""),
            "autor": (autor or "desconocido")[:80],
            "licencia": em.get("LicenseShortName", {}).get("value", "?"),
        })
    return salida


def descargar(url: str, destino: Path) -> Path | None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            datos = r.read()
    except Exception:
        return None
    if not datos:
        return None
    return _comprimir(datos, destino)


# ─── Grok ────────────────────────────────────────────────────────────

def _clave_xai() -> str:
    clave = os.environ.get("XAI_API_KEY")
    if not clave:
        env = REPO_ROOT / ".env"
        if env.is_file():
            for linea in env.read_text(encoding="utf-8").splitlines():
                if linea.strip().startswith("XAI_API_KEY="):
                    clave = linea.split("=", 1)[1].strip().strip("'\"")
                    break
    if not clave:
        raise RuntimeError("falta XAI_API_KEY (entorno o .env)")
    return clave


def generar_grok(prompt: str, destino: Path, reintentos: int = 3) -> Path | None:
    """Genera una ilustración. El prompt recibe siempre la coletilla prohibitiva."""
    cuerpo = json.dumps({"model": GROK_MODELO,
                         "prompt": prompt.rstrip() + GROK_PROHIBIDO,
                         "n": 1}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.x.ai/v1/images/generations", data=cuerpo,
        headers={"Authorization": f"Bearer {_clave_xai()}",
                 "Content-Type": "application/json"})
    for intento in range(reintentos):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                datos = json.loads(r.read().decode("utf-8"))
            url = datos["data"][0]["url"]
            return descargar(url, destino)
        except Exception:
            if intento == reintentos - 1:
                raise
            time.sleep(2 ** intento)
    return None


# ─── Compresión y hojas de contacto ──────────────────────────────────

def _comprimir(datos: bytes, destino: Path) -> Path | None:
    """Reescala a ANCHO_MAX y guarda como JPEG. Sin Pillow, guarda tal cual."""
    try:
        from PIL import Image  # noqa: PLC0415 — dependencia opcional
    except ImportError:
        destino.write_bytes(datos)
        return destino

    try:
        im = Image.open(io.BytesIO(datos))
        if im.mode in ("RGBA", "LA", "P"):
            fondo = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            fondo.paste(im, mask=im.split()[-1])
            im = fondo
        else:
            im = im.convert("RGB")
        if im.width > ANCHO_MAX:
            im = im.resize((ANCHO_MAX, round(im.height * ANCHO_MAX / im.width)),
                           Image.LANCZOS)
        destino.parent.mkdir(parents=True, exist_ok=True)
        calidad = CALIDAD
        while True:
            im.save(destino, "JPEG", quality=calidad, optimize=True)
            if destino.stat().st_size <= OBJETIVO_KB * 1024 or calidad <= 55:
                break
            calidad -= 8
        return destino
    except Exception:
        return None


def hoja_contacto(rutas: list[Path], etiquetas: list[str], destino: Path,
                  columnas: int = 4, celda: int = 300) -> Path | None:
    """Rejilla rotulada, para revisar muchas imágenes de una mirada."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    if not rutas:
        return None
    filas = (len(rutas) + columnas - 1) // columnas
    alto_texto = 26
    hoja = Image.new("RGB", (columnas * celda, filas * (celda + alto_texto)),
                     (245, 245, 245))
    dib = ImageDraw.Draw(hoja)
    for i, (ruta, etiqueta) in enumerate(zip(rutas, etiquetas)):
        x, y = (i % columnas) * celda, (i // columnas) * (celda + alto_texto)
        try:
            im = Image.open(ruta).convert("RGB")
            im.thumbnail((celda - 8, celda - 8), Image.LANCZOS)
            hoja.paste(im, (x + (celda - im.width) // 2, y + (celda - im.height) // 2))
        except Exception:
            dib.rectangle([x + 4, y + 4, x + celda - 4, y + celda - 4], outline=(200, 0, 0))
        dib.text((x + 6, y + celda + 4), etiqueta[:44], fill=(20, 20, 20))
    destino.parent.mkdir(parents=True, exist_ok=True)
    hoja.save(destino, "JPEG", quality=88)
    return destino
