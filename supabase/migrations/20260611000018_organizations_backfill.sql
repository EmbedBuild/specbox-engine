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

-- ── 1) Organizations ─────────────────────────────────────────────────
INSERT INTO organizations (id, name, slug, created_by) VALUES
    ('embed-build',         'Embed.Build',         'embed-build',         'jesusperezdeveloper'),
    ('automatio-solutions', 'Automatio Solutions', 'automatio-solutions', 'holadanimestre-arch'),
    ('va360labs',           'VA360Labs',           'va360labs',           'valen18'),
    ('nanis-org',           'Nani''s Org',         'nanis-org',           'nani0004')
ON CONFLICT (id) DO NOTHING;

-- ── 2) Organization memberships ──────────────────────────────────────
-- The creator of each org is org_admin. Automatio Solutions has a second
-- member (borjina-gif) as a plain member.
INSERT INTO organization_members (organization_id, developer_id, role) VALUES
    ('embed-build',         'jesusperezdeveloper', 'org_admin'),
    ('automatio-solutions', 'holadanimestre-arch', 'org_admin'),
    ('automatio-solutions', 'borjina-gif',         'member'),
    ('va360labs',           'valen18',             'org_admin'),
    ('nanis-org',           'nani0004',            'org_admin')
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
