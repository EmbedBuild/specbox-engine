# Discovery: zero_python_onboarding

**Discovery ID**: disc-7b986e44fdcb
**Created**: 2026-05-28T13:31:49.998392+00:00
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ c6cb558bf6e8cfce

## Problema

La extensión VSCode de SpecBox impone Python 3.12+ como requisito de
onboarding por dos motivos que resultaron innecesarios:

1. El MCP server ofrece un modo "Local" (corre el server Python en la máquina
   del cliente) junto al modo "Remote" (apunta al MCP gratuito hospedado por
   el owner en `https://mcp-specbox-engine.jpsdeveloper.com/mcp`).
2. Engram (memoria persistente, obligatoria) se cablea vía `pip install engram`
   / `pipx install engram` — pero Engram es en realidad un **binario nativo
   single-file con cero dependencias**, instalable vía `brew install
   gentleman-programming/tap/engram`. El pip era una vía obsoleta/incorrecta.

Un beta-tester (ICP-2) se quedó bloqueado en el onboarding por la dependencia
de Python. Como el MCP remoto se sirve gratis, el modo local no aporta valor
suficiente para justificar la fricción que añade. Eliminar el modo local +
migrar Engram a brew elimina Python por completo del path del cliente.

## ICPs involucrados

Heredados de `doc/app/app_market.md` (sin ICPs nuevos):

- **ICP-2: Dev solo con Claude Code que adopta SpecBox** (primario para esta
  feature). Es exactamente el perfil del beta-tester bloqueado: instala el
  engine en sus proyectos, valora disciplina spec-driven, pero el coste de
  entrada (instalar y mantener Python 3.12+) lo frena antes de obtener valor.
- **ICP-1: Owner-operator (JPS, dogfooding)** (secundario). Mantiene el MCP
  remoto gratuito; se beneficia de un onboarding más simple que reduce soporte.

No-ICP relevante: esta feature NO sirve a usuarios air-gapped que requieran
correr el MCP sin conexión al remoto — decisión de producto explícita
(matar el modo local del todo, sin fallback oculto).

## JTBDs racionales

- **JR-FZPY.1 [ICP-2]**: Cuando instalo la extensión SpecBox por primera vez,
  quiero estar operativo con solo Node + Claude Code (sin instalar ni
  configurar Python), para empezar a usar el pipeline en minutos en lugar de
  pelearme con versiones de Python y `PATH`.
- **JR-FZPY.2 [ICP-2]**: Cuando configuro los servidores MCP, quiero que la
  extensión apunte directamente al MCP remoto gratuito sin preguntarme
  local-vs-remoto, para no tener que decidir algo cuyo trade-off no entiendo
  todavía en el onboarding.
- **JR-FZPY.3 [ICP-2]**: Cuando instalo Engram (memoria obligatoria), quiero
  que se instale como binario nativo (`brew`) sin arrastrar un runtime de
  Python, para que la única dependencia "pesada" del producto desaparezca.
- **JR-FZPY.4 [ICP-1]**: Cuando reviso el health check / walkthrough / README,
  quiero que ningún artefacto mencione Python como requisito, para que la cara
  visible del producto sea coherente con la realidad (cero Python).

## JTBDs emocionales

- **JE-FZPY.1 [ICP-2]**: Sentir que el producto "simplemente funciona" tras
  instalar la extensión, sin la ansiedad de creer que falta algo o que mi
  entorno no está bien configurado. (Deriva de JE-G.3 — la cara visible
  refleja la disciplina interna.)
- **JE-FZPY.2 [ICP-1]**: Confianza de que el onboarding no genera tickets de
  soporte por "no me arranca el MCP / me falta Python". Menos fricción = menos
  abandono = más credibilidad. (Deriva de JE-G.3.)

## Validation evidence

- **[c] Conversación con usuario real**: un beta-tester (perfil ICP-2) reportó
  directamente al owner que la dependencia de tener Python instalado en local
  fue un problema durante la instalación/actualización vía extensión. Esta
  feature responde a ese feedback concreto.
- Datapoint de soporte: el modo local nunca aportó valor verificable frente al
  remoto gratuito; el remoto es el camino recomendado por defecto en la propia
  QuickPick actual.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Hereda ICP-1 e ICP-2 de app_market.md.
- **Nuevos JTBDs introducidos**: ninguno a nivel de producto. Los JTBDs de
  feature (JR-FZPY.*, JE-FZPY.*) derivan de JR-G.* y JE-G.3 existentes.
- **Resolución**: `no_drift`

## Verdict

**READY_FOR_PRD**

Todas las secciones están completas: ICPs heredados sin drift, JTBDs racionales
y emocionales con formato canónico, validation evidence basada en conversación
real con un usuario ICP-2, y drift resuelto como `no_drift`.

---

> Next step: `/prd zero_python_onboarding`
