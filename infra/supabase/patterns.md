# Supabase - Patrones de Infraestructura

> jps_dev_engine v3.5.0 | Referencia de patrones, herramientas MCP y plantillas

---

## 1. Herramientas MCP disponibles

| Herramienta | Descripcion |
|-------------|-------------|
| `mcp__supabase__list_tables` | Listar tablas del proyecto |
| `mcp__supabase__apply_migration` | Aplicar migracion SQL |
| `mcp__supabase__execute_sql` | Ejecutar SQL arbitrario (solo lectura recomendado) |
| `mcp__supabase__list_migrations` | Listar migraciones aplicadas |
| `mcp__supabase__list_extensions` | Listar extensiones habilitadas |
| `mcp__supabase__get_project` | Obtener detalles del proyecto |
| `mcp__supabase__get_logs` | Consultar logs del proyecto |
| `mcp__supabase__deploy_edge_function` | Desplegar Edge Function |
| `mcp__supabase__get_edge_function` | Obtener detalles de una Edge Function |
| `mcp__supabase__list_edge_functions` | Listar Edge Functions desplegadas |
| `mcp__supabase__generate_typescript_types` | Generar tipos TS desde el esquema |

### Flujo tipico con MCP

```
1. list_tables          -> Inspeccionar esquema actual
2. apply_migration      -> Aplicar cambios DDL
3. execute_sql          -> Verificar datos / consultas
4. generate_typescript_types -> Actualizar tipos del cliente
```

---

## 2. Patrones de diseno de esquema

### Columnas estandar para toda tabla

```sql
CREATE TABLE {table} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Trigger de updated_at automatico

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON {table}
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
```

### Enums como tipos Postgres

```sql
CREATE TYPE {project}_status AS ENUM ('draft', 'active', 'archived');

ALTER TABLE {table} ADD COLUMN status {project}_status NOT NULL DEFAULT 'draft';
```

### Soft delete

```sql
ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Indice parcial para consultas que ignoran eliminados
CREATE INDEX idx_{table}_active ON {table} (id) WHERE deleted_at IS NULL;
```

### Foreign keys con usuario

```sql
ALTER TABLE {table}
    ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX idx_{table}_user ON {table} (user_id);
```

---

## 3. Plantillas de politicas RLS

### Habilitar RLS

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
```

### Patron: Solo el propietario (owner-based)

```sql
CREATE POLICY "{table}_owner_select" ON {table}
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "{table}_owner_insert" ON {table}
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "{table}_owner_update" ON {table}
    FOR UPDATE USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "{table}_owner_delete" ON {table}
    FOR DELETE USING (auth.uid() = user_id);
```

### Patron: Basado en rol (role-based)

```sql
CREATE POLICY "{table}_admin_all" ON {table}
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'admin'
        )
    );

CREATE POLICY "{table}_member_select" ON {table}
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role IN ('admin', 'member')
        )
    );
```

### Patron: Lectura publica, escritura autenticada

```sql
CREATE POLICY "{table}_public_read" ON {table}
    FOR SELECT USING (true);

CREATE POLICY "{table}_auth_insert" ON {table}
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "{table}_owner_modify" ON {table}
    FOR UPDATE USING (auth.uid() = user_id);
```

---

## 4. Convencion de migraciones

### Formato de nombre

```
YYYYMMDDHHMMSS_{accion}_{tabla_o_descripcion}.sql
```

### Ejemplos

```
20260224120000_create_profiles.sql
20260224120100_add_status_to_projects.sql
20260224120200_create_rls_policies_tasks.sql
20260224120300_create_index_tasks_user.sql
```

### Reglas

- Una migracion por cambio logico (no mezclar creacion de tabla con RLS).
- Las migraciones son inmutables una vez aplicadas en staging/produccion.
- Incluir sentencias `DROP` o `ALTER` de rollback como comentario al final.

---

## 5. Patrones de Realtime

### Suscripcion a cambios en tabla

```typescript
const channel = supabase
    .channel('{table}_changes')
    .on('postgres_changes', {
        event: '*',           // 'INSERT' | 'UPDATE' | 'DELETE'
        schema: 'public',
        table: '{table}',
        filter: 'user_id=eq.{user_id}'
    }, (payload) => {
        console.log('Cambio:', payload);
    })
    .subscribe();
```

### Limpieza de suscripcion

```typescript
// Siempre desuscribirse al desmontar
supabase.removeChannel(channel);
```

### Buenas practicas Realtime

- Filtrar por columna para reducir trafico.
- No suscribirse a tablas con alto volumen sin filtro.
- Usar `event` especifico en lugar de `*` cuando sea posible.

---

## 6. Storage (buckets)

### Crear bucket via migracion

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('{bucket_name}', '{bucket_name}', false);
```

### Politica de storage: solo el propietario

```sql
CREATE POLICY "{bucket}_owner_upload"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = '{bucket_name}'
    AND auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "{bucket}_owner_read"
ON storage.objects FOR SELECT
USING (
    bucket_id = '{bucket_name}'
    AND auth.uid()::text = (storage.foldername(name))[1]
);
```

### Estructura de archivos recomendada

```
{bucket_name}/{user_id}/{categoria}/{archivo}
```

---

## 7. Edge Functions

### Estructura de archivo

```
supabase/functions/{function_name}/index.ts
```

### Plantilla base

```typescript
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

serve(async (req) => {
    const supabase = createClient(
        Deno.env.get('SUPABASE_URL')!,
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    const { data, error } = await supabase.from('{table}').select('*');

    return new Response(JSON.stringify({ data, error }), {
        headers: { 'Content-Type': 'application/json' },
    });
});
```

### Despliegue via MCP

```
mcp__supabase__deploy_edge_function(function_slug, code)
```

---

## 8. Patron DataSource (arquitectura de aplicacion)

### Regla fundamental

> **Nunca inyectar `SupabaseClient` directamente en repositorios o casos de uso.**

### Estructura

```
SupabaseClient (SDK)
    |
SupabaseDatasource (traduce llamadas SDK a datos puros)
    |
Repository (trabaja con entidades del dominio)
    |
UseCase / Service
```

### Ejemplo en Dart/Flutter

```dart
abstract class TaskRemoteDatasource {
    Future<List<Map<String, dynamic>>> getTasks(String userId);
    Future<void> createTask(Map<String, dynamic> data);
}

class SupabaseTaskDatasource implements TaskRemoteDatasource {
    final SupabaseClient _client;

    SupabaseTaskDatasource(this._client);

    @override
    Future<List<Map<String, dynamic>>> getTasks(String userId) async {
        final response = await _client
            .from('tasks')
            .select()
            .eq('user_id', userId)
            .order('created_at');
        return List<Map<String, dynamic>>.from(response);
    }

    @override
    Future<void> createTask(Map<String, dynamic> data) async {
        await _client.from('tasks').insert(data);
    }
}
```

### Beneficios

- El repositorio no conoce Supabase; solo trabaja con mapas o entidades.
- Se puede reemplazar el datasource sin tocar logica de negocio.
- Facilita testing con mocks del datasource.
