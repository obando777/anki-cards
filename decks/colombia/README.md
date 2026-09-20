# Mazo Colombia — examen de naturalización

Mazo de estudio para el **examen de conocimientos del trámite de Naturalización**
del Ministerio de Relaciones Exteriores (Cancillería).

Construido a partir de dos fuentes, ambas en `raw_input/colombia/` (ignorado por git):

| Archivo | Qué es |
|---|---|
| `Scan 2026-09-20 13.31.53.pdf` | Tu resumen de 19 páginas, impreso y anotado a mano |
| `Guia-oficial-Colombia-nuestra-casa.pdf` | La **guía oficial** de 190 páginas, [Cancillería](https://www.cancilleria.gov.co/sites/default/files/DOCUMENTOS-2026/naturalizacion/Guia_de_estudio_ajustada.pdf) |
| `Instructivo-examen-Naturalizacion-2025.pdf` | [Instructivo oficial](https://www.cancilleria.gov.co/sites/default/files/FOTOS2025/Gu%C3%ADa%20para%20la%20presetnaci%C3%B3n%20del%20examen%20de%20Naturalizaci%C3%B3n.pdf) del examen |

Tu resumen sigue la estructura de la guía oficial sección por sección. Donde los
dos se contradicen, **manda la guía oficial**: el examen se construye sobre ella.

## El examen real

Fuente: instructivo oficial. Diseñado por la **Universidad de Antioquia** por
encargo de la Cancillería (art. 13 de la Ley 2332 de 2023).

- **Opción múltiple**, 4 opciones, una sola correcta. No hay preguntas abiertas.
- **80 preguntas en 3 horas** — presentas la **Forma 1**, sin módulo de Lengua
  Castellana, porque el español es tu lengua materna.
- Solo **lápiz negro N.º 2**. Nada de electrónicos.

| Módulo del examen | Preguntas | Mínimo para aprobar | Mazo correspondiente | Tarjetas |
|---|---:|---:|---|---:|
| Constitución Política | 20 | **12** (60 %) | `Colombia::4. Constitución Política` | 115 |
| Geografía | 20 | **11** (55 %) | `Colombia::2. Geografía` | 157 |
| Historia Patria | 20 | **8** (40 %) | `Colombia::3. Historia Patria` | 83 |
| Cultura | 20 | **8** (40 %) | `Colombia::1. Cultura y Sociedad` | 123 |

Hay un quinto módulo, Lengua Castellana (10 preguntas), que **no te aplica**:
solo lo presentan quienes no tengan el español como lengua materna.

> **Hay que aprobar TODOS los módulos.** Basta fallar uno para quedar NO APROBADO,
> por bien que vayan los otros. Los módulos aprobados **no se acumulan** para una
> convocatoria futura: si repites, repites todo.

Tus notas al margen registraron los puntos de corte oficiales exactos (11/20,
8/20, 12/20), lo que confirma que el curso trabajaba con estas cifras.

## Qué hay en el mazo

**478 notas → 946 tarjetas** en Anki (las `basic-reversed` generan dos; las
`cloze`, una por cada `{{cN::}}`).

| Modelo | Notas | Para qué |
|---|---:|---|
| `basic` | 234 | Un hecho por tarjeta: fechas, cifras, definiciones |
| `basic-reversed` | 148 | Pares en ambos sentidos: departamento↔capital, artículo↔derecho, festival↔ciudad, autor↔obra |
| `cloze` | 96 | Listas cortas: fronteras, cordilleras, pisos térmicos, ríos |

El mazo se construyó sobre tu resumen escaneado y luego se **amplió desde la guía
oficial** solo en los dos módulos con el listón más alto: Constitución (74 → 115)
y Geografía (135 → 157). Cultura e Historia, que piden 40 %, quedaron igual.

El examen es de opción múltiple, o sea de **reconocer**, no de producir. El mazo
te exige producir la respuesta, que es más difícil: si dominas la tarjeta,
reconocer la opción correcta entre cuatro es trivial.

## Cómo estudiarlo

```bash
uv run scripts/build.py decks/colombia   # -> build/Colombia__*.apkg
```

Importa los cuatro `.apkg`. Quedan como submazos de `Colombia`, así que puedes
estudiar un módulo aislado o el mazo padre completo.

**Empieza por Constitución.** Es el módulo con el listón más alto (60 %) y el que
menos material tiene. Luego Geografía (55 %). Cultura e Historia piden 40 % y
perdonan más. El razonamiento completo está en `ANALISIS-MATERIAL.md`.

Cada tarjeta lleva su origen exacto en las notas — `Fuente: Guía oficial…, p. 87`
o `Fuente: Módulo 2, p. 9 (§1.5.4)` — para volver a la página cuando algo no cuadre.

### Etiquetas

Además de `colombia` y `modulo-N`, cada tarjeta lleva una etiqueta de capítulo
(`simbolos-patrios`, `festivales`, `caribe`, `independencia`,
`derechos-fundamentales`…) para armar mazos filtrados.

Cinco etiquetas de control dicen de dónde salió el dato:

| Etiqueta | Notas | Significado |
|---|---:|---|
| `anotacion` | 52 | Viene de una nota manuscrita del margen, no del texto impreso |
| `ampliacion` | 63 | Añadida desde la guía oficial, no está en tu resumen. **Suspéndela entera si el mazo se te hace pesado** |
| `externo` | 15 | No está en la guía oficial; la nota lleva la fuente |
| `corregido` | 8 | Tu resumen se apartaba de la guía oficial; **la tarjeta sigue a la oficial** |
| `error-fuente-oficial` | 1 | El error está en la guía **oficial**; la tarjeta la sigue igual |

## Las 8 tarjetas `corregido`

Tu resumen escrito a mano difiere de la guía oficial en estos ocho puntos. En
todos manda la oficial, y la nota de cada tarjeta lo explica:

| Tarjeta | Tu resumen decía | Guía oficial |
|---|---|---|
| `geo-isla-malpelo` | Malpelo al **sureste** | Al **suroeste** (p. 94) |
| `geo-macizo-colombiano` | Macizo al **sureste** | Al **suroeste** (p. 90) |
| `geo-amazonica-deptos` | "Guainía (San José del Guaviare)" | **Guaviare** → San José del Guaviare (p. 63) |
| `geo-archipielago-islas` | "10 islas" pero enumera 8 | **10 cayos**; faltaban Serranilla y Este-Sudeste (p. 93) |
| `geo-andina-ciudades` | Bogotá, Medellín, **Cali**, Cúcuta, B/manga | …y **Pereira**, no Cali (p. 68) |
| `geo-andina-poblacion` | 40 % del país | **40,5 %** (p. 68) |
| `his-pajaros` | "Los Pájaros" eran **liberales** | **Conservadores**, junto a los chulavitas (p. 131) |
| `his-jep` | "**Junta** Especial para la Paz" | "**Jurisdicción** Especial para la Paz" (pp. 130 y 134) |

Un noveno caso, `his-bomba-das`, decía 1980 por 1989 — pero la guía oficial **no
menciona** ese atentado, así que la tarjeta lleva la fecha correcta y queda
marcada `externo`: es poco probable en el examen.

## La tarjeta `error-fuente-oficial`

`his-santa-marta-fundacion` — la guía **oficial** dice textualmente *"la fundación
de Santa Marta por parte de Pedro de Heredia"* (p. 111). Históricamente es falso:
Santa Marta la fundó Rodrigo de Bastidas en 1525 y Heredia fundó Cartagena en
1533. Como el examen se construye sobre la guía oficial, **la tarjeta sigue a la
guía** y la nota explica el hecho real. Si te preguntan esto, responde lo que
dice la cartilla.

## Si te abruma

Son 946 tarjetas. Para bajar la carga sin perder cobertura, suspende en Anki la
etiqueta `ampliacion` (63 notas): vuelves al mazo que sale solo de tu resumen
escaneado. Reactívala cuando Constitución y Geografía te salgan sueltas.

## Lo que falta

`LAGUNAS.md` lleva el inventario.

## Regla que no debes romper

El `id` de cada tarjeta y el `deck_id` de cada mazo son permanentes. Corrige
libremente el texto: al reimportar, Anki **actualiza** la tarjeta y conserva tu
historial de repaso. Si cambias su `id`, obtienes una tarjeta nueva al lado de la
vieja.

Borrar una tarjeta del YAML **no** la borra de Anki: las importaciones solo
agregan y actualizan. Bórrala tú en Anki.
