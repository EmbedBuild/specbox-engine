---
name: manual-test
description: >
  Systematic manual testing with live bug resolution and stakeholder evidence.
  Use when the user says "manual test", "pruebas manuales", "test plan",
  "monta el sistema de pruebas manual", "testear la app", or wants to
  validate features interactively before a demo or release.
  The user provides screenshots, the agent diagnoses and fixes bugs in real-time.
context: direct
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(*), Agent, WebFetch, mcp__supabase__execute_sql, mcp__supabase__list_tables, mcp__supabase__apply_migration
triggers:
  - manual-test
  - pruebas manuales
  - test plan
  - testing manual
  - QA manual
  - stakeholder demo
  - pre-release testing
---

# /manual-test — Pruebas Manuales Sistemáticas

Sistema de testing manual interactivo: el agente prepara itinerarios, seed data, y guía al usuario paso a paso. Ante bugs, diagnostica y resuelve en el momento. Genera evidencia auditable para stakeholders.

---

## Sub-comandos

| Comando | Acción |
|---------|--------|
| `/manual-test` | Genera plan completo desde cero + empieza IT-1 |
| `/manual-test status` | Muestra resumen ejecutivo del progreso |
| `/manual-test next` | Prepara y empieza siguiente itinerario pendiente |
| `/manual-test seed IT-N` | Ejecuta seed data de un itinerario específico |
| `/manual-test report` | Genera informe de evidencia para stakeholders |
| `/manual-test reset IT-N` | Resetea un itinerario para re-testear |

---

## Paso 0 — Detectar contexto del proyecto

Antes de cualquier acción:

1. Leer `CLAUDE.md` del proyecto para entender stack, arquitectura, BD
2. Buscar spec/PRD: revisar si existe SpecBox (`list_us`, `list_uc`) o archivos `doc/prd/`, `doc/spec/`
3. Identificar BD: buscar config de Supabase, PostgreSQL, Firebase, etc.
4. Detectar rutas: leer el router (GoRouter, React Router, etc.) para mapear URLs a features
5. Detectar roles de usuario: buscar enum/constantes de roles (rider, sponsor, team_admin, etc.)

Guardar hallazgos en variables internas para los pasos siguientes.

---

## Paso 1 — Generar plan de itinerarios

A partir de los UCs/USs del proyecto, generar itinerarios agrupados por **flujo funcional** (no por UC individual).

### Reglas de agrupación

```
Principio: Un itinerario = un flujo end-to-end que un usuario real haría.

Agrupar por:
1. Flujos de entrada (auth: registro → verificación → selección de rol)
2. Flujos de onboarding (uno por rol: rider, sponsor, team, etc.)
3. Flujos de feature core (perfil, suscripción, contenido, dashboard)
4. Flujos transversales (i18n, notificaciones, reset password)
5. Flujos de protección (guardian, admin, moderación)

Cada itinerario debe:
- Tener 3-9 pasos (ni muy granular ni muy amplio)
- Cubrir 1-6 UCs relacionados
- Ser independiente (ejecutable sin completar otros IT, excepto auth)
- Tener precondiciones claras (rol, seed data, estado)
```

### Formato del itinerario

```markdown
| IT-N | Nombre descriptivo | UCs cubiertos | Pasos | Estado |
```

Para cada itinerario, generar internamente:
- **Precondiciones**: rol necesario, onboarding completado o no, seed data
- **Seed SQL**: queries INSERT para poblar la BD con datos de test
- **Pasos**: tabla con #, descripción, ruta, AC esperado
- **Postcondiciones**: queries SELECT para verificar estado tras el test

---

## Paso 2 — Crear archivo de evidencia

Crear `doc/testing/manual-test-evidence.md` usando la plantilla:

```markdown
# Registro de Pruebas Manuales — {proyecto}

**Proyecto**: {nombre}
**Tester**: {nombre del usuario} (rol)
**Asistido por**: Claude Code (Opus 4.7)
**Fecha inicio**: {fecha}
**Entorno**: localhost ({stack}) + {BD}

---

## Resumen ejecutivo

| Itinerario | UCs | Pasos | Pass | Fail | Blocked | Estado |
|-----------|-----|:-----:|:----:|:----:|:-------:|--------|
{tabla generada en Paso 1}

---

## Bugs encontrados y resueltos durante testing

| # | Bug | Severidad | Commit fix | Estado |
|---|-----|-----------|-----------|--------|

---

{secciones por itinerario — se rellenan conforme se ejecutan}
```

---

## Paso 3 — Preparar seed data

Para cada itinerario que requiera datos:

1. **Verificar estructura de BD**: `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '...'`
2. **Verificar CHECK constraints**: `SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = '...'::regclass AND contype = 'c'`
3. **Verificar FK constraints**: evitar insertar con UUIDs falsos si hay FKs a `auth.users`
4. **Generar SQL de seed** con datos realistas y variados (diferentes estados, fechas distribuidas en 6 meses, etc.)
5. **Guardar seed** en `doc/testing/seeds/it-{N}-{nombre}.sql` para reproducibilidad

