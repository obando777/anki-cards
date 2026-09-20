"""genanki note models.

The model IDs below are hardcoded on purpose. Anki identifies a note type by its
ID, so if these were randomized per build, every import would create a *new* note
type alongside the old one and your cards would drift apart. Never change them.

To add a model: pick a fresh random ID once (`random.randrange(1 << 30, 1 << 31)`),
paste it in as a literal, and register the model in MODELS.
"""

import genanki

CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  font-size: 22px;
  text-align: center;
  color: #1a1a1a;
  background-color: #fdfdfd;
  line-height: 1.5;
}

.notes {
  font-size: 15px;
  color: #666;
  margin-top: 1em;
}

code, pre {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 0.85em;
  text-align: left;
}

pre {
  background: #f4f4f4;
  padding: 0.6em 0.8em;
  border-radius: 6px;
  overflow-x: auto;
}

.cloze {
  font-weight: bold;
  color: #0a67c2;
}

.nightMode .card { color: #e8e8e8; background-color: #2f2f31; }
.nightMode .notes { color: #a0a0a0; }
.nightMode pre { background: #3a3a3c; }
.nightMode .cloze { color: #5cb3ff; }
"""

BASIC = genanki.Model(
    1727384501,
    "anki-cards Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Recognition",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        },
    ],
    css=CSS,
)

BASIC_REVERSED = genanki.Model(
    1727384502,
    "anki-cards Basic (and reversed)",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Recognition",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        },
        {
            "name": "Recall",
            "qfmt": "{{Back}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Front}}',
        },
    ],
    css=CSS,
)

CLOZE = genanki.Model(
    1727384503,
    "anki-cards Cloze",
    # QAudio existe para que el audio de la pregunta NO viaje en Text: cualquier
    # cosa puesta en Text se renderiza también al preguntar, y un [sound:] ahí
    # reproduce la frase resuelta, es decir, canta la respuesta.
    fields=[{"name": "Text"}, {"name": "Extra"}, {"name": "QAudio"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}{{QAudio}}",
            "afmt": '{{cloze:Text}}<div class="notes">{{Extra}}</div>',
        },
    ],
    css=CSS,
    model_type=genanki.Model.CLOZE,
)

MODELS = {
    "basic": BASIC,
    "basic-reversed": BASIC_REVERSED,
    "cloze": CLOZE,
}

# Which YAML keys supply the content for each model, in field order.
MODEL_FIELDS = {
    "basic": ("front", "back"),
    "basic-reversed": ("front", "back"),
    "cloze": ("text",),
}
