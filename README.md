# anki-cards

My Anki cards, written as plain-text YAML and version-controlled, plus Python
scripts that build them into `.apkg` decks you import into Anki.

The point: cards live in git, where they can be diffed, reviewed, grepped and
edited in a real editor — not locked inside Anki's collection database.

## Folder architecture

```
anki-cards/
├── decks/          SOURCE OF TRUTH. One .yaml per deck, organised in subfolders
│                   however you like. This is the only folder you hand-edit.
├── media/          Images and audio referenced by cards, by bare filename.
│                   A card writes <img src="dog.png"> and the file lives here.
├── ankicards/      The library: YAML schema, note models, .apkg builder.
│   ├── models.py   genanki note types (basic, basic-reversed, cloze) + card CSS.
│   ├── loader.py   Parses and validates deck YAML into Deck/Card objects.
│   └── builder.py  Turns a Deck into an .apkg with stable note GUIDs.
├── scripts/        The commands you actually run.
│   ├── build.py    decks/**/*.yaml  ->  build/*.apkg
│   ├── validate.py Check the YAML without building.
│   └── new_deck.py Scaffold a new deck file with a fresh deck_id.
├── build/          Generated .apkg files. Gitignored, disposable — never edit,
│                   never commit. Delete it any time; `build.py` recreates it.
└── pyproject.toml  Dependencies (genanki, pyyaml), managed with uv.
```

Sources go in `decks/`, output comes out in `build/`. Anything in `build/` is
derived and will be overwritten.

## Usage

```bash
uv sync                                     # one-time: install dependencies

uv run scripts/new_deck.py "Spanish::Verbs" # scaffold decks/spanish/verbs.yaml
uv run scripts/validate.py                  # check every deck for problems
uv run scripts/build.py                     # build every deck into build/
uv run scripts/build.py decks/spanish       # or just one folder / file
```

Then double-click the `.apkg` in `build/`, or use **File → Import** in Anki.

## Working from a scan in `raw_input/`

Scanned PDFs have no text layer, so there is nothing to extract automatically —
the pages get rendered to images, read, and transcribed into `decks/`.

```bash
uv sync --group extract
uv run --group extract scripts/render_pdf.py raw_input/<scan>.pdf -o /tmp/pages
uv run --group extract scripts/render_pdf.py raw_input/<scan>.pdf -o /tmp/crops \
    --pages 11 --dpi 220 --crop 0.0,0.02,0.18,0.30      # zoom a handwritten margin
```

`raw_input/` is gitignored — source scans stay local, the cards they produce get
committed. See `decks/colombia/` for a worked example.

## The one rule: ids are permanent

Anki recognises a note by a GUID, which this repo derives from the deck name plus
the card's `id`. That makes re-importing safe:

- **Edit a card's text** → next import *updates* the existing card, and your
  review history and scheduling survive.
- **Change a card's `id`** (or the deck's `name`/`deck_id`) → Anki sees something
  new and adds a *second* card next to the old one.

So pick an `id` once and leave it alone. Same for `deck_id`, which
`new_deck.py` generates for you.

Deleting a card from the YAML does **not** delete it from Anki — imports only add
and update. Remove it in Anki yourself.

## Card schemas

Every card needs an `id`. Everything else depends on the model.

**`basic`** — one card, front to back:

```yaml
- id: es-perro
  front: el perro
  back: the dog
  tags: [animals]
```

**`basic-reversed`** — two cards, front→back and back→front:

```yaml
- id: es-manzana
  model: basic-reversed
  front: la manzana
  back: the apple
```

**`cloze`** — one card per `{{cN::...}}` deletion:

```yaml
- id: es-subjunctive
  model: cloze
  text: Espero que {{c1::tengas}} razon.
  notes: Subjunctive after "espero que".
```

Optional on any card: `tags` (merged with the deck's tags), `notes` (shown
smaller beneath the answer), and `model` to override the deck default.

Deck-level keys are `deck` (name, `::` makes a subdeck), `deck_id`, `model`
(default for its cards), `tags` (applied to every card) and `cards`.

Fields accept HTML, so `<b>`, `<pre>`, `<ul>` and friends all work.

## What validation catches

`validate.py` (and `build.py`, which runs it first) reports every problem in one
pass rather than failing on the first:

- missing or duplicate card `id`, missing `deck_id`, unknown model
- keys that don't belong to a card's model, e.g. `front` on a cloze card
- a cloze card with no `{{c1::...}}` deletion, which would produce no cards
- media referenced by a card with no matching file in `media/`
- two decks sharing a `deck_id` or a name, which would merge on import

`build.py` writes nothing unless everything validates, so `build/` is never left
half-updated.

## Adding a new model

Note types are identified by a fixed ID, so they're hardcoded in
`ankicards/models.py`. To add one: generate an ID once
(`python3 -c 'import random; print(random.randrange(1<<30, 1<<31))'`), paste it
in as a literal, then register the model in `MODELS` and its YAML keys in
`MODEL_FIELDS`. Never change an existing ID.
