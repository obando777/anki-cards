"""Parse deck YAML files into validated Deck/Card objects.

A deck file looks like:

    deck: Spanish::Vocabulary
    deck_id: 1607392319
    model: basic          # optional default for every card
    tags: [spanish]       # optional, applied to every card

    cards:
      - id: es-perro
        front: el perro
        back: the dog
        tags: [animals]

Validation gathers *all* problems in a file before reporting, so a single run
tells you everything that needs fixing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ankicards.models import MODEL_FIELDS, MODELS

REPO_ROOT = Path(__file__).resolve().parent.parent
DECKS_DIR = REPO_ROOT / "decks"
MEDIA_DIR = REPO_ROOT / "media"

# Anki references media by bare filename: <img src="x.png"> and [sound:x.mp3].
MEDIA_PATTERNS = (
    re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r"\[sound:([^\]]+)\]"),
)
CLOZE_PATTERN = re.compile(r"\{\{c\d+::")

DECK_KEYS = {"deck", "deck_id", "model", "tags", "cards"}
CARD_META_KEYS = {"id", "model", "tags", "notes"}


class DeckError(Exception):
    """One or more deck files failed validation."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


@dataclass
class Card:
    id: str
    model: str
    fields: dict[str, str]
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def media(self) -> set[str]:
        """Bare filenames this card references."""
        found: set[str] = set()
        for value in (*self.fields.values(), self.notes):
            for pattern in MEDIA_PATTERNS:
                found.update(pattern.findall(value))
        return found


@dataclass
class Deck:
    name: str
    deck_id: int
    path: Path
    cards: list[Card] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """Deck name as a safe .apkg filename: Spanish::Verbs -> Spanish__Verbs."""
        safe = self.name.replace("::", "__")
        return re.sub(r"[^\w.\- ]", "_", safe) + ".apkg"

    def media(self) -> set[str]:
        found: set[str] = set()
        for card in self.cards:
            found |= card.media()
        return found


