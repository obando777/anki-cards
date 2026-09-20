# Mazo Colombia

Mazo de estudio generado a partir del escaneo de la cartilla en
`raw_input/colombia/` (19 páginas, 4 módulos, texto impreso más anotaciones
manuscritas al margen).

## Qué hay

| Módulo | Mazo en Anki | Notas | Páginas |
|---|---|---|---|
| 1 | `Colombia::1. Cultura y Sociedad` | 123 | 1-7 |
| 2 | `Colombia::2. Geografía` | 135 | 8-12 |
| 3 | `Colombia::3. Historia Patria` | 83 | 13-16 |
| 4 | `Colombia::4. Constitución Política` | 74 | 17-19 |
| | **Total** | **415** | **19** |

Las 415 notas producen **822 tarjetas** en Anki: las `basic-reversed` generan
dos y las `cloze` una por cada `{{cN::}}`.

| Modelo | Notas | Para qué se usa |
|---|---|---|
| `basic` | 196 | Un hecho, una pregunta: fechas, cifras, definiciones |
| `basic-reversed` | 144 | Pares que debes saber en ambos sentidos: departamento↔capital, festival↔ciudad, artículo↔derecho, autor↔obra |
| `cloze` | 75 | Listas cortas: fronteras, cordilleras, pisos térmicos, ríos de una región |

## Cómo estudiarlo

```bash
uv run scripts/build.py decks/colombia   # -> build/Colombia__*.apkg
```

Importa los cuatro `.apkg`. Quedan como submazos de `Colombia`, así que puedes
estudiar un módulo aislado (como en el examen) o el mazo padre completo.

Cada tarjeta lleva en las notas su origen exacto — `Fuente: Módulo 2, p. 9 (§1.5.4)` —
para que puedas volver a la página cuando algo no cuadre. Las 415 lo llevan.

### Etiquetas

Además de `colombia` y `modulo-N`, cada tarjeta lleva una etiqueta de capítulo
(`simbolos-patrios`, `festivales`, `caribe`, `independencia`, `derechos-fundamentales`…)
para armar mazos filtrados por tema.

Cuatro etiquetas de control marcan de dónde viene el dato:

| Etiqueta | Notas | Significado |
|---|---|---|
| `anotacion` | 52 | El dato viene de una nota manuscrita del margen, no del texto impreso |
| `externo` | 12 | No está en la cartilla; se investigó y la nota lleva la URL |
| `discrepancia` | 9 | La cartilla contradice el hecho documentado — **ver abajo** |
| `revisar` | 4 | Lectura del manuscrito no resuelta; confirma y corrige el YAML |

## Las 9 tarjetas `discrepancia` — léelas antes del examen

La cartilla tiene errores de hecho. **La tarjeta enseña lo que dice la cartilla**
(es contra lo que te evalúan) y la nota explica la corrección documentada. Si tu
examen no se califica contra esta cartilla, invierte el criterio.

| Tarjeta | La cartilla dice | Lo documentado |
|---|---|---|
| `his-santa-marta-fundacion` | Pedro de Heredia fundó Santa Marta (1533) | Bastidas fundó Santa Marta (1525); Heredia fundó **Cartagena** (1533) |
| `his-bomba-das` | Bomba al DAS en **1980** | 6 de diciembre de **1989** |
| `his-jep` | **Junta** Especial para la Paz | **Jurisdicción** Especial para la Paz |
| `his-pajaros` | "Los Pájaros" eran **liberales** | Eran de filiación **conservadora**, atacaban liberales |
| `his-modernizacion-presidente` | (manuscrito corrige "Reyes"→"Núñez") | El impreso acierta: fue **Rafael Reyes**, 1904-1909 |
| `geo-macizo-colombiano` | Macizo Colombiano al **sureste** | Al **suroeste** (Cauca) |
| `geo-isla-malpelo` | Malpelo al **sureste** | Mar adentro al **suroeste**; pertenece al Valle del Cauca |
| `geo-amazonica-deptos` | "Guainía (San José del Guaviare)" | San José del Guaviare es capital de **Guaviare** |
| `geo-archipielago-islas` | "10 islas" y enumera 8 | Enumera 8 |

## Las 4 tarjetas `revisar` — confírmalas tú

Son cifras demográficas anotadas a mano en los márgenes de la p. 11, con dígitos
que no se leen con certeza ni siquiera a 220 dpi. Contrasta con tus apuntes y
corrige el YAML:

- `geo-poblacion-total` — población de Colombia: 44-50 millones
- `geo-indigenas-pct` — indígenas 4,3 %
- `geo-afrocolombianos-pct` — afrocolombianos 6,7 % ≈ 3 millones
- `geo-rom-gitanos` — Rom/gitanos ≈ 2.000 personas

## Lo que falta

`LAGUNAS.md` lista las 22 lagunas abiertas del material. La más importante: lo
escaneado es una guía-resumen de 19 páginas sobre una cartilla de ~145 páginas a
la que remite 38 veces. Escanear esa cartilla cierra 16 de las 22.

## Regla que no debes romper

El `id` de cada tarjeta y el `deck_id` de cada mazo son permanentes. Corrige
libremente el texto de una tarjeta: al reimportar, Anki la **actualiza** y
conserva tu historial de repaso. Si cambias su `id`, obtienes una tarjeta nueva
al lado de la vieja.

Borrar una tarjeta del YAML **no** la borra de Anki: las importaciones solo
agregan y actualizan. Bórrala tú en Anki.
