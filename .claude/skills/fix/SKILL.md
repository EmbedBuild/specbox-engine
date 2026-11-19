---
name: fix
description: >
  Arregla un bug pequeño sin PRD ni plan, pero con su UC y su criterio en el tablero: prueba que
  reproduce el bug y falla, UC en la historia indicada o en la de bugs del proyecto, criterio
  aprobado, rama fix/, arreglo que deja la prueba en verde, recibo, revisión aislada y cierre.
  Para y propone /prd si el arreglo toca más de 5 ficheros, un contrato de API o una migración de
  datos, y propone /feedback si el bug no se puede reproducir con una prueba. Use when the user
  says "fix", "arregla este bug", "corrige el bug", "quick fix", "arreglo rápido", or when
  /manual-test finds a bug in the code of a project with a board.
context: direct
---

# /fix — Un arreglo con su UC y su criterio (US-127 · UC-12701)

/implement exige PRD y plan; un bug pequeño no los necesita, pero sí tiene que dejar rastro: una UC
con su criterio, una prueba que lo demuestra y su cierre en el tablero. /fix lleva un arreglo por el
mismo recorrido que cualquier UC, y para en cuanto el arreglo deja de ser pequeño.

## Uso

```
/fix "<qué falla y cómo se ve>"            # va a la historia de bugs del proyecto
/fix US-XX "<qué falla y cómo se ve>"      # va a esa historia
```

Un bug por /fix. Si la persona describe varios, arregla el primero y propone /fix para cada uno de
los demás.

## Paso 0 — ¿Hay tablero?

Hay tablero si `.claude/settings.local.json` tiene `boardId`, `backend_type` o
`specbox.backend_type`, o `.claude/project-config.json` tiene `backend_type` (la misma regla que los
hooks, `lib/config.mjs`). En un satélite multirepo el tablero es el del orquestador.

Sin tablero, /fix no hace nada y lo dice así:

> /fix necesita un tablero para dejar el arreglo con su UC y su criterio. Créalo con /app-init (o
> /prd para una funcionalidad nueva). Mientras, el bug se puede arreglar con /manual-test o a mano,
> sin rastro en el tablero.

Termina ahí, sin error.

## Paso 1 — Reproducir el bug con una prueba

Antes de tocar el tablero:

1. Diagnostica la causa leyendo el código (el mensaje, el log, la captura que te den).
2. Escribe **una prueba que reproduce el bug** en la carpeta de pruebas normal del proyecto
   (`tests/`, `test/`, `__tests__/`, `*_test.go`…), **nunca** en las de aceptación
   (`tests/acceptance/`, `test/acceptance/`, `e2e/acceptance/`, `.maestro/`): esas son de AG-09a.
3. Ejecútala y comprueba que **falla por el bug** (la aserción sobre el comportamiento roto), no por
   un error de importación, de sintaxis o de entorno. Apunta la orden exacta que la ejecuta.
4. Todavía no hagas commit: la prueba viaja a la rama de la UC en el Paso 5.

**Si no se puede reproducir con una prueba** (un problema visual sin pruebas de interfaz, de
configuración del entorno o de datos en la base), /fix no lo toma (UC-12701 AC-07). Deshaz la prueba
a medio escribir y dilo así:

> Este bug no se puede reproducir con una prueba ({motivo}), así que no va por /fix. Repórtalo con
> /feedback para que quede registrado con su captura; si es de configuración o de datos, se arregla
> donde vive (la base, el entorno), fuera del código.

**Primera medida del alcance.** Con el diagnóstico, estima qué ficheros cambiará el arreglo. Si ya se
ve que serán más de 5 (sin contar sus pruebas), o que toca un contrato de API o una migración de
datos, para aquí y propone /prd (Paso 8 dice cómo).

## Paso 2 — La historia

- Con `US-XX` en la orden: esa historia (`get_us`). Si no existe, dilo y para.
- Sin ella: la **historia de bugs** del tablero, la que se titula **«Arreglos sin PRD»**
  (`list_us`, por el título sin el prefijo del id). Si tiene 99 UC, la siguiente es «Arreglos sin
  PRD (2)», y así.
