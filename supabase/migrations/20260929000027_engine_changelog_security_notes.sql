-- UC-4302 (US-43): la página de versiones del site muestra la sección Security cuando existe.
-- Versiona además las tres tablas del estado del engine (US-15/US-16), creadas en su día
-- desde el MCP sin fichero .sql, con CREATE TABLE IF NOT EXISTS (misma forma que producción).
-- Idempotente: IF NOT EXISTS + DROP POLICY IF EXISTS. Escritura solo con service-role
-- (bypassa RLS); lectura pública anon.
--
-- Solo vive en supabase/migrations (como 20260618000020): estas tablas son del site, no del
-- esquema native que aplica server/db/migrate.py en CI. Aplicada en producción el 2026-09-29
-- (engine_changelog_security_notes_uc4302).

create table if not exists public.engine_release (
    version         text primary key,
    codename        text not null default '',
    release_date    date,
    min_claude_code text not null default '',
    is_current      boolean not null default false,
    created_at      timestamptz not null default now()
);
comment on table public.engine_release is
    'US-16: releases del engine publicadas por server/site_publish en cada /release. Lectura pública anon.';

create table if not exists public.engine_feature (
    feature_key   text primary key,
    category      text not null default '',
    since_version text not null default '',
    status        text not null default 'active'
);
comment on table public.engine_feature is
    'US-15/US-16: catálogo de features del engine (ENGINE_VERSION.yaml). Lectura pública anon.';

create table if not exists public.engine_changelog_entry (
    version           text primary key references public.engine_release(version) on delete cascade,
    codename          text not null default '',
    release_date      date,
    public_highlights jsonb not null default '[]'::jsonb
);

-- UC-4302: avisos de seguridad de la versión (sección ### Security del CHANGELOG.md), en el
-- mismo formato que public_highlights. Vacío cuando la versión no tiene cambios de seguridad.
alter table public.engine_changelog_entry
    add column if not exists security_notes jsonb not null default '[]'::jsonb;
comment on column public.engine_changelog_entry.security_notes is
    'UC-4302 (US-43): qué evita esta versión (sección Security del changelog), sin severidades ni origen. Lista JSON de textos.';
comment on table public.engine_changelog_entry is
    'US-16/UC-4302: changelog curado por versión (highlights + avisos de seguridad). Lectura pública anon.';

alter table public.engine_release enable row level security;
alter table public.engine_feature enable row level security;
alter table public.engine_changelog_entry enable row level security;

drop policy if exists engine_release_read on public.engine_release;
create policy engine_release_read on public.engine_release
    for select to anon, authenticated using (true);
drop policy if exists engine_feature_read on public.engine_feature;
create policy engine_feature_read on public.engine_feature
    for select to anon, authenticated using (true);
drop policy if exists engine_changelog_read on public.engine_changelog_entry;
create policy engine_changelog_read on public.engine_changelog_entry
    for select to anon, authenticated using (true);
