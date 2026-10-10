# Verificar una pantalla

`/design-review verify <pantalla>` mira el resultado, no la intención: mide la pantalla en un navegador
real, aplica reglas que no dependen de opinión y se la pasa a un revisor que no la ha diseñado. En la
prueba UC-9001 fue, con el brief, la capa que más subió la nota (+5,75/40), y lo que más puntos movió
fue una medición: el `scrollWidth` a 390 px.

Sirve para una pantalla implementada (lo llama `/implement`) y para un candidato en HTML de Stitch o
Claude Design.

## 1. Medir

El script vive junto a esta skill, en `scripts/verify.mjs` (con la instalación global,
`~/.claude/skills/design-review/scripts/verify.mjs`). Se ejecuta **desde la raíz del proyecto**, para
que use el Playwright que el proyecto ya tiene para sus e2e:

```bash
node <skill>/scripts/verify.mjs <URL o fichero.html> \
  --out .quality/evidence/{feature}/design-review --name {pantalla}
```

- **Destino:** la URL de la pantalla con el servidor de desarrollo levantado (el `webServer` o la
  `baseURL` de `playwright.config`), o el fichero HTML del candidato. Con un fichero, cada hallazgo
  lleva la línea donde está el elemento.
- **Navegador:** primero el Chrome del sistema y después el Chromium de Playwright (`CHROME_PATH` lo
  fuerza). No instala nada.
- **Pantalla quieta:** antes de medir recorre la página (para que aparezca lo que entra al hacer
  scroll) y espera a las fuentes y al final de las animaciones, como mucho 5 s. Así la captura no
  sale a mitad de una animación de carga.
- **Salida:** `{pantalla}-1440.png`, `{pantalla}-390.png` (página completa) y `{pantalla}-verify.json`.
  Tarda segundos por pantalla.
- **Código de salida:** `0` informe escrito; `2` el proyecto no tiene Playwright; `1` error. Con `2`
  se sigue sin capturas: el revisor trabaja sobre el código y la revisión dice que no hubo medición.

Qué mide en los dos anchos:

| Regla | Qué detecta |
|---|---|
| `desbordamiento` | `scrollWidth` mayor que la ventana, con los elementos que sobresalen y su selector |
| `texto-degradado` | `background-clip: text` con degradado |
| `borde-lateral` | Un solo lado con más de 1 px y color (la tarjeta o el aviso con franja) |
| `eyebrow` | Mayúsculas pequeñas con espaciado justo encima de un título |
| `transition-all` | `transition-property: all` |
| `emoji-icono` | Pictogramas Unicode como icono de un botón, un enlace o un icono |
| `contraste` | Texto por debajo de 4,5:1, o de 3:1 si es grande, contra su fondo efectivo |
| `area-pulsacion` | A 390 px, controles de menos de 40 px, salvo enlaces dentro de un texto |

Cada hallazgo trae `selector`, un fragmento del texto, el ancho donde aparece y, con un fichero, la
`linea`. Hay un tope de 40 por regla; los que pasan se cuentan en `resumen.omitidos`.

**Son mediciones, no veredictos.** El revisor las confirma en la captura o en el código antes de
usarlas, y una puede estar justificada por el brief. Límites conocidos: el contraste se calcula
contra los colores de fondo del árbol, no contra imágenes ni degradados (esos textos se saltan); lo
que solo aparece con una interacción (hover, un clic, un menú abierto) no se mide; la línea es la
primera que casa, así que en elementos repetidos o pintados por un script es una pista.

### Después de una corrección: `dato-sin-fuente`

```bash
node <skill>/scripts/verify.mjs <destino> --out <dir> --name {pantalla}-r1 \
  --previous <dir>/{pantalla}-verify.json \
  --sources doc/design/{feature}/{pantalla}.brief.md,doc/prd/{feature}/prd.md
```

`dato_sin_fuente` lista las cifras visibles que no estaban antes de la corrección ni aparecen en las
fuentes. En la prueba, el diseñador inventó un participante y unos recuentos para cumplir la crítica:
cada cifra de esa lista es un defecto del criterio 1 hasta que alguien diga de dónde sale.

## 2. Revisar, en un subagente aislado

Quien diseñó no se revisa. Lanza un subagente (herramienta Agent) **sin** el razonamiento ni la
conversación de quien diseñó, con este encargo:

```text
Revisa una pantalla. No la has diseñado y no tienes que defenderla. No edites ningún fichero.

Lee, en este orden:
1. El brief: doc/design/{feature}/{pantalla}.brief.md (y .direction.md si existe).
2. La rúbrica: <skill>/reference/rubric.md, con <skill>/reference/defaults.md y surfaces.md.
3. Las capturas: <dir>/{pantalla}-1440.png y <dir>/{pantalla}-390.png. Míralas enteras.
4. Las mediciones y los hallazgos: <dir>/{pantalla}-verify.json.
5. El código de la pantalla: <rutas>.

Los hallazgos del JSON son mediciones: confírmalos en la captura o en el código. Si el brief
justifica uno, dilo y no lo penalices. Una cifra, fila o función que no sale del brief ni del PRD
es un defecto del criterio 1.

Devuelve exactamente el formato de rubric.md (tabla de 8 criterios, total y veredicto, defectos
por severidad) y, al final, «Tres problemas prioritarios»: los tres arreglos que más subirían
la pantalla, cada uno con su ubicación y en una frase.
```

## 3. Escribir `{pantalla}.verify.md`

En `doc/design/{feature}/`, junto al brief y la dirección:

```markdown
# Verificación: {pantalla}

> {fecha} · Destino: {URL o fichero} · Revisor: subagente aislado · Ronda: 0 | 1

**Veredicto: Block | Needs changes | Approve · Total: N/40**

## Tres problemas prioritarios
1. …
2. …
3. …

## Notas
| # | Criterio | Nota | Justificación |

## Mediciones
| Ancho | scrollWidth | Desborda | Sobresalen |
| 1440 | … | no | — |
| 390 | … | sí | `selector` (right: N px) |

## Hallazgos de las reglas
| Regla | Dónde | Línea | Detalle | ¿Justificado por el brief? |

## Defectos
| Severidad | Dónde | Qué está mal | Qué hacer |

## Ronda de corrección (si la hubo)
| Defecto | Aplicado | Si no, por qué |
Cifras sin fuente tras la corrección: ninguna | lista

Capturas e informe: `.quality/evidence/{feature}/design-review/{pantalla}-*`
```

## 4. Una ronda de corrección, como mucho

Con «Needs changes» o «Block», se aplican los defectos con las reglas de la ronda de
[rubric.md](rubric.md): una sola ronda, sin inventar datos (lo que falte va como `[DATO REAL: …]`) y
con motivo escrito para lo que no se aplique. Después se vuelve a medir con `--previous` y
`--sources`, se revisa otra vez en un subagente nuevo y el `.verify.md` se actualiza con la ronda 1.
No hay ronda 2: lo que quede va al veredicto y a la evidencia.