- Si no existe, créala con `import_spec`, sin UC, con el siguiente id libre del tablero (el mayor
  `US-NN` de `list_us` más uno):

  ```
  import_spec(board_id, spec={"user_stories": [{
    "us_id": "US-NN", "name": "Arreglos sin PRD", "screens": "",
    "description": "Arreglos pequeños hechos con /fix: cada uno con su UC, su criterio y su prueba.",
    "exclusions": ["Funcionalidad nueva o cambios grandes: van por /prd"],
    "use_cases": []}]})
  ```

## Paso 3 — La UC y su criterio

1. **El criterio**: uno, en indicativo y con el valor observable que el arreglo deja bien («El total
   de la factura queda en 120,00 € con dos líneas de 60,00 €»; no «Funciona bien» ni «Se arregla el
   total»). Sin rutas de fichero, sin credenciales, sin `[POR DECIDIR`.
2. **El id**: el siguiente de la serie `UC-{número de la historia}{NN}` (US-131 con UC-13101 y
   UC-13102 → UC-13103; una historia vacía empieza en `UC-{número}01`). Pásalo siempre en `uc_id`:
   sin él, en una historia vacía `add_uc` toma el siguiente número del tablero entero. Comprueba
   con `get_uc` que el id está libre.
3. **Crear**:

   ```
   add_uc(board_id, us_id, name="Arreglo · <el bug en pocas palabras>",
          description="<qué fallaba, cómo se reproduce y la causa>",
          acceptance_criteria=[{"text": "<criterio>", "verification": "automated_test"}],
          uc_id="UC-XXXX", actor="<quien ve el bug>")
   ```

   En un satélite multirepo, pasa también `satellite`: la etiqueta de este repositorio en
   `multirepo.satellites` del `.claude/settings.local.json` del orquestador.
4. **Calidad**: `validate_ac_quality(board_id, uc_id)`. Si el criterio no llega al umbral,
   reescríbelo con `update_ac` y repite: con `spec_quality` en «block», `start_uc` no arranca una UC
   que no llega.
5. **Sin PRD, con motivo**: `update_uc(board_id, uc_id, no_prd_reason="Arreglo con /fix: <el bug en
   una línea>")`. Va antes de `start_uc`, que lo lleva al marcador de UC activa (la medida
   `spec_in_pr` lo lee al fusionar).

## Paso 4 — Aprobación del criterio

Pregunta a la persona con AskUserQuestion, con el criterio literal: «¿Apruebas este criterio para
UC-XXXX?». Con un sí, `approve_criteria(board_id, uc_ids=["UC-XXXX"])`, desde esta sesión (un
subagente recibe `SUBAGENT_CANNOT_APPROVE`). Si pide otro texto, reescríbelo (Paso 3.4) y vuelve a
preguntar. En Trello o Plane la respuesta es `APPROVAL_NOT_SUPPORTED`: sigue y dilo en el resumen.

## Paso 5 — Arrancar la UC y la rama

1. `start_uc(board_id, uc_id)`. Si responde con un error de medida (`AC_QUALITY_BELOW_THRESHOLD`,
   `AC_NOT_APPROVED`, `PENDING_DECISIONS`), corrige lo que dice y repite; no sigas sin arrancarla.
2. Rama desde la principal actualizada, con la prueba del Paso 1 sin commitear:

   ```bash
   git fetch origin
   git switch -c fix/UC-XXXX-<slug> origin/<rama principal>
   ```

   Si hay cambios sin commitear que no son la prueba del arreglo, para y pregunta qué hacer con
   ellos antes de cambiar de rama.

   En native, `register_native_branch(board_id, uc_id, branch)`.
3. Commit de **la prueba sola**, que falla: `test(UC-XXXX): reproduce <el bug>`. Ejecútala otra vez
   en la rama y apunta que falla.

## Paso 6 — El arreglo

1. Cambia el código, lo mínimo para que la prueba pase.
2. Ejecuta la prueba (en verde) y el resto de las pruebas del proyecto y su linter (sin fallos
   nuevos).
3. Antes del commit, el Paso 7.

## Paso 7 — ¿Sigue siendo pequeño?

