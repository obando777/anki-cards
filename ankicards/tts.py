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

    En cloze no se genera audio de pregunta: una nota con c1..c5 produce cinco
    tarjetas y una sola etiqueta [sound:] sonaría igual en todas, así que no
    podría decir "..." en el hueco correcto de cada una. Se lee la frase
    completa al revelar.
    """
    if card.model == "cloze":
        return {"text": card.fields.get("text", "")}
    return {"front": card.fields.get("front", ""), "back": card.fields.get("back", "")}


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
