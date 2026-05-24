# UC-601 — Acceptance Evidence

**US:** US-CLAIM-RENAME — Rename `claim` → `reservation` in Native Backend + Control Panel
**UC:** UC-601 — SQL migration `uc_claims` → `uc_reservations` in `specbox-engine`
**Branch:** `feature/uc-601-rename-claims-to-reservations`
**Date:** 2026-05-24

---

## Files

| Path | Role |
|------|------|
| `server/db/migrations/0007_rename_claims_to_reservations.sql` | Canonical migration (local dev/tests runner) |
| `supabase/migrations/20260524000007_rename_claims_to_reservations.sql` | Supabase ledger mirror (production) |

Both files contain the same DDL inside a `DO $$ ... $$` block with four
guarded renames (table, column, index, RLS policy), each idempotent via
`to_regclass` / `information_schema.columns` / `pg_policies` lookups.

---

## Verification environment

- Postgres 16-alpine via `docker compose -f docker-compose.dev.yml up -d`
  (host: `specbox-native-pg-dev`, port `55432`, db `specbox_native`).
- Apply chain: `0001_native_schema` → `0002_developers` → `0003_claims` →
  `0004_github_identities` → `0005_mcp_tokens` → `0006_audit_log` →
  `0007_rename_claims_to_reservations`.

---

## AC-01 — migration exists, idempotent, renames everything, preserves rows

### Scenario A: row inserted before rename, recovered with new names

```sql
-- Pre-migration (after 0001..0006 applied)
INSERT INTO projects (project_id, name) VALUES ('test-proj-uc601', 'UC-601 fixture');
INSERT INTO developers (developer_id, display_name) VALUES ('test-dev-uc601', 'Test Dev');
INSERT INTO uc_claims (project_id, uc_id, developer_id, branch)
  VALUES ('test-proj-uc601', 'UC-999', 'test-dev-uc601', 'feature/test');

SELECT project_id, uc_id, developer_id, branch, claimed_at
  FROM uc_claims WHERE project_id='test-proj-uc601';
--    project_id    | uc_id  |  developer_id  |    branch    |          claimed_at
-- -----------------+--------+----------------+--------------+-------------------------------
--  test-proj-uc601 | UC-999 | test-dev-uc601 | feature/test | 2026-05-24 12:28:23.485024+00

-- Apply 0007
-- (psql -f server/db/migrations/0007_rename_claims_to_reservations.sql → DO)

SELECT project_id, uc_id, developer_id, branch, reserved_at
  FROM uc_reservations WHERE project_id='test-proj-uc601';
--    project_id    | uc_id  |  developer_id  |    branch    |          reserved_at
-- -----------------+--------+----------------+--------------+-------------------------------
--  test-proj-uc601 | UC-999 | test-dev-uc601 | feature/test | 2026-05-24 12:28:23.485024+00
```

Identical row, identical timestamp, recovered via the new column name. **PASS.**

### Scenario B: idempotency (re-apply 2× and 3×)

```
$ psql ... -f server/db/migrations/0007_rename_claims_to_reservations.sql   # exit 0, DO
$ psql ... -f server/db/migrations/0007_rename_claims_to_reservations.sql   # exit 0, DO (no-op)
$ psql ... -f server/db/migrations/0007_rename_claims_to_reservations.sql   # exit 0, DO (no-op)
```

Zero errors, zero warnings on repeated application. **PASS.**

---

## AC-02 — final schema shape

`\d uc_reservations` on the post-migration database:

```
                        Table "public.uc_reservations"
    Column    |           Type           | Collation | Nullable |   Default
--------------+--------------------------+-----------+----------+-------------
 project_id   | text                     |           | not null |
 uc_id        | text                     |           | not null |
 developer_id | text                     |           | not null |
 branch       | text                     |           | not null | ''::text
 reserved_at  | timestamp with time zone |           | not null | now()
 meta         | jsonb                    |           | not null | '{}'::jsonb
Indexes:
    "uc_claims_pkey" PRIMARY KEY, btree (project_id, uc_id)
    "idx_uc_reservations_developer_id" btree (developer_id)
Foreign-key constraints:
    "uc_claims_developer_id_fkey" FOREIGN KEY (developer_id) REFERENCES developers(developer_id) ON DELETE CASCADE
    "uc_claims_project_id_fkey"   FOREIGN KEY (project_id)   REFERENCES projects(project_id)   ON DELETE CASCADE
```

- PK `(project_id, uc_id)` ✅
- FKs ON DELETE CASCADE to `projects(project_id)` and `developers(developer_id)` ✅
- Column `reserved_at TIMESTAMPTZ NOT NULL DEFAULT now()` ✅

```sql
SELECT to_regclass('public.uc_claims');   -- NULL ✅
```

**Note on constraint names:** Postgres does NOT rename PK/FK constraint names
when a table is renamed. The constraints are still called `uc_claims_pkey`,
`uc_claims_*_fkey` — purely cosmetic, functionality unaffected. AC-02 does
not require renaming constraints, so they are left as-is. A future cleanup
(out of scope for UC-601) could rename them via `ALTER TABLE ... RENAME
CONSTRAINT`.

**PASS.**

---

## AC-03 — applies cleanly to fresh DB and DB with pre-migration data

### Fresh DB (no prior rows)

```
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
-- Apply 0001..0007 in order:
-- 0001_native_schema ............. CREATE INDEX, CREATE INDEX
-- 0002_developers ................ CREATE TABLE, CREATE INDEX
-- 0003_claims .................... CREATE TABLE, CREATE INDEX
-- 0004_github_identities ......... CREATE TABLE, CREATE INDEX
-- 0005_mcp_tokens ................ DROP INDEX, ALTER TABLE
-- 0006_audit_log ................. CREATE TABLE, CREATE INDEX
-- 0007_rename_claims_to_reservations . DO
```

Zero warnings, zero errors. Final state:
- `to_regclass('public.uc_claims')` = `NULL`
- `to_regclass('public.uc_reservations')` = `uc_reservations`
- `idx_uc_reservations_developer_id` exists
- `reserved_at` column exists, `claimed_at` column does not

### DB with pre-migration data

Covered in AC-01 Scenario A above — the same migration applied to a
populated `uc_claims` produced no warnings and preserved all rows.

**PASS.**

---

## RLS policy rename (Supabase mirror)

The Supabase migration `20260522000004_rls_policies.sql` creates a policy
`specbox_deny_anon_uc_claims ON uc_claims`. After `ALTER TABLE RENAME`,
RLS policies follow the table by OID, but their literal name stays
`specbox_deny_anon_uc_claims`. The migration renames the policy to
`specbox_deny_anon_uc_reservations` so the project's naming convention
`specbox_deny_anon_<table>` continues to hold.

The local-dev runner does not apply the RLS migration (it lives only
under `supabase/migrations/`), so on Postgres dev the `pg_policies` guard
finds nothing and the rename is silently skipped. On Supabase production
the guard finds the policy and renames it. Both paths are safe.

---

## Verdict

All three acceptance criteria **PASS** on Postgres 16-alpine local dev.
The Supabase ledger mirror is byte-for-byte equivalent in DDL (only the
header comment differs). UC-601 ready for review.
