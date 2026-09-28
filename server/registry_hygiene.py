"""Registry hygiene — purge the shared state registry of sensitive fields (UC-3802 AC-04).

The hosted MCP keeps one registry for every project that ever reported to it
(``$STATE_PATH/registry.json``, the backend-switch registry
``$STATE_PATH/projects.json`` and one ``projects/<name>/meta.json`` per
project). Until UC-3802 those files carried free-text ``description`` fields
and local paths of the developers' machines. The tools no longer write them;
this module removes what is already there.

Operator flow (see ``doc/runbooks/registry-hygiene.md``)::

    python -m server.registry_hygiene --state-path /data/state --dry-run
    python -m server.registry_hygiene --state-path /data/state \\
        --backup-to /data/state/backup/registry-2026-09-28.enc

The backup is written **before** anything is purged and is encrypted with a
passphrase taken from ``SPECBOX_REGISTRY_BACKUP_PASSPHRASE`` (never a CLI
argument, so it never lands in a shell history). Move it off the server
(``scp``) and delete the local copy: the plaintext original must not survive
on the host. ``--decrypt FILE`` restores the bundle locally for the audit.

``--claim DEVELOPER_ID [NAME ...|--all]`` attributes legacy entries (which
predate ``registered_by``) to a developer so they become visible to that
developer's identity again. Unclaimed entries stay invisible to everyone.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .coordination.scope import REGISTERED_BY_FIELD, SENSITIVE_REGISTRY_FIELDS

PASSPHRASE_ENV = "SPECBOX_REGISTRY_BACKUP_PASSPHRASE"

#: Files the purge covers, relative to the state path.
REGISTRY_FILES: tuple[str, ...] = ("registry.json", "projects.json")

#: A string value that describes somebody's machine rather than the project.
#: Windows drive letters and UNC paths, plus the usual absolute roots on
#: macOS/Linux. URLs never match (they start with a scheme).
_LOCAL_PATH_RE = re.compile(
    r"^(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|root|data|app|opt|var|tmp|mnt|srv|private|Volumes)(?:/|$))"
)

_PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16
_MAGIC = b"SBXREG1\n"


# ── Pure scrubbing ──────────────────────────────────────────────────


def looks_like_local_path(value: Any) -> bool:
    """True for strings that point into a developer's filesystem."""
    return isinstance(value, str) and bool(_LOCAL_PATH_RE.match(value.strip()))


def scrub_entry(entry: Any) -> tuple[Any, dict[str, int]]:
    """Return a copy of ``entry`` without sensitive fields or local paths.

    Removes every key in :data:`SENSITIVE_REGISTRY_FIELDS` and blanks any
    remaining string value that looks like a local path (nested dicts and
    lists included). The report counts ``removed_fields`` and
    ``blanked_paths``.
    """
    report = {"removed_fields": 0, "blanked_paths": 0}

    def _walk(node: Any, key: str | None = None) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                if k in SENSITIVE_REGISTRY_FIELDS:
                    report["removed_fields"] += 1
                    continue
                out[k] = _walk(v, k)
            return out
        if isinstance(node, list):
            return [_walk(v, key) for v in node]
        if looks_like_local_path(node):
            report["blanked_paths"] += 1
            return ""
        return node

    return _walk(entry), report


def scrub_registry(registry: Any) -> tuple[Any, dict[str, Any]]:
    """Scrub every project entry of a registry document (dict or legacy list form)."""
    totals: dict[str, Any] = {"projects": 0, "removed_fields": 0, "blanked_paths": 0}
    if not isinstance(registry, dict):
        return registry, totals
    projects = registry.get("projects")
    cleaned = dict(registry)
    if isinstance(projects, dict):
        new_projects: dict[str, Any] = {}
        for name, entry in projects.items():
            scrubbed, rep = scrub_entry(entry)
            new_projects[name] = scrubbed
            totals["projects"] += 1
            totals["removed_fields"] += rep["removed_fields"]
            totals["blanked_paths"] += rep["blanked_paths"]
        cleaned["projects"] = new_projects
    elif isinstance(projects, list):
        new_list: list[Any] = []
        for entry in projects:
            scrubbed, rep = scrub_entry(entry)
            new_list.append(scrubbed)
            totals["projects"] += 1
            totals["removed_fields"] += rep["removed_fields"]
            totals["blanked_paths"] += rep["blanked_paths"]
        cleaned["projects"] = new_list
    return cleaned, totals


def claim_entries(
    registry: Any,
    developer_id: str,
    names: Iterable[str] | None = None,
) -> list[str]:
    """Stamp ``registered_by`` on entries that have no owner yet.

    ``names`` limits the claim; ``None`` claims every unowned entry. Entries
    already attributed (to anyone) are left untouched. Returns the claimed names.
    """
    if not isinstance(registry, dict) or not isinstance(registry.get("projects"), dict):
        return []
    wanted = None if names is None else set(names)
    claimed: list[str] = []
    for name, entry in registry["projects"].items():
        if wanted is not None and name not in wanted:
            continue
        if not isinstance(entry, dict) or entry.get(REGISTERED_BY_FIELD):
            continue
        entry[REGISTERED_BY_FIELD] = developer_id
        claimed.append(name)
    return sorted(claimed)


# ── Encrypted backup ────────────────────────────────────────────────


def _fernet(passphrase: str, salt: bytes):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_PBKDF2_ITERATIONS)
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
    return Fernet(key)


