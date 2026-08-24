-- 0018_organizations_backfill.sql
-- SpecBox NativeBackend — backfill existing data into organizations (US-13 / UC-1302).
--
-- WHY: migration 0017 added the organizations tables and the NULLABLE
-- `projects.organization_id` column. This migration populates them: it creates
-- the real organizations of the production tenant and assigns every existing
-- project + developer to its org. After this runs, no project has a NULL
-- organization_id, so a follow-up can set the column NOT NULL (two-pass).
--
-- MAP (decided by the operator, NOT "everything to one default org"):
--   Embed.Build         (embed-build)         admin=jesusperezdeveloper
--       projects: ddboss-web-saas, EmbedBuild/specbox-manager, hq-embed-build,
--                 moto.fan, jesusperezdeveloper/potencial_digital_2026
--   Automatio Solutions (automatio-solutions) admin=holadanimestre-arch, member=borjina-gif
--       projects: lorido-seguros, obraos
--   VA360Labs           (va360labs)           admin=valen18      (no projects yet)
--   Nani's Org          (nanis-org)           admin=nani0004     (no projects yet)
--
-- The org `id` is the slug itself — stable, readable, URL-safe.
--
-- IDEMPOTENT: org INSERTs use ON CONFLICT (id) DO NOTHING; membership INSERTs use
-- ON CONFLICT (organization_id, developer_id) DO NOTHING; project assignment only
-- touches rows WHERE organization_id IS NULL. Re-running is a no-op.
--
-- ROLLBACK (manual, documented — run as a one-off, NOT auto-applied):
--   UPDATE projects SET organization_id = NULL
--     WHERE organization_id IN ('embed-build','automatio-solutions','va360labs','nanis-org');
--   DELETE FROM organization_members
--     WHERE organization_id IN ('embed-build','automatio-solutions','va360labs','nanis-org');
--   DELETE FROM organizations
--     WHERE id IN ('embed-build','automatio-solutions','va360labs','nanis-org');
--   -- (projects are never deleted by the rollback)
--
-- NOTE: the cleanup of the junk project `potencial-digital-2026` (operator
-- decision) is NOT part of this migration — it is a one-off data deletion run
-- separately, because a schema migration must stay pure over the org map.
--
-- Mirrored byte-for-byte in supabase/migrations/20260611000018_organizations_backfill.sql.
--
-- ── ENMENDADA 2026-08-24 — aplicable sobre una base LIMPIA ───────────
-- Tal y como se escribió, este backfill INSERTABA los cuatro developers de
-- producción por su id. En cualquier Postgres donde esos developers no existan
-- —una BD de dev recién creada, un clon del engine open-source, la CI— el paso
-- 1 violaba `organizations_created_by_fkey` y ABORTABA EL LEDGER ENTERO. Efecto
-- real medido: 11 de 16 tests de `test_native_provision.py` fallaban en `main`
-- sobre un contenedor nuevo, y con ellos TODA la suite native del engine, que
-- llama a `apply_migrations` en su fixture. El engine no se podía testear desde
-- cero.
--
-- Es el mismo error de capa que la 0020 ya corrigió por escrito para la 0019:
-- «organization» es un concepto del panel / manager, NO del engine genérico.
-- Aquí, además, el ledger llevaba dentro datos de clientes reales.
--
-- POR QUÉ SE ENMIENDA EN SITIO Y NO SE AÑADE UNA 0022:
-- la 0020 revirtió a la 0019 con una migración nueva, que es el patrón correcto
-- cuando el problema es semántico. Aquí no lo es: la 0018 **aborta**, así que
-- ninguna migración posterior llega a ejecutarse. No hay forma de arreglarla
-- desde delante.
--
-- POR QUÉ ES SEGURO: el cambio es estrictamente MÁS PERMISIVO. Se filtra cada
-- fila contra `developers`, de modo que solo se inserta lo que la FK ya
-- aceptaba. En producción los cuatro existen → comportamiento idéntico, y el
-- ledger ya la tiene aplicada. En una base limpia → no-op silencioso en vez de
-- excepción. Sigue siendo idempotente.

-- ── 1) Organizations ─────────────────────────────────────────────────
-- El JOIN contra `developers` es el guard: una org cuyo creador no existe en
-- esta base simplemente no se siembra.
INSERT INTO organizations (id, name, slug, created_by)
SELECT v.id, v.name, v.slug, v.created_by
  FROM (VALUES
      ('embed-build',         'Embed.Build',         'embed-build',         'jesusperezdeveloper'),
      ('automatio-solutions', 'Automatio Solutions', 'automatio-solutions', 'holadanimestre-arch'),
      ('va360labs',           'VA360Labs',           'va360labs',           'valen18'),
      ('nanis-org',           'Nani''s Org',         'nanis-org',           'nani0004')
  ) AS v(id, name, slug, created_by)
  JOIN developers d ON d.developer_id = v.created_by
ON CONFLICT (id) DO NOTHING;

-- ── 2) Organization memberships ──────────────────────────────────────
-- The creator of each org is org_admin. Automatio Solutions has a second
-- member (borjina-gif) as a plain member.
-- Doble guard: la org tiene que haberse creado arriba Y el developer existir.
INSERT INTO organization_members (organization_id, developer_id, role)
SELECT v.organization_id, v.developer_id, v.role
  FROM (VALUES
      ('embed-build',         'jesusperezdeveloper', 'org_admin'),
      ('automatio-solutions', 'holadanimestre-arch', 'org_admin'),
      ('automatio-solutions', 'borjina-gif',         'member'),
      ('va360labs',           'valen18',             'org_admin'),
      ('nanis-org',           'nani0004',            'org_admin')
  ) AS v(organization_id, developer_id, role)
  JOIN developers   d ON d.developer_id   = v.developer_id
  JOIN organizations o ON o.id            = v.organization_id
ON CONFLICT (organization_id, developer_id) DO NOTHING;

-- ── 3) Assign each project to its organization (only NULLs) ──────────
-- Embed.Build projects (jesusperezdeveloper's).
UPDATE projects SET organization_id = 'embed-build'
 WHERE organization_id IS NULL
   AND project_id IN (
       'ddboss-web-saas',
       'EmbedBuild/specbox-manager',
       'hq-embed-build',
       'moto.fan',
       'jesusperezdeveloper/potencial_digital_2026'
   );

-- Automatio Solutions projects (Dani + Borja's).
UPDATE projects SET organization_id = 'automatio-solutions'
 WHERE organization_id IS NULL
   AND project_id IN ('lorido-seguros', 'obraos');
