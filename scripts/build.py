#!/usr/bin/env python3
"""Build decks/**/*.yaml into build/*.apkg.

    uv run scripts/build.py                     # every deck
    uv run scripts/build.py decks/spanish       # one folder
    uv run scripts/build.py decks/a.yaml b.yaml # specific files

Nothing is written unless every requested deck validates, so build/ never holds
a half-updated set.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ankicards.builder import BUILD_DIR, build_deck  # noqa: E402
from ankicards.loader import DeckError, load_all_decks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="deck files or folders to build (default: all of decks/)",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=BUILD_DIR,
        help=f"output directory (default: {BUILD_DIR.name}/)",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="synthesize speech for each card and embed it (needs --group audio)",
    )
    parser.add_argument("--voice", default="coral", help="TTS voice (default: coral)")
    parser.add_argument(
        "--tts-model", default="gpt-4o-mini-tts", help="TTS model (default: gpt-4o-mini-tts)"
    )
    args = parser.parse_args()

    try:
        decks = load_all_decks(args.paths or None)
    except DeckError as exc:
        print(f"{len(exc.problems)} problem(s) found — nothing was built:\n", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    audio_by_deck = {}
    if args.audio:
        from ankicards import tts  # noqa: PLC0415 — optional `audio` dependency group

        pending = tts.plan(decks, args.voice, args.tts_model)[2]
        if pending:
            print(f"  synthesizing {pending} new clip(s)…")
        client = tts._client()
        for deck in decks:
            audio_by_deck[deck.name] = tts.audio_for_deck(
                deck, args.voice, args.tts_model, client=client
            )

    total = 0
    for deck in decks:
        out_path = build_deck(deck, args.out, audio_by_deck.get(deck.name))
        count = len(deck.cards)
        total += count
        print(f"  {deck.name:<40} {count:>4} card(s)  ->  {out_path.name}")

    print(f"\nBuilt {len(decks)} deck(s), {total} card(s) into {args.out}/")
    print("Import into Anki: File > Import, or just double-click the .apkg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
