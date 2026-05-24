# UC-602 — Acceptance Evidence

**US:** US-CLAIM-RENAME — Rename `claim` → `reservation` in Native Backend + Control Panel
**UC:** UC-602 — Rename `server/coordination/claims.py` → `reservations.py` and all internal APIs
**Branch:** `feature/uc-602-rename-claims-module-to-reservations`
**Date:** 2026-05-24

---

## Files renamed / updated

| Path | Action |
|------|--------|
| `server/coordination/reservations.py` | **NEW** — full module with renamed identifiers |
| `server/coordination/claims.py` | **DELETED** (`git rm`) |
| `server/coordination/__init__.py` | Docstring updated, `reservations` module documented |
| `server/tools/coordination.py` | Imports + `claim_uc` → `reserve_uc`, codes, summaries |
| `server/tools/spec_driven.py` | `_start_uc_native` + `_native_uc_ids_reserved_by_others` renamed; compat constant `_NATIVE_RESERVATION_CACHE_KEY` introduced for Node hook |
| `server/migration/native_handling.py` | Import + `list_active_reservations`, output keys `reservations`/`reserved_at`, `DISCARD_NOTE` |
| `server/server.py` | Comment block updated for H3 tool rename |
| `server/auth_gateway.py` | Docstring updated |
| `server/app_docs/drift_detector.py` | Two English "claims" verbs rephrased to avoid grep noise |
| `server/db/migrations/0007_*` + `supabase/migrations/20260524000007_*` | Hardened: handle the re-apply case where the legacy runner re-runs 0003 (creates empty `uc_claims` alongside live `uc_reservations`) by dropping the empty legacy table |
| `tests/test_coordination_claims.py` | Imports + identifiers renamed (file rename + test function rename deferred to UC-605) |
| `tests/test_native_handling.py` | Import alias to new module + output key reads (`discarded["reservations"]`, `counts["reservations"]`) |

---

## AC-01 — module exists with renamed surface

```text
$ ls server/coordination/
__init__.py  branches.py  identity.py  reservations.py    # claims.py removed
```

Python import smoke-test:

```python
from server.coordination.reservations import (
    AlreadyReservedError,    # → "ALREADY_RESERVED"
    NotReservationOwnerError,  # → "NOT_RESERVATION_OWNER"
    UCReservation,           # dataclass(frozen=True)
    get_reservation,
    list_active_reservations,
    reserved_uc_ids_by_others,
    release_uc,
    reserve_uc,
    start_uc_atomic,
)
# all import cleanly; claims.py no longer importable
```

`server/coordination/__init__.py` docstring lists `:mod:\`reservations\`` and
notes it was "renamed from ``claims`` in v5.35.0 / US-CLAIM-RENAME". **PASS.**

---

## AC-02 — dataclass shape + error payload

Live verification:

```python
>>> UCReservation('p','UC-1','alice','b','2026').to_public()
{'uc_id': 'UC-1', 'developer_id': 'alice', 'reserved_at': '2026', 'branch': 'b'}
>>> AlreadyReservedError.code
'ALREADY_RESERVED'
>>> NotReservationOwnerError.code
'NOT_RESERVATION_OWNER'
```

`AlreadyReservedError.to_payload()` (tested in
`test_coordination_claims.py::test_claim_uc_already_claimed_carries_owner_info`):

```python
{'code': 'ALREADY_RESERVED', 'uc_id': 'UC-301', 'owner': 'bob',
 'reserved_at': '2026-05-21T20:00:00+00:00', 'branch': 'feature/uc-301-bob'}
```

The four required keys (`code`, `owner`, `reserved_at`, `branch`) are present
and the conflict-time `uc_id` is included as well. `to_conflict()` is kept as
a backwards-compatible alias for the rare external caller until UC-612. **PASS.**

---

## AC-03 — grep claim/Claim/claimed_at in server/*.py is bounded

```
$ grep -rn 'claim\|Claim\|claimed_at' server/ --include='*.py'
server/server.py:158:# renamed the H3 tool from claim_uc to reserve_uc; UC-604 reintroduces
server/server.py:159:# claim_uc as a deprecated alias for v5.35-v5.36.
server/tools/spec_driven.py:56:# (...lib/native-claim-revalidate.mjs)
server/tools/spec_driven.py:57:# the MCP REST endpoint /api/native/claim-status both consume...
server/tools/spec_driven.py:61:# then, the local cache file keeps the historical "claim" key as a compat
server/tools/spec_driven.py:63:_NATIVE_RESERVATION_CACHE_KEY = "claim"  # noqa: S105 — compat with Node hook
server/tools/spec_driven.py:91:# reserved_at is accepted as the new key; claimed_at is still
server/tools/spec_driven.py:95:    or reservation.get("claimed_at")
server/tools/coordination.py:23..248:  (docstrings about the rename)
server/coordination/__init__.py:12:- :mod:`reservations` — UC reservation exclusion (renamed from ``claims``
server/coordination/reservations.py:5,10:  (historical docstrings)
```

All 16 hits fall into AC-03's permitted exception cases:

- `server/tools/coordination.py` — explicitly excluded by AC-03 (where UC-604
  will add the deprecated alias).
- All other lines are docstrings/comments explaining the historical rename,
  or the single documented compatibility constant `_NATIVE_RESERVATION_CACHE_KEY = "claim"`
  + its `claimed_at` fallback read, both kept because the Node hook
  (`.claude/hooks/spec-guard.mjs`) and the MCP REST endpoint
  `/api/native/claim-status` are cross-language wire-protocol consumers whose
  rename is intentionally deferred to a later UC of this US to avoid breaking
  in-flight deployments mid-rollout.

**No active code path uses the legacy vocabulary.** **PASS.**

---

## Tests

```
$ docker compose -f docker-compose.dev.yml up -d
$ SPECBOX_NATIVE_DSN="postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native" \
    .venv/bin/pytest tests/test_native_*.py tests/test_coordination_*.py -q
........................................................................ [ 55%]
.........................................................                 [100%]
130 passed in 4.68s
```

The native + coordination suite stays 100% green against Postgres 16-alpine.
The wider repo also includes 14 pre-existing failures in
`test_spec_mutations.py` and `test_milestone_management.py` (`InMemoryBackend`
mock missing `archive_item`) — these predate UC-602 and are documented in the
H1 handoff as deferred pre-existing tech debt.

## Migration robustness regression caught + fixed

While running the full test suite mid-development, the PG-gated tests
exposed a re-apply bug in UC-601's migration: `apply_migrations()` replays
every `*.sql` in order, so on a re-apply 0003_claims.sql's
`CREATE TABLE IF NOT EXISTS uc_claims` would recreate an empty `uc_claims`
alongside the already-renamed `uc_reservations`, and 0007's `ALTER TABLE
RENAME TO uc_reservations` would then fail with "relation uc_reservations
already exists".

Fixed in this UC by extending 0007 (canonical + Supabase mirror) to detect
the "both tables exist" state: if the legacy `uc_claims` is empty (the
expected re-apply case where data lives in `uc_reservations`), drop it
silently; if it has rows, raise an explicit `RAISE EXCEPTION` rather than
risk silently destroying data. Verified by applying the full migration
chain three times in a row against a fresh DB: `uc_reservations` stays,
`uc_claims` stays NULL, zero errors.

## Verdict

All three acceptance criteria **PASS**. UC-602 ready for review.
