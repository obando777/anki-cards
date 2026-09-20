#!/usr/bin/env python3
"""Check deck YAML without building anything.

    uv run scripts/validate.py
    uv run scripts/validate.py decks/spanish

Exits non-zero and lists every problem if anything is wrong.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ankicards.loader import DeckError, load_all_decks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="deck files or folders to check (default: all of decks/)",
    )
    args = parser.parse_args()

    try:
        decks = load_all_decks(args.paths or None)
    except DeckError as exc:
        print(f"{len(exc.problems)} problem(s):\n", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    total = sum(len(d.cards) for d in decks)
    for deck in decks:
        print(f"  ok  {deck.name:<40} {len(deck.cards):>4} card(s)")
    print(f"\n{len(decks)} deck(s), {total} card(s), no problems.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
