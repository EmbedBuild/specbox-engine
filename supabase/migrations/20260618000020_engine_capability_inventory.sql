-- UC-2002 (US-20): inventario de capacidades del engine publicado al site.
-- Cuatro tablas públicas (lectura anon, escritura solo service-role que bypassa RLS),
-- alimentadas por server/site_publish (build_inventory_publish_requests) en cada /release.
-- Replican el patrón de public.engine_feature (US-15): PK simple, RLS read-only anon.
-- Idempotente: IF NOT EXISTS + DROP POLICY IF EXISTS para re-aplicar sin error.

-- ---------------------------------------------------------------------------
-- engine_agent — catálogo de agentes (agents/*.md)
-- ---------------------------------------------------------------------------
create table if not exists public.engine_agent (
    agent_key text primary key,
    name      text not null default '',
    role      text not null default ''
);
comment on table public.engine_agent is
    'UC-2002 (US-20): catálogo de agentes del engine (de agents/*.md). Lectura pública anon.';

alter table public.engine_agent enable row level security;
drop policy if exists engine_agent_read on public.engine_agent;
create policy engine_agent_read on public.engine_agent
    for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- engine_tool — catálogo de MCP tools (decoradores @*.tool en server/)
-- ---------------------------------------------------------------------------
create table if not exists public.engine_tool (
    tool_name text primary key,
    module    text not null default ''
);
comment on table public.engine_tool is
    'UC-2002 (US-20): catálogo de MCP tools del engine (decoradores @*.tool en server/). Lectura pública anon.';

alter table public.engine_tool enable row level security;
drop policy if exists engine_tool_read on public.engine_tool;
create policy engine_tool_read on public.engine_tool
    for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- engine_skill — catálogo de skills/comandos (.claude/skills/*/SKILL.md)
-- ---------------------------------------------------------------------------
create table if not exists public.engine_skill (
    skill_key   text primary key,
    command     text not null default '',
    description text not null default ''
);
comment on table public.engine_skill is
    'UC-2002 (US-20): catálogo de skills/comandos del engine (de .claude/skills/*/SKILL.md). Lectura pública anon.';

alter table public.engine_skill enable row level security;
drop policy if exists engine_skill_read on public.engine_skill;
create policy engine_skill_read on public.engine_skill
    for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- engine_vscode_ext — extensión VSCode (vscode-extension/package.json). 1 fila.
-- ---------------------------------------------------------------------------
create table if not exists public.engine_vscode_ext (
    marketplace_id text primary key,
    name           text not null default '',
    publisher      text not null default '',
    version        text not null default ''
);
comment on table public.engine_vscode_ext is
    'UC-2002 (US-20): extensión VSCode del engine (de vscode-extension/package.json). Lectura pública anon.';

alter table public.engine_vscode_ext enable row level security;
drop policy if exists engine_vscode_ext_read on public.engine_vscode_ext;
create policy engine_vscode_ext_read on public.engine_vscode_ext
    for select to anon, authenticated using (true);
