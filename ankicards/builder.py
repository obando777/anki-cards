"""Turn a loaded Deck into an .apkg file."""

from __future__ import annotations

from pathlib import Path

import genanki

from ankicards.loader import MEDIA_DIR, REPO_ROOT, Deck
from ankicards.models import MODEL_FIELDS, MODELS

BUILD_DIR = REPO_ROOT / "build"


def _note(deck: Deck, card, audio: dict[str, Path] | None = None) -> genanki.Note:
    model = MODELS[card.model]
    keys = MODEL_FIELDS[card.model]
    values = [card.fields[key] for key in keys]

    # El audio se inyecta aquí, no en el YAML: la fuente se queda con texto puro
    # y los clips son derivados, como build/. Anki reproduce [sound:] solo.
    audio = audio or {}

    if card.model == "cloze":
        # Text se renderiza en ambas caras, así que solo puede llevar el clip del
        # ENUNCIADO, que no revela nada. El de la respuesta va a Extra, que la
        # plantilla usa únicamente en `afmt`. Al revelar suenan encadenados.
        if audio.get("question"):
            values[0] += f' [sound:{audio["question"].name}]'
        extra = card.notes
        if audio.get("text"):
            extra += f' [sound:{audio["text"].name}]'
        values.append(extra)
    else:
        for index, key in enumerate(keys):
            clip = audio.get(key)
            if clip:
                values[index] += f" [sound:{clip.name}]"
        if card.notes:
            values[-1] += f'<div class="notes">{card.notes}</div>'

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
) -> Path:
    """Write deck to out_dir/<deck>.apkg and return the path.

    `audio` maps card id -> {field key: mp3 path}; when given, each clip is
    referenced with [sound:] and bundled into the package.
    """
    audio = audio or {}
    anki_deck = genanki.Deck(deck.deck_id, deck.name)
    for card in deck.cards:
        anki_deck.add_note(_note(deck, card, audio.get(card.id)))

    package = genanki.Package(anki_deck)
    clips = sorted({str(p) for sides in audio.values() for p in sides.values()})
    package.media_files = [str(MEDIA_DIR / name) for name in sorted(deck.media())] + clips

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / deck.filename
    package.write_to_file(str(out_path))
    return out_path