### Patrón de seed por tipo de dato

```sql
-- Fechas distribuidas en 6 meses
now() - interval 'N months' + interval 'M days'

-- Usar UUIDs reales de auth.users para FKs
-- Si solo hay 1 usuario, reutilizarlo para testing

-- Verificar valores válidos de CHECK constraints antes de insertar
-- Ejemplo: status puede ser 'paid'|'pending'|'failed', NO 'completed'
```

---

## Paso 4 — Ejecutar itinerario interactivo

Para cada itinerario pendiente:

### 4.1 — Preparación
1. Verificar precondiciones (rol del usuario, onboarding status)
2. Ejecutar seed SQL si necesario
3. Informar al usuario: "Hot restart y navega a {ruta}. Mándame screenshot."

### 4.2 — Ejecución paso a paso
Para cada paso del itinerario:

1. **Indicar al usuario** qué hacer: "Rellena X, haz clic en Y, mándame screenshot"
2. **Analizar screenshot** que envía el usuario
3. **Si PASS**: marcar paso, pedir siguiente acción
4. **Si FAIL/BUG detectado**:
   a. Leer el error (en pantalla, en logs, en consola)
   b. Diagnosticar causa raíz leyendo el código
   c. Aplicar fix en el código
   d. Verificar que compila (`flutter analyze` / `npm run lint` / etc.)
   e. Registrar como BUG-XXX en la tabla de bugs
   f. Pedir al usuario que recargue y reintente el paso

### 4.3 — Cierre del itinerario
1. Actualizar tabla de resumen ejecutivo (pass/fail/blocked counts)
2. Documentar la sección detallada del itinerario en el evidence file
3. Si hay bugs resueltos, guardar en engram memory

### Patrones de bugs comunes a buscar proactivamente

| Patrón | Causa típica | Diagnóstico |
|--------|-------------|-------------|
| "No encontrado" en una page autenticada | Router pasa `profileId` en vez de `userId` | Verificar qué ID pasa el router vs qué busca el repository |
| Redirect loop tras completar un flujo | `profileNotifier` no refrescado | Añadir `AuthCheckRequested` antes de `context.go()` |
| PostgrestException UUID inválido | Ruta paramétrica (`/:id`) captura ruta estática (`/dashboard`) | Mover rutas estáticas ANTES de paramétrizadas |
| Status/type mismatch | Código usa 'completed' pero BD permite solo 'paid' | Verificar CHECK constraints de la tabla |
| Columna no existe (PGRST204) | Código referencia campo que no está en la tabla | Añadir columna vía migración |
| JOIN sin FK (PGRST200) | Query intenta relacionar tablas sin foreign key | Añadir FK o cambiar la query |

---

## Paso 5 — Cambio de rol para testear otros flujos

Cuando un itinerario requiere un rol diferente al actual:

### Opción A — Reutilizar usuario existente (más rápido)
```sql
UPDATE profiles SET role = '{nuevo_rol}', onboarding_completed = false
WHERE user_id = '{user_id}';
```

### Opción B — Crear usuario nuevo (más realista)
- Solo si la BD permite insertar en `auth.users` directamente
- Si hay FK constraints que lo impiden, usar Opción A

### Restaurar estado original después
```sql
UPDATE profiles SET role = '{rol_original}', onboarding_completed = true
WHERE user_id = '{user_id}';
```

---

## Paso 6 — Generar informe para stakeholders

Al invocar `/manual-test report`:

1. Leer `doc/testing/manual-test-evidence.md`
2. Calcular métricas:
   - Total itinerarios completados / pendientes
   - Total pasos pass / fail / blocked
   - Total bugs encontrados / resueltos / abiertos
   - Cobertura de UCs testeados vs total
3. Generar resumen ejecutivo con formato stakeholder-friendly
4. Listar bugs críticos abiertos (si hay)
5. Dar veredicto: READY FOR DEMO / BLOQUEADO POR {bugs}

---

## Checklist

Antes de marcar un itinerario como COMPLETADO, verificar:

- [ ] Todos los pasos ejecutados con resultado (PASS/FAIL/BLOCKED)
- [ ] Bugs encontrados registrados con severidad y estado
- [ ] Bugs bloqueantes resueltos (no quedan FAIL sin fix)
- [ ] Seed data documentado (reproducible)
- [ ] Resumen ejecutivo actualizado
- [ ] Evidence file tiene la sección detallada del itinerario

---

## Referencia rápida

### Severidades de bugs
| Severidad | Criterio |
|-----------|---------|
| Bloqueante | Impide continuar el flujo, crash, data loss |
| Mayor | Funcionalidad rota pero hay workaround |
| Menor | UI issue, texto incorrecto, no bloquea |
| Configuración | Requiere cambio en infra/BD, no en código |

### Estructura de archivos generados
```
doc/testing/
├── manual-test-evidence.md    ← Registro vivo principal
├── manual-test-plan.md        ← Plan detallado (opcional)
└── seeds/
    ├── it-01-{nombre}.sql
    ├── it-02-{nombre}.sql
    └── ...
```
