# Plan: Backend Nativo — SpecBox en equipo (multi-developer)

> Generado: 2026-05-21
> Origen: US-NATIVE-BACKEND (FreeForm `ff-ed0c02f4565a`)
> PRD: [doc/prd/native_backend_team_prd.md](../prd/native_backend_team_prd.md)
> Estado: Pendiente
> Tipo: Backend-only (sin UI → no aplica análisis UI, VEG ni Stitch)

---

## Resumen

Añadir un 4º backend `NativeBackend` sobre Postgres interno (Modo A: solo el MCP
tiene credenciales de BBDD) + un módulo de coordinación `server/coordination/`
fuera del `SpecBackend` ABC, para soportar desarrollo en equipo sin pisotones de
US/UC ni colisión de branches. Alcance v1 = H1 (source-of-truth) + H2 (identidad)
+ H3 (claims).

---

## Análisis de Componentes UI

**N/A** — Este US es infraestructura del engine (Python/FastMCP + Postgres). No
hay pantallas. Pasos 2, 2.5b (VEG) y 6 (Stitch) del flujo /plan no aplican.
`stitch_designs: N/A`.

---

## Hallazgos del código actual (lo que se reutiliza vs lo nuevo)

| Pieza | Estado actual | Acción |
|-------|---------------|--------|
| `SpecBackend` ABC | 26 métodos abstractos en [server/spec_backend.py:137](../../server/spec_backend.py#L137) | **NO tocar** — NativeBackend los implementa |
| Dispatch de backend | [server/auth_gateway.py:42-66](../../server/auth_gateway.py#L42) `get_session_backend` if/elif por `backend_type` | **Modificar**: añadir rama `elif backend_type == "native"` |
| Credenciales por sesión | `store_freeform_credentials` / `store_plane_credentials` (auth_gateway.py:100-134) | **Añadir**: `store_native_credentials(ctx, token, project_id)` |
| Driver Postgres | **NO existe** en pyproject.toml | **Añadir** `asyncpg` a dependencies |
| Tests de backend | `tests/` (pendiente confirmar contract test parametrizado) | **Añadir/extender** suite de conformidad (AC-01) |
| Coordinación (claims/identidad) | **NO existe** | **Crear** módulo `server/coordination/` |

> El dispatch hoy hace `from .backends.X import XBackend; return XBackend(...)`.
> NativeBackend sigue el mismo patrón lazy-import. Frontera 2 (credencial de BBDD)
> se lee de env del VPS dentro de `NativeBackend.__init__`, nunca del `config`.

---

## Fases de Implementación

### Fase 1 — Esquema Postgres multi-tenant (UC-102)

- [ ] Crear `server/db/migrations/0001_native_schema.sql`: tablas `projects`,
  `user_stories`, `use_cases`, `acceptance_criteria` con `project_id` FK +
  columna `version` (entero, default 1) en cada tabla de spec. **(AC-04, AC-03)**
- [ ] Idempotencia: `CREATE TABLE IF NOT EXISTS` + migración re-aplicable. **(AC-04)**
- [ ] Índices por `project_id` para aislamiento eficiente. **(AC-05)**
- [ ] Módulo `server/db/pool.py`: pool `asyncpg` inicializado al arrancar el MCP. **(AC-02)**
- [ ] Añadir `asyncpg` a `pyproject.toml` dependencies.
- Estimación: 8h

### Fase 2 — NativeBackend sobre el ABC (UC-101, UC-103)

- [ ] Crear `server/backends/native_backend.py`: `NativeBackend(SpecBackend)`
  implementando los 26 métodos abstractos sobre Postgres vía el pool. **(AC-01)**
- [ ] Frontera 2: credencial de servicio leída de env del VPS en `__init__`,
  nunca del `config` de sesión. **(AC-14)**
- [ ] Concurrencia optimista: `update_item` / `update_acceptance_criterion`
  incrementan `version`; UPDATE con `version` stale → error `STALE_VERSION`. **(AC-03)**
- [ ] Cablear dispatch: rama `elif backend_type == "native"` en
  `get_session_backend` ([auth_gateway.py:42](../../server/auth_gateway.py#L42))
  + `store_native_credentials`. **(AC-07)**
- [ ] `set_auth_token(backend_type="native", ...)` + `detect_project_backend`
  prioriza `native` cuando `specbox.backend_type="native"`. **(AC-07)**
- [ ] `import_spec` round-trip US/UC/AC en Postgres. **(AC-08)**
- Estimación: 22h

### Fase 3 — Identidad de developer (UC-201, UC-202, UC-203) — Frontera 1

- [ ] Tabla `developers` (`developer_id` PK, `display_name`, `token_hash`) en
  migración `0002_developers.sql`. Tokens hasheados. **(AC-10)**
- [ ] Token de dev en `settings.local.json` (`specbox.native.token`), adjuntado
  por el cliente MCP; nunca en logs del server. **(AC-11)**
- [ ] `server/coordination/identity.py`: resolución token → developer,
  autenticación (UNAUTHENTICATED) + autorización dev↔project (FORBIDDEN). **(AC-12, AC-13)**
- [ ] Tool `whoami()`. **(AC-15)**
- Estimación: 21h

### Fase 4 — Claims de UC (UC-301, UC-302, UC-303, UC-304) — Coordinación

- [ ] `server/coordination/claims.py`: tabla `uc_claims` con `UNIQUE(uc_id)`;
  `claim_uc` / `release_uc` (NOT_CLAIM_OWNER si ajeno). **(AC-16, AC-17)**
- [ ] `start_uc` consulta claims; crea claim + estado in_progress en una
  transacción (sin huérfano); conflicto con owner/claimed_at/branch. **(AC-18, AC-19)**
- [ ] `find_next_uc` excluye UCs con claim activo de otro dev. **(AC-20)**
- [ ] `server/coordination/branches.py`: `branch_registry`
  (project_id, uc_id, branch, dev); rechaza colisión; naming `feature/{uc_id}-{slug}`. **(AC-23)**
- [ ] `.quality/active_uc.json` pasa a cache del claim remoto; `spec-guard.mjs`
  lo acepta offline y revalida contra el MCP con red. **(AC-21, AC-22)**
- Estimación: 22h

### Fase 5 — QA y conformidad

- [ ] Contract test que ejecuta la misma suite sobre Freeform y Native. **(AC-01)**
- [ ] Test de carrera: 2 `claim_uc` paralelos → 1 OK, 1 ALREADY_CLAIMED. **(AC-16)**
- [ ] Test de aislamiento por `project_id`. **(AC-05)**
- [ ] Test de pool: 50 ops concurrentes, conteo `pg_stat_activity`. **(AC-02)**
- [ ] Regresión de los 3 backends existentes en verde. **(AC-09)**
- [ ] Coverage 85%+ en módulos nuevos.
- Estimación: 12h

---

## Orden de implementación recomendado

`Fase 1 (esquema)` → `Fase 2 (NativeBackend)` → `Fase 3 (identidad)` →
`Fase 4 (claims)` → `Fase 5 (QA)`. La identidad (H2) es prerequisito duro de los
claims (H3): sin `developer_id` no hay "quién tiene el UC".

Mapeo a UCs (1 UC = 1 ciclo /implement): UC-102 → UC-101 → UC-103 → UC-201 →
UC-202 → UC-203 → UC-301 → UC-302 → UC-303 → UC-304.

---

## Alternativas y Tradeoffs

| Decisión | Elegida | Descartada | Razón |
|----------|---------|------------|-------|
| Topología | Modo A (MCP única puerta) | Modo B (acceso directo + RLS) | Una sola superficie de seguridad; abstracción intacta |
| BBDD | Postgres interno VPS | Supabase gestionado | Control total, sin dependencia de tercero (decisión del usuario) |
| Coordinación | Módulo aparte `server/coordination/` | Métodos en el `SpecBackend` ABC | No contaminar la abstracción; 3 backends quedan limpios |
| Tenancy | Una instancia multi-tenant | Esquema por proyecto | Source-of-truth única + visibilidad cross-proyecto gratis |
| Driver | asyncpg | psycopg | Async-native, coherente con FastMCP |

---

## Riesgos (heredados del PRD)

- MCP pasa a punto crítico de escritura → mitigado por cache offline de
  active_uc.json; degradación completa es H5 (fuera de v1).
- Credencial de servicio de Postgres = joya de la corona → solo env del VPS.
- Claim huérfano → atomicidad transaccional (AC-18).
- Scope creep hacia "otro Jira" → teams completos fuera de v1 (H4).

---

## Archivos a Crear/Modificar

```
server/
├── db/
│   ├── pool.py                          # CREAR — pool asyncpg
│   └── migrations/
│       ├── 0001_native_schema.sql       # CREAR — projects + spec + version
│       └── 0002_developers.sql          # CREAR — developers + uc_claims + branch_registry
├── backends/
│   └── native_backend.py                # CREAR — NativeBackend(SpecBackend)
├── coordination/                        # CREAR — módulo nuevo (fuera del ABC)
│   ├── __init__.py
│   ├── identity.py                      # developers, tokens, whoami, authz
│   ├── claims.py                        # uc_claims, claim/release
│   └── branches.py                      # branch_registry
├── auth_gateway.py                      # MODIFICAR — rama "native" + store_native_credentials
└── tools/
    └── spec_driven.py                   # MODIFICAR — start_uc/find_next_uc consultan claims
.claude/hooks/
└── spec-guard.mjs                       # MODIFICAR — active_uc.json como cache + revalidación
pyproject.toml                           # MODIFICAR — añadir asyncpg
tests/
└── (contract test parametrizado Freeform+Native)  # CREAR/EXTENDER
```

---

## Referencias

- PRD: [doc/prd/native_backend_team_prd.md](../prd/native_backend_team_prd.md)
- SpecBackend ABC: [server/spec_backend.py:137](../../server/spec_backend.py#L137)
- Dispatch actual: [server/auth_gateway.py:42](../../server/auth_gateway.py#L42)
