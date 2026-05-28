# Discovery: prerequisites_gate

**Discovery ID**: disc-660eeef3d25c
**Created**: 2026-05-28T13:48:23Z
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md

## Problema

La extensión VSCode ya tiene un HealthChecker que sabe qué falta (Node, Claude
Code, Engram, MCP configurado), pero **no avisa proactivamente** al usuario
cuando faltan requisitos. Hoy:
- El health check solo se muestra bajo demanda o pasivamente en la status bar.
- En el arranque solo se avisa si el *engine* no está instalado, no si faltan
  *prerequisitos* (Claude Code, Engram, Node) o si los servidores MCP no están
  configurados.

Resultado: un usuario puede creer que SpecBox está operativo cuando en realidad
le falta una pieza crítica, y descubrirlo más tarde con un fallo confuso. Esto
es exactamente el drift entre "lo que la UI sugiere" y "la realidad" que mata
credibilidad (JE-G.3).

## ICPs involucrados

Heredados de app_market.md (sin ICPs nuevos):
- **ICP-2: Dev solo con Claude Code que adopta SpecBox** (primario). Acaba de
  instalar la extensión; necesita saber inequívocamente si su entorno está listo.
- **ICP-1: Owner-operator (JPS, dogfooding)** (secundario). Menos tickets de
  soporte del tipo "no me funciona" cuando en realidad faltaba un requisito.

## JTBDs racionales

- **JR-FPG.1 [ICP-2]**: Cuando abro VSCode tras instalar la extensión, quiero
  que SpecBox me avise claramente si me falta algún requisito (Claude Code,
  Engram, Node o MCP sin configurar) y por qué importa, para no perder tiempo
  depurando fallos confusos creyendo que todo está bien.
- **JR-FPG.2 [ICP-2]**: Cuando el gate me avisa de un requisito ausente, quiero
  acciones directas (instalar / ver guía / ejecutar el wizard), para resolverlo
  sin salir a buscar documentación.
- **JR-FPG.3 [ICP-2]**: Cuando todo está correctamente instalado, NO quiero que
  el gate me moleste — silencio cuando no hay nada que avisar.
- **JR-FPG.4 [ICP-1]**: Cuando reviso el estado, quiero un comando dedicado
  para re-evaluar prerequisitos a demanda, para verificar tras instalar algo.

## JTBDs emocionales

- **JE-FPG.1 [ICP-2]**: Confianza de saber, sin ambigüedad, si el entorno está
  listo — no la ansiedad de "¿estará bien configurado o me va a fallar?".
  (Deriva de JE-G.1 — red de seguridad psicológica.)
- **JE-FPG.2 [ICP-1]**: Sentir que la extensión es honesta sobre su propio
  estado: si falta algo, lo dice; si todo está bien, no inventa ruido.
  (Deriva de JE-G.3 — la cara visible refleja la disciplina interna.)

## Validation evidence

- **[c] Conversación con usuario real**: el mismo beta-tester (ICP-2) del flujo
  cero-Python evidenció que la fricción de setup es un punto de abandono real.
  Un gate claro de prerequisitos reduce ese riesgo directamente.
- **[w] Waiver parcial**: el alcance exacto (qué requisitos disparan, severidad
  no bloqueante) se basa en la filosofía SpecBox "avisar, no impedir" y en el
  arranque rápido de v6.6.2 — no requiere validación externa adicional.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno.
- **Nuevos JTBDs introducidos**: ninguno a nivel producto (JR-FPG.* y JE-FPG.*
  derivan de JE-G.1 / JE-G.3 existentes).
- **Resolución**: `no_drift`

## Verdict

**READY_FOR_PRD**

---

> Next step: `/prd prerequisites_gate`
