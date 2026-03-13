# Neon (Serverless Postgres) - Patrones de Infraestructura

> SpecBox Engine v3.9.0 | Referencia de patrones para Neon Database

---

## 1. Cuando usar Neon vs Supabase

| Criterio | Neon | Supabase |
|----------|------|----------|
| Backend propio (Next.js, Remix) | Recomendado | Posible |
| Auth + RLS + Realtime integrado | No incluido | Recomendado |
| Flutter como cliente directo | No recomendado | Recomendado |
| Branching de base de datos | Nativo | No disponible |
| Costo en reposo (scale to zero) | Gratuito | Plan minimo |
| ORM preferido | Drizzle / Prisma | Cliente propio |

**Regla general:** Usar Neon cuando el proyecto tiene backend propio (Next.js API routes, servidor Express) y no necesita las funcionalidades integradas de Supabase (Auth, Realtime, Storage).

---

## 2. Conexion con @neondatabase/serverless

### Instalacion

```bash
npm install @neondatabase/serverless
```

### Conexion basica

```typescript
import { neon } from '@neondatabase/serverless';

const sql = neon(process.env.DATABASE_URL!);

const users = await sql`SELECT * FROM users WHERE active = true`;
```

### Connection pooling (para entornos serverless)

```typescript
import { Pool } from '@neondatabase/serverless';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

const client = await pool.connect();
try {
    const result = await client.query('SELECT * FROM {table} WHERE id = $1', [id]);
    return result.rows;
} finally {
    client.release();
}
```

### Buenas practicas de conexion

- Usar el driver `@neondatabase/serverless` en entornos edge/serverless (Vercel, Cloudflare).
- Usar `Pool` cuando se necesitan multiples queries en la misma peticion.
- Usar el conector `neon()` directo para queries individuales (mas simple).
- Configurar `DATABASE_URL` con el sufijo `?sslmode=require`.

---

## 3. Estrategia de branching

### Ramas de base de datos

```
main (produccion)
  |-- staging (pre-produccion)
  |-- dev (desarrollo compartido)
  |-- feature/{nombre} (efimera, por feature)
```

### Flujo de trabajo

1. Crear rama `feature/{nombre}` desde `dev` para desarrollo.
2. Aplicar migraciones en la rama feature.
3. Hacer merge de la rama feature a `dev` para pruebas.
4. Promover migraciones de `dev` a `staging` para QA.
5. Promover de `staging` a `main` para produccion.

### Crear rama via CLI

```bash
neonctl branches create --name feature/{nombre} --parent dev
```

### Eliminar rama efimera

```bash
neonctl branches delete feature/{nombre}
```

**Regla:** Las ramas feature son efimeras. Eliminarlas tras hacer merge para evitar costos innecesarios.

---

## 4. Integracion con Drizzle ORM

### Instalacion

```bash
npm install drizzle-orm @neondatabase/serverless
npm install -D drizzle-kit
```

### Definicion de esquema

```typescript
// src/db/schema/{table}.ts
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core';

export const {table} = pgTable('{table}', {
    id: uuid('id').primaryKey().defaultRandom(),
    name: text('name').notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});
```

### Instancia del cliente

```typescript
// src/db/index.ts
import { drizzle } from 'drizzle-orm/neon-http';
import { neon } from '@neondatabase/serverless';
import * as schema from './schema';

const sql = neon(process.env.DATABASE_URL!);
export const db = drizzle(sql, { schema });
```

### Consultas tipicas

```typescript
import { db } from '@/db';
import { {table} } from '@/db/schema/{table}';
import { eq } from 'drizzle-orm';

// Select
const items = await db.select().from({table}).where(eq({table}.userId, userId));

// Insert
await db.insert({table}).values({ name: 'Nuevo item' });

// Update
await db.update({table}).set({ name: 'Actualizado' }).where(eq({table}.id, id));
```

---

## 5. Patrones de migracion

### Configuracion de Drizzle Kit

```typescript
// drizzle.config.ts
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
    schema: './src/db/schema',
    out: './drizzle/migrations',
    dialect: 'postgresql',
    dbCredentials: {
        url: process.env.DATABASE_URL!,
    },
});
```

### Comandos de migracion

```bash
# Generar migracion desde cambios en el esquema
npx drizzle-kit generate

# Aplicar migraciones pendientes
npx drizzle-kit migrate

# Inspeccionar esquema actual (Drizzle Studio)
npx drizzle-kit studio
```

### Convencion de nombres

Las migraciones generadas por Drizzle Kit usan formato numerico automatico. No renombrar los archivos generados. Documentar el proposito en el archivo `meta/_journal.json` si es necesario.

### Reglas

- Nunca modificar una migracion ya aplicada en staging o produccion.
- Ejecutar migraciones en la rama Neon correspondiente antes de hacer merge.
- Validar migraciones en rama feature antes de promover a dev.
