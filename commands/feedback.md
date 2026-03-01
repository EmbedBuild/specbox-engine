# /feedback

> Referencia legacy — la implementacion activa esta en `.claude/skills/feedback/SKILL.md`

## Uso

```
/feedback [feature] [--ac AC-XX] [--severity critical|major|minor]
/feedback resolve FB-NNN
/feedback list [feature]
```

## Que hace

Captura feedback de testing manual del desarrollador como evidencia estructurada:

1. Detecta feature (desde rama o argumento)
2. Localiza PRD y AC-XX disponibles
3. Recopila feedback: description, expected, actual, severity
4. Crea JSON local en `.quality/evidence/{feature}/feedback/FB-NNN.json`
5. Crea GitHub issue con labels `[feedback, {severity}]`
6. Si el feedback invalida un AC-XX con PASS → cambia verdict a INVALIDATED
7. Actualiza feedback-summary.json

## Severity y merge

| Severity | Bloquea merge |
|----------|:---:|
| critical | Si |
| major | Si |
| minor | No |

## Sub-comandos

- `resolve FB-NNN` — Marca como resuelto, cierra GitHub issue, AC-XX → NEEDS_REVALIDATION
- `list [feature]` — Tabla resumen de todos los feedback

## Agente

AG-10: Developer Tester (`agents/developer-tester.md`)

## Ver tambien

- `.claude/skills/feedback/SKILL.md` — Skill activo con instrucciones completas
- `agents/developer-tester.md` — Definicion del agente AG-10
