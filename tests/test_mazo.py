"""Invariantes del mazo. Cada uno existe porque su ausencia rompió algo real.

- El esquema de un tipo de nota no puede cambiar: añadir un campo hizo que Anki
  rechazara 47 notas al importar.
- El audio y las imágenes no pueden ir en un campo que se renderice en la cara de
  pregunta: el clip de las cloze cantaba la respuesta.
- Toda imagen referenciada debe estar empaquetada y llevar su procedencia.
"""

import json
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ankicards import images as IM
from ankicards import tts
from ankicards.loader import MEDIA_DIR, load_all_decks
from ankicards.models import MODELS

DECKS = Path("decks/colombia")
CAMPOS_ESPERADOS = {"basic": 2, "basic-reversed": 2, "cloze": 2}


@pytest.fixture(scope="module")
def mazos():
    return load_all_decks([DECKS])


# ─── Esquema ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre,n", CAMPOS_ESPERADOS.items())
def test_los_modelos_conservan_su_numero_de_campos(nombre, n):
    assert len(MODELS[nombre].fields) == n, (
        f"{nombre} cambió de campos; Anki rechazaría las notas ya importadas"
    )


# ─── Audio de las cloze ──────────────────────────────────────────────

def test_el_clip_de_pregunta_no_dice_nada_oculto(mazos):
    for deck in mazos:
        for card in deck.cards:
            if card.model != "cloze":
                continue
            lados = tts.sides_for_card(card)
            if "question" not in lados:
                continue
            enunciado = lados["question"]
            assert "{{" not in enunciado, f"{card.id}: el enunciado lleva marcado cloze"
            assert card.fields["text"].startswith(enunciado[:30]), (
                f"{card.id}: el enunciado no es un prefijo del texto visible"
            )


def test_las_cloze_de_varios_huecos_no_llevan_clip_de_pregunta(mazos):
    for deck in mazos:
        for card in deck.cards:
            if card.model != "cloze":
                continue
            if len(tts.cloze_numbers(card.fields["text"])) > 1:
                assert "question" not in tts.sides_for_card(card), (
                    f"{card.id}: con varios cN un clip único no vale para todas sus tarjetas"
                )


# ─── Normalización para la voz ───────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("40,5 %", "por ciento"),
    ("800.000 km²", "kilómetros cuadrados"),
    ("entre 10° y 18°C", "grados centígrados"),
    ("la C.P.C. es norma", "Constitución Política de Colombia"),
    ("(art. 4)", "artículo 4"),
    ("Billete de $100.000", "pesos"),
])
def test_normalize_expande_lo_que_la_voz_leeria_mal(entrada, esperado):
    assert esperado in tts.normalize(entrada)


def test_normalize_quita_el_html_y_resuelve_las_delaciones():
    salida = tts.normalize('Hay {{c1::tres}} ramas.<br><img src="x.png">')
    assert "tres" in salida
    assert "<" not in salida and "img" not in salida


# ─── Manifiesto de imágenes ──────────────────────────────────────────

@pytest.fixture(scope="module")
def manifiesto():
    return yaml.safe_load(IM.MANIFEST.read_text("utf-8")) or {}


def test_todas_las_tarjetas_de_geografia_tienen_imagen(manifiesto):
    geo = yaml.safe_load((DECKS / "02-geografia.yaml").read_text("utf-8"))
    sin = [c["id"] for c in geo["cards"] if c["id"] not in manifiesto]
    assert not sin, f"sin imagen: {sin[:5]}"


def test_cada_par_departamento_capital_usa_su_mapa_localizador(manifiesto):
    geo = yaml.safe_load((DECKS / "02-geografia.yaml").read_text("utf-8"))
    for c in geo["cards"]:
        if c["id"].startswith("geo-cap-"):
            entrada = manifiesto[c["id"]]
            assert entrada["origen"] == "commons-mapa", (
                f"{c['id']}: debería llevar localizador, lleva {entrada['origen']}"
            )


def test_los_archivos_del_manifiesto_existen(manifiesto):
    faltan = [e["archivo"] for e in manifiesto.values()
              if not (IM.CACHE_DIR / e["archivo"]).is_file()
              and not (MEDIA_DIR / e["archivo"]).is_file()]
    assert not faltan, f"archivos ausentes: {faltan[:5]}"


def test_nunca_se_genera_un_hecho_visual(manifiesto):
    """Grok inventó un capibara en el escudo: los símbolos solo van por foto."""
    prohibidos = {"cul-bandera-franjas", "cul-escudo-anio-autor", "cul-escudo-condor",
                  "geo-regiones-cuantas", "geo-andina-deptos"}
    for cid in prohibidos & set(manifiesto):
        assert not manifiesto[cid]["origen"].startswith("grok"), (
            f"{cid} lleva imagen generada y es un hecho visual"
        )


# ─── El .apkg construido ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def apkgs():
    rutas = sorted(Path("build").glob("Colombia__*.apkg"))
    if not rutas:
        pytest.skip("no hay .apkg construidos")
    return rutas


def test_el_apkg_empaqueta_todo_lo_que_referencia(apkgs):
    for ruta in apkgs:
        with tempfile.TemporaryDirectory() as d, zipfile.ZipFile(ruta) as z:
            z.extractall(d)
            media = set(json.loads(z.read("media").decode() or "{}").values())
            con = sqlite3.connect(Path(d) / "collection.anki2")
            refs = set()
            for (flds,) in con.execute("select flds from notes"):
                refs |= set(re.findall(r'<img src="([^"]+)"', flds))
                refs |= set(re.findall(r"\[sound:([^\]]+)\]", flds))
            con.close()
        assert not refs - media, f"{ruta.name}: {len(refs - media)} archivos sin empaquetar"


def test_ninguna_cloze_lleva_media_en_el_campo_text(apkgs):
    for ruta in apkgs:
        with tempfile.TemporaryDirectory() as d, zipfile.ZipFile(ruta) as z:
            z.extractall(d)
            con = sqlite3.connect(Path(d) / "collection.anki2")
            models = json.loads(con.execute("select models from col").fetchone()[0])
            cloze = [k for k, v in models.items() if v["name"] == "anki-cards Cloze"]
            if not cloze:
                continue
            for (flds,) in con.execute("select flds from notes where mid=?", (cloze[0],)):
                texto = flds.split("\x1f")[0]
                assert "<img" not in texto, f"{ruta.name}: <img> en Text destriparía la respuesta"
            con.close()


def test_toda_nota_con_imagen_declara_su_procedencia(apkgs):
    for ruta in apkgs:
        with tempfile.TemporaryDirectory() as d, zipfile.ZipFile(ruta) as z:
            z.extractall(d)
            con = sqlite3.connect(Path(d) / "collection.anki2")
            for (flds,) in con.execute("select flds from notes"):
                if "<img" in flds:
                    assert re.search(r"Foto:|Mapa:|Ilustración generada", flds), (
                        f"{ruta.name}: nota con imagen y sin procedencia"
                    )
            con.close()