```bash
node ~/.claude/skills/fix/scripts/scope.mjs        # o .claude/skills/fix/scripts/scope.mjs en el engine
```

Devuelve `count`, `files`, `excluded`, `classes`, `stop` y `reasons`. Cuenta los ficheros del arreglo
frente a la rama base sin sus pruebas, `.quality/` ni `doc/tracking/`, y los clasifica con la regla
del radio de impacto (con los `impact` de la rama base).

- `stop: false` → commit del arreglo: `fix(UC-XXXX): <el bug>`.
- `stop: true` → **el Paso 8**.

## Paso 8 — Cuando deja de ser un arreglo pequeño

Con más de 5 ficheros, un contrato de API o una migración de datos (UC-12701 AC-04):

1. No hagas commit del arreglo. Deja la rama con la prueba que falla.
2. Apunta en la UC por qué se para (`update_uc` con la descripción ampliada: los `reasons` de
   `scope.mjs` y lo que falta), quita el motivo sin PRD (`update_uc(no_prd_reason="")`) y libérala
   (`release_uc`): queda en el tablero para que /prd la recoja con su prueba.
3. Dilo así:

   > Este arreglo ya no es pequeño: {reasons}. Va por /prd (y después /plan y /implement), que
   > recoge la UC-XXXX y la prueba que reproduce el bug en la rama fix/UC-XXXX-….

## Paso 9 — Recibo y revisión

1. **Recibo** (`mark_ac_batch`), antes del CI y de la PR: la puerta de desviación reclama los
   ficheros de una UC sin plan por los `files` de sus recibos.

   ```
   mark_ac_batch(board_id, uc_id, results=[{"ac_id": "AC-01", "passed": true,
     "evidence": {"type": "test", "label": "<fichero de la prueba>: <nombre de la prueba>",
       "detail": "falla antes del arreglo (<commit de la prueba>) y pasa después",
       "commit": "<commit del arreglo>", "repo": "<owner/repo>",
       "test": "<la orden que la ejecuta>", "files": [<todos los ficheros del arreglo, prueba incluida>]}}])
   ```

2. `move_uc(board_id, uc_id, "review")`.
3. CI local del proyecto si lo tiene (`bash scripts/ci-local.sh`), push y PR:
   `fix(UC-XXXX): <el bug>`, con el bug, la causa, la prueba (falla antes, pasa después) y los
   ficheros.
4. **Revisión aislada**, como 8.5.1c de /implement: un subagente `general-purpose` que solo recibe la
   UC (`get_uc`), su criterio, su recibo y el diff de la PR, comprueba que la prueba reproduce el bug
   y que el arreglo no rompe nada, y registra `record_review_verdict(board_id, uc_id,
   verdict="accepted")` o `verdict="returned"` con su `reason`. Con «returned», corrige, vuelve a
   marcar el recibo y repite.

## Paso 10 — Fusionar y cerrar

1. `gh pr merge <n> --squash --delete-branch` y vuelve a la rama principal (`git pull`).
2. `complete_uc(board_id, uc_id, files=<los ficheros de la PR>, repo="<owner/repo>")`, con
   `gh api repos/<owner>/<repo>/pulls/<n>/files --paginate --jq '.[].filename'`. La UC queda hecha y
   visible en el tablero, en su historia (UC-12701 AC-03).

## Resumen final

```
## ✅ Arreglo cerrado: UC-XXXX
- Bug: <qué fallaba>
- Historia: US-NN «…»
- Criterio: «…» (aprobado por <persona>)
- Prueba: <orden> — falla en <commit de la prueba>, pasa en <commit del arreglo>
- PR: #<n> (fusionada) · ficheros: <N>
- Revisión: <veredicto>
```

## Reglas

- Sin PRD ni plan, pero nunca sin UC, criterio aprobado, prueba que falla primero ni recibo.
- La prueba de regresión va en la carpeta de pruebas normal, nunca en las de aceptación.
- Un bug por /fix; más de 5 ficheros, un contrato de API o una migración de datos van por /prd.
- No se inventan datos: lo que el bug no dice se pregunta.
- La aprobación del criterio la da la persona; /fix nunca la da por ella.
