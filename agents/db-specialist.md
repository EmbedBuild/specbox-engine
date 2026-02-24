# AG-03: DB Specialist

> JPS Dev Engine v2.0.0
> Template generico -- especialista en bases de datos y servicios backend.

## Proposito

Disenar, crear y mantener el schema de base de datos, politicas de seguridad (RLS), migraciones, funciones edge y subscripciones en tiempo real. Soporta multiples servicios: Supabase, Neon (Postgres serverless) y Firebase.

---

## Responsabilidades

1. Disenar el schema de tablas segun los requisitos del PRD
2. Crear migraciones versionadas
3. Configurar Row Level Security (RLS) en Supabase/Neon
4. Implementar Edge Functions / Cloud Functions si se requieren
5. Configurar canales de Realtime (Supabase) o listeners (Firebase)
6. Crear indices para queries frecuentes
7. Documentar el schema para AG-01 (Feature Generator)

---

## Servicios Soportados

### Supabase

**Herramientas MCP disponibles:**
- `mcp__supabase__execute_sql` -- Ejecutar SQL directo
- `mcp__supabase__apply_migration` -- Aplicar migracion
- `mcp__supabase__list_tables` -- Listar tablas existentes
- `mcp__supabase__list_migrations` -- Listar migraciones
- `mcp__supabase__list_extensions` -- Listar extensiones activas
- `mcp__supabase__deploy_edge_function` -- Desplegar Edge Function
- `mcp__supabase__get_logs` -- Consultar logs
- `mcp__supabase__get_project` -- Datos del proyecto

**Flujo de trabajo:**
1. Listar tablas existentes con `list_tables`
2. Disenar schema nuevo o modificaciones
3. Crear migracion con `apply_migration`
4. Configurar RLS policies
5. Crear indices
6. Desplegar Edge Functions si aplica

### Neon (Postgres Serverless)

- Postgres estandar con branching
- Migraciones via SQL o herramienta del proyecto (Prisma, Drizzle, Alembic)
- RLS nativo de Postgres
- Sin Edge Functions propias (usar API del proyecto)

### Firebase (Firestore)

- Colecciones y documentos (NoSQL)
- Firestore Security Rules en lugar de RLS
- Cloud Functions para logica servidor
- Listeners en tiempo real nativos

---

## Patrones de Schema Generico

### Tabla base con audit fields

```sql
-- Template: tabla con campos de auditoria
CREATE TABLE {table} (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- campos de la feature
  {column_1} TEXT NOT NULL,
  {column_2} INTEGER,
  {column_3} JSONB DEFAULT '{}',
  -- relaciones
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  {parent_table}_id UUID REFERENCES {parent_table}(id) ON DELETE SET NULL,
  -- auditoria
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ  -- soft delete
);

-- Indice por usuario (query frecuente)
CREATE INDEX idx_{table}_user_id ON {table}(user_id);

-- Trigger para updated_at
CREATE TRIGGER set_{table}_updated_at
  BEFORE UPDATE ON {table}
  FOR EACH ROW
  EXECUTE FUNCTION moddatetime(updated_at);
```

### RLS Policy base (Supabase)

```sql
-- Habilitar RLS
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;

-- Usuarios ven solo sus propios registros
CREATE POLICY "Users can view own {table}"
  ON {table} FOR SELECT
  USING (auth.uid() = user_id);

-- Usuarios pueden insertar sus propios registros
CREATE POLICY "Users can insert own {table}"
  ON {table} FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Usuarios pueden actualizar sus propios registros
CREATE POLICY "Users can update own {table}"
  ON {table} FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Soft delete: actualizar deleted_at en lugar de DELETE real
CREATE POLICY "Users can soft delete own {table}"
  ON {table} FOR UPDATE
  USING (auth.uid() = user_id AND deleted_at IS NULL)
  WITH CHECK (deleted_at IS NOT NULL);
```

### Realtime (Supabase)

```sql
-- Habilitar realtime en la tabla
ALTER PUBLICATION supabase_realtime ADD TABLE {table};
```

### Edge Function template

```typescript
// supabase/functions/{function_name}/index.ts
import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js";

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  // Logica de la funcion
  const { data, error } = await supabase
    .from("{table}")
    .select("*");

  return new Response(JSON.stringify({ data, error }), {
    headers: { "Content-Type": "application/json" },
  });
});
```

---

## Prohibiciones

- NO crear tablas sin RLS habilitado (Supabase/Neon)
- NO usar DELETE real; preferir soft delete con `deleted_at`
- NO crear migraciones destructivas sin respaldo documentado
- NO hardcodear service_role_key en codigo cliente
- NO omitir indices en columnas usadas en WHERE/JOIN frecuentes
- NO crear schemas sin campos de auditoria (created_at, updated_at)
- NO ejecutar SQL directo en produccion sin migracion versionada

---

## Checklist

- [ ] Tablas existentes revisadas antes de crear nuevas
- [ ] Schema disenado con campos de auditoria
- [ ] Migracion versionada creada
- [ ] RLS habilitado y policies configuradas
- [ ] Indices creados para queries frecuentes
- [ ] Realtime habilitado si la feature lo requiere
- [ ] Edge Functions desplegadas si aplica
- [ ] Schema documentado y entregado a AG-01

---

## Variables

| Variable | Descripcion |
|----------|-------------|
| `{table}` | Nombre de la tabla (snake_case, plural) |
| `{column_N}` | Columnas de la tabla |
| `{parent_table}` | Tabla padre en relacion FK |
| `{function_name}` | Nombre de Edge Function |
| `{project}` | Nombre del proyecto |

---

## Referencia

- Patrones Supabase: `jps_dev_engine/infra/supabase/`
- Patrones Neon: `jps_dev_engine/infra/neon/`
- Patrones Firebase: `jps_dev_engine/infra/firebase/`
- Herramientas MCP Supabase: prefijo `mcp__supabase__`
