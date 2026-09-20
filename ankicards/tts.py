"""Síntesis de voz para las tarjetas: normaliza, cachea y sintetiza.

El YAML nunca lleva etiquetas [sound:]. El audio es un artefacto derivado, como
build/: este módulo convierte el texto de una tarjeta en un mp3 y lo guarda en
.audio-cache/ con un nombre que es el hash de su contenido. Cambiar el texto, la
voz o el modelo produce otro hash, así que solo se regenera lo que cambió.

Uso desde el build:

    from ankicards import tts
    clips = tts.audio_for_deck(deck, voice="nova")   # {card_id: {'front': Path}}
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from ankicards.loader import REPO_ROOT

CACHE_DIR = REPO_ROOT / ".audio-cache"
DEFAULT_VOICE = "coral"
DEFAULT_MODEL = "gpt-4o-mini-tts"

# Las voces de OpenAI son identidades fijas: no se elige el acento por el nombre.
# Lo que sí dirige el acento es el parámetro `instructions` de gpt-4o-mini-tts.
DEFAULT_INSTRUCTIONS = (
    "Habla en español colombiano neutro, con acento de Bogotá. "
    "Voz femenina, clara, cálida y pausada, como una profesora explicando. "
    "Pronuncia la ese completa al final de cada sílaba, sin aspirarla, "
    "y usa entonación andina colombiana, no española ni mexicana."
)

# OpenAI devuelve mp3 a 128 kbps estéreo. Para voz eso es derroche: recodificar a
# 48 kbps mono 24 kHz deja el archivo en un 38 % sin pérdida audible, y es la
# diferencia entre un mazo de 64 MB y uno de 24 MB.
BITRATE = "48k"
SAMPLE_RATE = "24000"

# Lo que una voz española leería mal. El orden importa: km² antes que km.
REPLACEMENTS = [
    (re.compile(r"<br\s*/?>", re.I), ". "),
    (re.compile(r'<img[^>]*>', re.I), " "),
    (re.compile(r"<[^>]+>"), " "),
    (re.compile(r"\bC\.P\.C\.?"), "Constitución Política de Colombia"),
    (re.compile(r"\bD\.C\.?"), "Distrito Capital"),
    (re.compile(r"\bN\.º\s*(\d)"), r"número \1"),
    (re.compile(r"\barts?\.\s*(\d)", re.I), r"artículo \1"),
    (re.compile(r"\bmts\b"), "metros"),
    (re.compile(r"(\d)\s*km²"), r"\1 kilómetros cuadrados"),
    (re.compile(r"\bkm²"), "kilómetros cuadrados"),
    (re.compile(r"(\d)\s*km\b"), r"\1 kilómetros"),
    (re.compile(r"(\d)\s*°C"), r"\1 grados centígrados"),
    (re.compile(r"°C"), "grados centígrados"),
    (re.compile(r"(\d)\s*%"), r"\1 por ciento"),
    (re.compile(r"\$\s*([\d.]+)"), r"\1 pesos"),
    (re.compile(r"\bs\.\s*(XIX|XVIII|XVII|XVI|XV|XX|XXI)\b"), r"siglo \1"),
    (re.compile(r"§\s*[\d.]+"), " "),
    (re.compile(r"\bpp?\.\s*"), "página "),
]

CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}", re.S)

# Artículos, preposiciones y conjunciones que quedan colgando al cortar en el
# primer hueco: sin esto, "…son el {{c1::maíz}}" daría «…son el…». Los verbos
# (son, es, están) NO se quitan: cierran bien el enunciado de una pregunta.
COLGANTES = re.compile(
    r"\s*\b(el|la|los|las|un|una|unos|unas|de|del|en|y|e|o|u|con|por|para|"
    r"su|sus|al|lo|a)\s*$",
    re.I,
)


def normalize(text: str) -> str:
    """Campo de Anki -> texto pronunciable en español."""
    if not text:
        return ""
    t = CLOZE.sub(r"\1", str(text))
    t = html.unescape(t)
    for pattern, repl in REPLACEMENTS:
        t = pattern.sub(repl, t)
    t = re.sub(r'["“”]', " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"(\s*\.)+\s*\.", ".", t)


def stem(text: str) -> str:
    """Enunciado hasta el primer hueco, para el audio de la cara de pregunta.

    Corta en la primera deleción y limpia el artículo o conector que quede
    colgando, de modo que «Los principales ingredientes … son el {{c1::maíz}}…»
    produzca «Los principales ingredientes … son», no «… son el».
    """
    if not text:
        return ""
    head = str(text).split("{{", 1)[0]
    # Si el enunciado presenta la lista con dos puntos, ese es el corte natural:
    # "…son: región {{c1::Caribe}}" -> "…son", no "…son: región".
    if ":" in head:
        head = head.rsplit(":", 1)[0]
    head = re.sub(r"[\s,;:.\-–—]+$", "", head.rstrip())
    previo = None
    while previo != head:                      # "son el" -> "son"; "con el" -> ""
        previo = head
        head = COLGANTES.sub("", head).rstrip(" ,;:.")
    return head


def deletions(text: str) -> list[str]:
    """Lo que cada deleción oculta. Sirve para comprobar que el clip de
    pregunta no dice ninguna de estas palabras."""
    return [m.group(1) for m in CLOZE.finditer(str(text or ""))]


def answer(text: str) -> str:
    """Solo lo que las delaciones ocultan, encadenado en una frase.

    El clip de respuesta ya no repite el enunciado: ese lo lleva el campo Text y
    vuelve a sonar al revelar, así que aquí basta con lo que faltaba. Se obtiene
    "Caribe, Andina, Pacífica, Orinoquía y Amazónica" en vez de la frase entera.
    """
    partes = [p.strip() for p in deletions(text) if p and p.strip()]
    if not partes:
        return ""
    vistos, unicas = set(), []
    for p in partes:                       # las listas repiten "región X, región Y"
        if p.lower() not in vistos:
            vistos.add(p.lower())
            unicas.append(p)
    if len(unicas) == 1:
        return unicas[0] + "."
    return ", ".join(unicas[:-1]) + " y " + unicas[-1] + "."


def cloze_numbers(text: str) -> set[str]:
    """Números de deleción distintos presentes en el texto."""
    return set(re.findall(r"\{\{c(\d+)::", str(text or "")))


def clip_id(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    instructions: str = DEFAULT_INSTRUCTIONS,
) -> str:
    """Nombre de archivo determinista.

    El hash incluye la voz, el modelo y las instrucciones de acento: cambiar
    cualquiera de los tres invalida la caché y obliga a regenerar.
    """
    key = f"{normalize(text)}|{voice}|{model}|{instructions}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:16]


def _client():
    from openai import OpenAI  # noqa: PLC0415 — dependencia opcional del grupo `audio`

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        env = REPO_ROOT / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
                    break
    if not key:
        raise RuntimeError("falta OPENAI_API_KEY (en el entorno o en .env)")
    return OpenAI(api_key=key)


def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    cache_dir: Path = CACHE_DIR,
    client=None,
    retries: int = 3,
    instructions: str = DEFAULT_INSTRUCTIONS,
) -> Path | None:
    """Devuelve el mp3 del texto, generándolo solo si no está en caché."""
    spoken = normalize(text)
    if not spoken:
        return None

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{clip_id(text, voice, model, instructions)}.mp3"
    if out.is_file() and out.stat().st_size > 0:
        return out

    client = client or _client()
    for attempt in range(retries):
        try:
            kwargs = dict(model=model, voice=voice, input=spoken, response_format="mp3")
            if instructions:
                kwargs["instructions"] = instructions
            resp = client.audio.speech.create(**kwargs)
            data = resp.read() if hasattr(resp, "read") else resp.content
            if not data:
                raise RuntimeError("la API devolvió audio vacío")
            # Se escribe primero a un temporal: así un fallo a mitad no deja un
            # mp3 truncado en la caché que luego se daría por bueno.
            tmp = out.with_suffix(".part")
            tmp.write_bytes(data)
            _compress(tmp, out)
            return out
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None


def _compress(src: Path, dest: Path) -> None:
    """Recodifica a mono de baja tasa. Sin ffmpeg, se guarda el original."""
    if not shutil.which("ffmpeg"):
        src.replace(dest)
        return
    done = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
         "-codec:a", "libmp3lame", "-b:a", BITRATE, "-ac", "1", "-ar", SAMPLE_RATE,
         str(dest)],
        capture_output=True,
    )
    if done.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
        src.replace(dest)          # ffmpeg falló: mejor el original que nada
    else:
        src.unlink(missing_ok=True)


def sides_for_card(card) -> dict[str, str]:
    """Qué texto se lee en cada cara, según el modelo de la tarjeta.

    - `text`     -> solo lo que ocultan las delaciones; va a Extra (solo `afmt`).
    - `question` -> enunciado hasta el primer hueco; va a Text, que se renderiza
      en ambas caras. No revela nada, así que puede sonar al preguntar, y al
      revelar encadena con el clip de respuesta. Solo se genera si la nota tiene
      un único cN; con varios, cada tarjeta esconde un hueco distinto y un clip
      único no podría servir para todas.
    """
    if card.model != "cloze":
        return {
            "front": card.fields.get("front", ""),
            "back": card.fields.get("back", ""),
        }

    texto = card.fields.get("text", "")

    # El clip de pregunta solo sirve si la nota genera UNA tarjeta. Con varios
    # cN cada tarjeta esconde un hueco distinto y un clip único no podría
    # marcar el correcto en todas.
    enunciado = stem(texto) if len(cloze_numbers(texto)) <= 1 else ""

    if enunciado:
        # Hay enunciado hablado: la respuesta solo necesita decir lo que faltaba,
        # y al revelar se oye enunciado + respuesta encadenados.
        return {"question": enunciado, "text": answer(texto) or texto}

    # Sin enunciado hablado, la respuesta tiene que valerse sola: frase completa.
    return {"text": texto}


def audio_for_deck(
    deck,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    cache_dir: Path = CACHE_DIR,
    client=None,
    progress=None,
    workers: int = 8,
    instructions: str = DEFAULT_INSTRUCTIONS,
) -> dict[str, dict[str, Path]]:
    """{card_id: {'front': Path, 'back': Path}} para todo un mazo.

    Sintetiza en paralelo: en serie, 860 clips tardan casi media hora.
    """
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    client = client or _client()
    jobs = [
        (card.id, side, text)
        for card in deck.cards
        for side, text in sides_for_card(card).items()
        if normalize(text)
    ]

    result: dict[str, dict[str, Path]] = {}
    done = 0

    def run(job):
        cid, side, text = job
        return cid, side, synthesize(
            text, voice, model, cache_dir, client, instructions=instructions
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for cid, side, path in pool.map(run, jobs):
            if path:
                result.setdefault(cid, {})[side] = path
            done += 1
            if progress:
                progress(done, len(jobs))
    return result


def plan(decks, voice: str = DEFAULT_VOICE, model: str = DEFAULT_MODEL,
         cache_dir: Path = CACHE_DIR,
         instructions: str = DEFAULT_INSTRUCTIONS) -> tuple[int, int, int]:
    """(clips totales, ya en caché, por generar) sin llamar a la API."""
    cache_dir = Path(cache_dir)
    total = cached = 0
    for deck in decks:
        for card in deck.cards:
            for text in sides_for_card(card).values():
                if not normalize(text):
                    continue
                total += 1
                if (cache_dir / f"{clip_id(text, voice, model, instructions)}.mp3").is_file():
                    cached += 1
    return total, cached, total - cached
