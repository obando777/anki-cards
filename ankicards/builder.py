"""Turn a loaded Deck into an .apkg file."""

from __future__ import annotations

from pathlib import Path

import genanki

from ankicards.loader import MEDIA_DIR, REPO_ROOT, Deck
from ankicards.models import MODEL_FIELDS, MODELS

BUILD_DIR = REPO_ROOT / "build"


def _note(deck: Deck, card) -> genanki.Note:
    model = MODELS[card.model]
    values = [card.fields[key] for key in MODEL_FIELDS[card.model]]

    if card.model == "cloze":
        values.append(card.notes)
    elif card.notes:
        values[-1] += f'<div class="notes">{card.notes}</div>'

    return genanki.Note(
        model=model,
        fields=values,
        tags=card.tags,
        # Deterministic: the same (deck, card id) always yields the same GUID, so
        # re-importing updates the existing note instead of duplicating it.
        guid=genanki.guid_for(deck.name, card.id),
    )


def build_deck(deck: Deck, out_dir: Path = BUILD_DIR) -> Path:
    """Write deck to out_dir/<deck>.apkg and return the path."""
    anki_deck = genanki.Deck(deck.deck_id, deck.name)
    for card in deck.cards:
        anki_deck.add_note(_note(deck, card))

    package = genanki.Package(anki_deck)
    package.media_files = [str(MEDIA_DIR / name) for name in sorted(deck.media())]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / deck.filename
    package.write_to_file(str(out_path))
    return out_path
