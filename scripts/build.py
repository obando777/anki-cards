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
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ankicards.builder import BUILD_DIR, build_deck  # noqa: E402
from ankicards.loader import DeckError, load_all_decks  # noqa: E402


def _configured_drop() -> Path | None:
    """Drop directory from the environment, falling back to .env.

    Kept out of the code on purpose: it is a personal path (a synced Drive
    folder, say) and this repo is public.
    """
    value = os.environ.get("ANKI_DECKS_DROP_DIR")
    if not value:
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ANKI_DECKS_DROP_DIR="):
                    value = line.split("=", 1)[1].strip().strip("'\"")
                    break
    return Path(value).expanduser() if value else None


def _drop_decks(paths, drop: Path) -> int:
    """Copy the built decks into `drop`, writing each atomically.

    A cloud-synced folder may start uploading the moment a file appears, so the
    copy lands on a temporary name first and is then renamed into place.
    """
    drop = Path(drop).expanduser()
    try:
        drop.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"  warning: cannot use drop directory {drop}: {exc}", file=sys.stderr)
        return 0

    copied = 0
    for src in paths:
        dest = drop / src.name
        tmp = dest.with_name(dest.name + ".part")
        try:
            shutil.copy2(src, tmp)
            tmp.replace(dest)
            copied += 1
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            print(f"  warning: could not copy {src.name}: {exc}", file=sys.stderr)
    return copied


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
        "--images",
        action="store_true",
        help="embed reference images from decks/colombia/imagenes.yaml",
    )
    parser.add_argument(
        "--drop",
        type=Path,
        help="also copy the built .apkg here after a successful build "
        "(default: ANKI_DECKS_DROP_DIR from the environment or .env)",
    )
    parser.add_argument(
        "--no-drop", action="store_true", help="skip the drop step even if one is configured"
    )
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

    images_by_card = {}
    if args.images:
        import yaml  # noqa: PLC0415

        from ankicards.images import CACHE_DIR, MANIFEST  # noqa: PLC0415
        from ankicards.loader import MEDIA_DIR  # noqa: PLC0415

        if MANIFEST.is_file():
            for card_id, entry in (yaml.safe_load(MANIFEST.read_text("utf-8")) or {}).items():
                ruta = CACHE_DIR / entry["archivo"]
                if not ruta.is_file():          # las curadas a mano viven en media/
                    ruta = MEDIA_DIR / entry["archivo"]
                if ruta.is_file():
                    images_by_card[card_id] = {**entry, "ruta": ruta}
            print(f"  {len(images_by_card)} card(s) with a reference image")
        else:
            print(f"  warning: no image manifest at {MANIFEST}", file=sys.stderr)

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

    built = []
    total = 0
    for deck in decks:
        out_path = build_deck(
            deck, args.out, audio_by_deck.get(deck.name), images_by_card
        )
        count = len(deck.cards)
        total += count
        built.append(out_path)
        print(f"  {deck.name:<40} {count:>4} card(s)  ->  {out_path.name}")

    print(f"\nBuilt {len(decks)} deck(s), {total} card(s) into {args.out}/")

    drop = None if args.no_drop else (args.drop or _configured_drop())
    if drop:
        copied = _drop_decks(built, drop)
        print(f"\nCopied {copied} deck(s) to {drop}")

    print("Import into Anki: File > Import, or just double-click the .apkg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
