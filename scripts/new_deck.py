#!/usr/bin/env python3
"""Scaffold a new deck file with a fresh, stable deck_id.

    uv run scripts/new_deck.py "Spanish::Verbs"
    uv run scripts/new_deck.py "Python::Stdlib" --model cloze --path decks/python/stdlib.yaml

The deck_id it generates is written once and must never change afterwards —
Anki uses it to recognise the deck on re-import.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ankicards.loader import DECKS_DIR, REPO_ROOT, deck_files  # noqa: E402
from ankicards.models import MODELS  # noqa: E402

TEMPLATES = {
    "basic": """  - id: {slug}-001
    front: Front of the first card
    back: Back of the first card
    tags: [example]
""",
    "basic-reversed": """  - id: {slug}-001
    front: Front of the first card
    back: Back of the first card
    tags: [example]
""",
    "cloze": """  - id: {slug}-001
    text: The capital of France is {{{{c1::Paris}}}}.
    notes: One deletion per fact you want tested separately.
    tags: [example]
""",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "deck"


def used_deck_ids() -> set[int]:
    """Read existing deck_ids straight from the files, so a broken deck elsewhere
    doesn't stop you scaffolding a new one."""
    ids = set()
    for path in deck_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*deck_id:\s*(\d+)", line)
            if match:
                ids.add(int(match.group(1)))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="deck name; use :: for subdecks, e.g. Spanish::Verbs")
    parser.add_argument(
        "--model",
        default="basic",
        choices=sorted(MODELS),
        help="default note model for the deck (default: basic)",
    )
    parser.add_argument("--path", type=Path, help="where to write it (default: derived from name)")
    args = parser.parse_args()

    slug = slugify(args.name.replace("::", "-"))
    if args.path:
        path = args.path
    else:
        parts = [slugify(p) for p in args.name.split("::")]
        path = DECKS_DIR.joinpath(*parts).with_suffix(".yaml")

    if path.exists():
        print(f"error: {path} already exists", file=sys.stderr)
        return 1

    taken = used_deck_ids()
    while True:
        deck_id = random.randrange(1 << 30, 1 << 31)
        if deck_id not in taken:
            break

    content = f"""# {args.name}
#
# deck_id is permanent — changing it makes Anki treat this as a brand new deck.
# Each card's `id` is likewise permanent: edit a card's text freely and the next
# import updates it in place; change its id and you get a second, separate card.

deck: {args.name}
deck_id: {deck_id}
model: {args.model}
tags: [{slug}]

cards:
{TEMPLATES[args.model].format(slug=slug)}"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    try:
        shown = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = path
    print(f"Created {shown} (deck_id {deck_id})")
    print(f"Next: edit it, then `uv run scripts/build.py {shown}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