def encrypt_bytes(data: bytes, passphrase: str) -> bytes:
    """Encrypt ``data`` with a passphrase-derived key (PBKDF2-SHA256 → Fernet)."""
    if not passphrase or len(passphrase) < 12:
        raise ValueError("The backup passphrase must be at least 12 characters long.")
    salt = secrets.token_bytes(_SALT_BYTES)
    return _MAGIC + salt + _fernet(passphrase, salt).encrypt(data)


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    """Inverse of :func:`encrypt_bytes`. Raises ``ValueError`` on a wrong passphrase or file."""
    from cryptography.fernet import InvalidToken

    if not blob.startswith(_MAGIC):
        raise ValueError("Not a SpecBox registry backup.")
    body = blob[len(_MAGIC):]
    salt, token = body[:_SALT_BYTES], body[_SALT_BYTES:]
    try:
        return _fernet(passphrase, salt).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Wrong passphrase or corrupted backup.") from exc


# ── Filesystem run ──────────────────────────────────────────────────


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _meta_files(state_path: Path) -> list[Path]:
    projects_dir = state_path / "projects"
    if not projects_dir.is_dir():
        return []
    return sorted(p for p in projects_dir.glob("*/meta.json") if p.is_file())


def collect_bundle(state_path: Path) -> dict[str, Any]:
    """Every file the purge touches, as it is now — the content of the backup."""
    bundle: dict[str, Any] = {
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "state_path": str(state_path),
        "files": {},
    }
    for name in REGISTRY_FILES:
        doc = _load_json(state_path / name)
        if doc is not None:
            bundle["files"][name] = doc
    for meta in _meta_files(state_path):
        doc = _load_json(meta)
        if doc is not None:
            bundle["files"][str(meta.relative_to(state_path))] = doc
    return bundle


def run(
    state_path: Path,
    *,
    dry_run: bool = True,
    backup_to: Path | None = None,
    passphrase: str | None = None,
    claim_developer: str | None = None,
    claim_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Purge the registries and meta files under ``state_path``.

    With ``dry_run`` nothing is written; the report says what would change.
    Otherwise a backup is mandatory: ``backup_to`` + ``passphrase`` produce the
    encrypted bundle first, and the purge only proceeds once it is on disk.
    """
    report: dict[str, Any] = {
        "state_path": str(state_path),
        "dry_run": dry_run,
        "backup": None,
        "files": {},
        "claimed": [],
    }
    bundle = collect_bundle(state_path)
    if not bundle["files"]:
        report["note"] = "nothing to purge: no registry or meta files found"
        return report

    if not dry_run:
        if backup_to is None or not passphrase:
            raise ValueError("A purge requires --backup-to and the passphrase env var; use --dry-run to preview.")
        backup_to.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")
        backup_to.write_bytes(encrypt_bytes(payload, passphrase))
        report["backup"] = {"path": str(backup_to), "bytes": backup_to.stat().st_size, "files": len(bundle["files"])}

    for rel, doc in bundle["files"].items():
        is_registry = rel in REGISTRY_FILES
        cleaned, totals = scrub_registry(doc) if is_registry else scrub_entry(doc)
        claimed: list[str] = []
        if is_registry and claim_developer:
            claimed = claim_entries(cleaned, claim_developer, claim_names)
            report["claimed"].extend(f"{rel}:{n}" for n in claimed)
        file_report = dict(totals) if is_registry else {"removed_fields": totals["removed_fields"], "blanked_paths": totals["blanked_paths"]}
        file_report["claimed"] = len(claimed)
        changed = cleaned != doc
        file_report["changed"] = changed
        report["files"][rel] = file_report
        if changed and not dry_run:
            (state_path / rel).write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


# ── CLI ─────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m server.registry_hygiene",
        description="Purge the shared SpecBox state registry of descriptions and local paths (UC-3802 AC-04).",
    )
    p.add_argument("--state-path", default=os.getenv("STATE_PATH", "/data/state"), help="State directory (default: $STATE_PATH or /data/state)")
    p.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing")
    p.add_argument("--backup-to", type=Path, help="Encrypted backup file written before the purge (required unless --dry-run)")
    p.add_argument("--claim", metavar="DEVELOPER_ID", help="Attribute unowned entries to this developer")
    p.add_argument("--all", action="store_true", help="With --claim: claim every unowned entry")
    p.add_argument("names", nargs="*", help="With --claim: only these project names")
    p.add_argument("--decrypt", type=Path, metavar="FILE", help="Print the decrypted backup bundle and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    passphrase = os.getenv(PASSPHRASE_ENV)

    if args.decrypt is not None:
        if not passphrase:
            print(f"error: set {PASSPHRASE_ENV} to decrypt", file=sys.stderr)
            return 2
        try:
            sys.stdout.write(decrypt_bytes(args.decrypt.read_bytes(), passphrase).decode("utf-8"))
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.claim and not args.all and not args.names:
        print("error: --claim needs --all or a list of project names", file=sys.stderr)
        return 2
    if not args.dry_run and (args.backup_to is None or not passphrase):
        print(f"error: a purge needs --backup-to and {PASSPHRASE_ENV}; use --dry-run to preview", file=sys.stderr)
        return 2

    try:
        report = run(
            Path(args.state_path),
            dry_run=args.dry_run,
            backup_to=args.backup_to,
            passphrase=passphrase,
            claim_developer=args.claim,
            claim_names=None if args.all else (args.names or None),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report.get("backup"):
        print(
            f"\nBackup written to {report['backup']['path']}. Move it OFF this server now "
            "(scp) and delete the local copy — the plaintext must not survive here.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
