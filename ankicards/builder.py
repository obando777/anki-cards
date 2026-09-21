"""Turn a loaded Deck into an .apkg file."""

from __future__ import annotations

from pathlib import Path

import genanki

from ankicards.loader import MEDIA_DIR, REPO_ROOT, Deck
from ankicards.models import MODEL_FIELDS, MODELS

BUILD_DIR = REPO_ROOT / "build"


# Qué se le dice al estudiante sobre la procedencia de lo que está mirando. La
# distinción que importa es foto auténtica contra ilustración evocadora.
ATRIBUCION = {
    "guia-oficial": "Foto: guía oficial «Colombia, nuestra casa», p. {pagina_guia}",
    "commons": "Foto: {autor} · {licencia} · Wikimedia Commons",
    "grok": "Ilustración generada — esquemática, no documental",
    "grok-relleno": "Ilustración generada — evocadora, NO es una foto del original",
    "commons-mapa": "Mapa: Wikimedia Commons",
    "guia-mapa": "Mapa: guía oficial «Colombia, nuestra casa», p. {pagina_guia}",
    "commons-mapa-rotulado": "Mapa: {autor} · {licencia} · Wikimedia Commons — rótulos añadidos",
}


def _note(
    deck: Deck,
    card,
    audio: dict[str, Path] | None = None,
    imagen: dict | None = None,
) -> genanki.Note:
    model = MODELS[card.model]
    keys = MODEL_FIELDS[card.model]
    values = [card.fields[key] for key in keys]

    # El audio se inyecta aquí, no en el YAML: la fuente se queda con texto puro
    # y los clips son derivados, como build/. Anki reproduce [sound:] solo.
    audio = audio or {}

    # La imagen y su procedencia van en la cara de RESPUESTA. Misma trampa que
    # con el audio: un campo se renderiza donde la plantilla lo ponga.
    etiqueta_img = nota_img = ""
    if imagen and imagen.get("ruta"):
        etiqueta_img = f'<br><img src="{Path(imagen["ruta"]).name}">'
        plantilla = ATRIBUCION.get(imagen.get("origen", ""), "")
        if plantilla:
            nota_img = "<br>" + plantilla.format(**imagen)

    if card.model == "cloze":
        # Text se renderiza en ambas caras, así que solo puede llevar el clip del
        # ENUNCIADO, que no revela nada. El de la respuesta va a Extra, que la
        # plantilla usa únicamente en `afmt`. Al revelar suenan encadenados.
        if audio.get("question"):
            values[0] += f' [sound:{audio["question"].name}]'
        extra = card.notes + nota_img
        if audio.get("text"):
            extra += f' [sound:{audio["text"].name}]'
        values.append(extra + etiqueta_img)
    else:
        for index, key in enumerate(keys):
            clip = audio.get(key)
            if clip:
                values[index] += f" [sound:{clip.name}]"
        values[-1] += etiqueta_img
        if card.notes or nota_img:
            values[-1] += f'<div class="notes">{card.notes}{nota_img}</div>'

    return genanki.Note(
        model=model,
        fields=values,
        tags=card.tags,
        # Deterministic: the same (deck, card id) always yields the same GUID, so
        # re-importing updates the existing note instead of duplicating it.
        guid=genanki.guid_for(deck.name, card.id),
    )


def build_deck(
    deck: Deck,
    out_dir: Path = BUILD_DIR,
    audio: dict[str, dict[str, Path]] | None = None,
    images: dict[str, dict] | None = None,
) -> Path:
    """Write deck to out_dir/<deck>.apkg and return the path.

    `audio` maps card id -> {field key: mp3 path}; when given, each clip is
    referenced with [sound:] and bundled into the package.
    """
    audio = audio or {}
    images = images or {}
    anki_deck = genanki.Deck(deck.deck_id, deck.name)
    for card in deck.cards:
        anki_deck.add_note(_note(deck, card, audio.get(card.id), images.get(card.id)))

    package = genanki.Package(anki_deck)
    clips = sorted({str(p) for sides in audio.values() for p in sides.values()})
    fotos = sorted({str(i["ruta"]) for i in images.values() if i.get("ruta")})
    package.media_files = (
        [str(MEDIA_DIR / name) for name in sorted(deck.media())] + clips + fotos
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / deck.filename
    package.write_to_file(str(out_path))
    return out_path