def _as_tags(value, where: str, problems: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return value.split()
    if isinstance(value, list) and all(isinstance(t, str) for t in value):
        return list(value)
    problems.append(f"{where}: 'tags' must be a list of strings or a space-separated string")
    return []


def _stringify(value) -> str:
    """YAML gives ints/bools/floats for bare values; Anki fields are text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load_deck(path: Path) -> Deck:
    """Load and validate one deck file. Raises DeckError listing every problem."""
    path = Path(path)
    rel = _rel(path)
    problems: list[str] = []

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DeckError([f"{rel}: invalid YAML: {exc}"]) from exc

    if not isinstance(raw, dict):
        raise DeckError([f"{rel}: top level must be a mapping with 'deck', 'deck_id' and 'cards'"])

    unknown = set(raw) - DECK_KEYS
    if unknown:
        problems.append(f"{rel}: unknown top-level key(s): {', '.join(sorted(unknown))}")

    name = raw.get("deck")
    if not isinstance(name, str) or not name.strip():
        problems.append(f"{rel}: 'deck' is required and must be a non-empty string (the deck name)")
        name = "<unnamed>"

    deck_id = raw.get("deck_id")
    if not isinstance(deck_id, int) or isinstance(deck_id, bool):
        problems.append(
            f"{rel}: 'deck_id' is required and must be an integer. "
            f"Generate one with: uv run scripts/new_deck.py"
        )
        deck_id = 0

    default_model = raw.get("model", "basic")
    if default_model not in MODELS:
        problems.append(
            f"{rel}: unknown model {default_model!r}; expected one of {', '.join(sorted(MODELS))}"
        )
        default_model = "basic"

    deck_tags = _as_tags(raw.get("tags"), rel, problems)

    raw_cards = raw.get("cards")
    if raw_cards is None:
        raw_cards = []
    if not isinstance(raw_cards, list):
        problems.append(f"{rel}: 'cards' must be a list")
        raw_cards = []

    cards: list[Card] = []
    seen: dict[str, int] = {}

    for index, entry in enumerate(raw_cards, start=1):
        where = f"{rel}: card #{index}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping")
            continue

        card_id = entry.get("id")
        if not isinstance(card_id, str) or not card_id.strip():
            problems.append(
                f"{where}: 'id' is required and must be a non-empty string "
                f"(it is what keeps the card stable across re-imports)"
            )
            continue
        card_id = card_id.strip()
        where = f"{rel}: card '{card_id}'"

        if card_id in seen:
            problems.append(f"{where}: duplicate id, already used by card #{seen[card_id]}")
            continue
        seen[card_id] = index

        model = entry.get("model", default_model)
        if model not in MODELS:
            problems.append(
                f"{where}: unknown model {model!r}; expected one of {', '.join(sorted(MODELS))}"
            )
            continue

        expected = MODEL_FIELDS[model]
        allowed = CARD_META_KEYS | set(expected)
        extra = set(entry) - allowed
        if extra:
            problems.append(
                f"{where}: key(s) {', '.join(sorted(extra))} are not valid for model "
                f"'{model}' (it uses: {', '.join(expected)})"
            )

        fields_: dict[str, str] = {}
        missing = []
        for key in expected:
            value = entry.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(key)
            else:
                fields_[key] = _stringify(value)
        if missing:
            problems.append(f"{where}: model '{model}' requires {', '.join(missing)}")
            continue

        if model == "cloze" and not CLOZE_PATTERN.search(fields_["text"]):
            problems.append(
                f"{where}: cloze card has no {{{{c1::...}}}} deletion — "
                f"it would produce no cards in Anki"
            )

        notes = entry.get("notes")
        notes = _stringify(notes).strip() if notes is not None else ""

        cards.append(
            Card(
                id=card_id,
                model=model,
                fields=fields_,
                tags=sorted(set(deck_tags) | set(_as_tags(entry.get("tags"), where, problems))),
                notes=notes,
            )
        )

    if not cards and not problems:
        problems.append(f"{rel}: no cards defined")

    deck = Deck(name=name, deck_id=deck_id, path=path, cards=cards)
    problems.extend(_check_media(deck, rel))

    if problems:
        raise DeckError(problems)
    return deck


def _check_media(deck: Deck, rel: str) -> list[str]:
    problems = []
    for card in deck.cards:
        for filename in sorted(card.media()):
            if not (MEDIA_DIR / filename).is_file():
                problems.append(
                    f"{rel}: card '{card.id}' references media/{filename}, which does not exist"
                )
    return problems


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _es_mazo(path: Path) -> bool:
    """Los .yaml que empiezan por _ son datos auxiliares, no mazos.

    Sin esto, un manifiesto guardado junto a los mazos se intenta cargar como
    uno de ellos y la validación falla pidiéndole un `deck:`.
    """
    return not path.name.startswith("_")


def deck_files(paths: list[Path] | None = None) -> list[Path]:
    """Deck files to process: the given paths, or every .yaml under decks/."""
    if paths:
        resolved: list[Path] = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                resolved.extend(
                    sorted(f for f in list(p.rglob("*.yaml")) + list(p.rglob("*.yml"))
                           if _es_mazo(f))
                )
            else:
                resolved.append(p)
        return resolved
    todos = list(DECKS_DIR.rglob("*.yaml")) + list(DECKS_DIR.rglob("*.yml"))
    return sorted(f for f in todos if _es_mazo(f))


def load_all_decks(paths: list[Path] | None = None) -> list[Deck]:
    """Load every deck, reporting problems from all files at once.

    Also catches deck_id collisions across files — two decks sharing an ID would
    merge into one on import.
    """
    files = deck_files(paths)
    if not files:
        raise DeckError([f"no deck files found (looked for *.yaml under {_rel(DECKS_DIR)}/)"])

    decks: list[Deck] = []
    problems: list[str] = []
    for path in files:
        if not path.is_file():
            problems.append(f"{_rel(path)}: no such file")
            continue
        try:
            decks.append(load_deck(path))
        except DeckError as exc:
            problems.extend(exc.problems)

    by_id: dict[int, Deck] = {}
    by_name: dict[str, Deck] = {}
    for deck in decks:
        if deck.deck_id in by_id:
            problems.append(
                f"{_rel(deck.path)}: deck_id {deck.deck_id} is already used by "
                f"{_rel(by_id[deck.deck_id].path)} — each deck needs its own"
            )
        else:
            by_id[deck.deck_id] = deck
        if deck.name in by_name:
            problems.append(
                f"{_rel(deck.path)}: deck name {deck.name!r} is already used by "
                f"{_rel(by_name[deck.name].path)}"
            )
        else:
            by_name[deck.name] = deck

    if problems:
        raise DeckError(problems)
    return decks
