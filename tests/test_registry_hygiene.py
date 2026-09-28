"""UC-3802 AC-04 — purga del registro compartido con copia cifrada.

La descripción libre y las rutas locales dejan de guardarse (ver
``test_registry_scope.py``); este archivo cubre la depuración del registro
YA existente en el servidor: ``python -m server.registry_hygiene``.

- Elimina ``description`` y cualquier campo/valor que describa la máquina
  del developer, en ``registry.json``, ``projects.json`` y cada ``meta.json``.
- Escribe ANTES una copia cifrada (PBKDF2-SHA256 → Fernet) con passphrase
  tomada del entorno, nunca de la línea de comandos.
- ``--dry-run`` no toca nada; sin copia no hay purga.
- ``--claim`` atribuye entradas legacy sin dueño a un developer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server import registry_hygiene as rh
from server.coordination.scope import REGISTERED_BY_FIELD

REGISTRY = {
    "projects": {
        "acme-api": {
            "stack": "python",
            "repo_url": "https://github.com/acme/api",
            "description": "Cliente ACME — contrato 40k€, NDA firmada",
            "registered_at": "2026-01-01T00:00:00+00:00",
            "backend_history": [{"backend": "freeform", "board_id": "/Users/alice/dev/api/doc/tracking"}],
        },
        "win-proj": {
            "stack": "flutter",
            "path": "C:\\Users\\bob\\dev\\proj",
            "freeform_root_absolute": "D:/work/proj/doc/tracking",
            "notes": {"local": "/home/bob/proj"},
            "registered_by": "bob",
        },
        "clean": {"stack": "go", "repo_url": "https://github.com/x/clean"},
    }
}


def _seed(state_path: Path) -> None:
    state_path.mkdir(parents=True, exist_ok=True)
    (state_path / "registry.json").write_text(json.dumps(REGISTRY), encoding="utf-8")
    (state_path / "projects.json").write_text(
        json.dumps({"projects": {"acme-api": {"spec_backend": "freeform", "board_id": "/Users/alice/dev/api/doc/tracking"}}}),
        encoding="utf-8",
    )
    meta_dir = state_path / "projects" / "acme-api"
    meta_dir.mkdir(parents=True)
    (meta_dir / "meta.json").write_text(
        json.dumps({"stack": "python", "description": "secreto", "onboarded_by": "Alice", "repo_url": "https://github.com/acme/api"}),
        encoding="utf-8",
    )


def test_looks_like_local_path():
    for v in ("/Users/a/b", "/home/x", "C:\\Users\\y", "D:/work", "\\\\server\\share", "/data/state", "/app/doc"):
        assert rh.looks_like_local_path(v), v
    for v in ("https://github.com/a/b", "acme/api", "ff-1", "", 3, None, "/2026-release"):
        assert not rh.looks_like_local_path(v), v


def test_scrub_entry_removes_fields_and_blanks_nested_paths():
    cleaned, report = rh.scrub_entry(REGISTRY["projects"]["win-proj"])
    assert cleaned == {"stack": "flutter", "notes": {"local": ""}, "registered_by": "bob"}
    assert report == {"removed_fields": 2, "blanked_paths": 1}


def test_scrub_registry_counts_and_keeps_public_fields():
    cleaned, totals = rh.scrub_registry(REGISTRY)
    assert totals == {"projects": 3, "removed_fields": 3, "blanked_paths": 2}
    acme = cleaned["projects"]["acme-api"]
    assert "description" not in acme and acme["repo_url"] == "https://github.com/acme/api"
    assert acme["backend_history"][0]["board_id"] == ""
    assert cleaned["projects"]["clean"] == REGISTRY["projects"]["clean"]
    # Legacy list-form registries are handled too.
    legacy, t2 = rh.scrub_registry({"projects": [{"name": "a", "path": "/Users/a", "developer": "Alice"}]})
    assert legacy["projects"] == [{"name": "a"}] and t2["removed_fields"] == 2


def test_claim_entries_only_unowned_and_optionally_by_name():
    reg = json.loads(json.dumps(REGISTRY))
    assert rh.claim_entries(reg, "alice", ["acme-api", "win-proj"]) == ["acme-api"]
    assert reg["projects"]["acme-api"][REGISTERED_BY_FIELD] == "alice"
    assert reg["projects"]["win-proj"][REGISTERED_BY_FIELD] == "bob"  # never re-attributed
    assert rh.claim_entries(reg, "alice") == ["clean"]  # None → every unowned entry


def test_encrypt_decrypt_roundtrip_and_wrong_passphrase():
    blob = rh.encrypt_bytes(b'{"x": 1}', "correct horse battery")
    assert blob.startswith(rh._MAGIC) and b'{"x"' not in blob
    assert rh.decrypt_bytes(blob, "correct horse battery") == b'{"x": 1}'
    with pytest.raises(ValueError):
        rh.decrypt_bytes(blob, "wrong passphrase!!")
    with pytest.raises(ValueError):
        rh.decrypt_bytes(b"not a backup", "correct horse battery")
    with pytest.raises(ValueError):
        rh.encrypt_bytes(b"x", "short")


def test_dry_run_reports_and_writes_nothing(tmp_path):
    _seed(tmp_path)
    before = {p: p.read_text() for p in tmp_path.rglob("*.json")}
    report = rh.run(tmp_path, dry_run=True)
    assert report["dry_run"] is True and report["backup"] is None
    assert report["files"]["registry.json"]["removed_fields"] == 3
    assert report["files"]["projects.json"]["blanked_paths"] == 1
    assert report["files"]["projects/acme-api/meta.json"]["removed_fields"] == 1
    assert {p: p.read_text() for p in tmp_path.rglob("*.json")} == before


def test_purge_requires_backup(tmp_path):
    _seed(tmp_path)
    with pytest.raises(ValueError):
        rh.run(tmp_path, dry_run=False)
    assert "secreto" in (tmp_path / "projects" / "acme-api" / "meta.json").read_text()


def test_purge_writes_encrypted_backup_first_then_scrubs_and_claims(tmp_path):
    _seed(tmp_path)
    backup = tmp_path / "out" / "registry.enc"
    report = rh.run(
        tmp_path, dry_run=False, backup_to=backup, passphrase="correct horse battery",
        claim_developer="alice", claim_names=None,
    )
    assert report["backup"]["files"] == 3 and backup.exists()
    # The backup holds the ORIGINAL (still with the secrets), encrypted.
    raw = backup.read_bytes()
    assert b"contrato" not in raw and b"secreto" not in raw
    bundle = json.loads(rh.decrypt_bytes(raw, "correct horse battery"))
    assert bundle["files"]["registry.json"]["projects"]["acme-api"]["description"].startswith("Cliente ACME")
    assert bundle["files"]["projects/acme-api/meta.json"]["description"] == "secreto"
    # On disk nothing sensitive survives.
    for p in tmp_path.rglob("*.json"):
        text = p.read_text()
        assert "contrato" not in text and "secreto" not in text and "C:\\\\Users" not in text
        assert "/Users/alice" not in text and "/home/bob" not in text
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["projects"]["acme-api"][REGISTERED_BY_FIELD] == "alice"
    assert registry["projects"]["clean"][REGISTERED_BY_FIELD] == "alice"
    assert registry["projects"]["win-proj"][REGISTERED_BY_FIELD] == "bob"
    # Both shared registries are claimed (the switch registry holds acme-api too).
    assert sorted(report["claimed"]) == [
        "projects.json:acme-api",
        "registry.json:acme-api",
        "registry.json:clean",
    ]
    meta = json.loads((tmp_path / "projects" / "acme-api" / "meta.json").read_text())
    assert meta == {"stack": "python", "onboarded_by": "Alice", "repo_url": "https://github.com/acme/api"}


def test_cli_dry_run_and_guards(tmp_path, monkeypatch, capsys):
    _seed(tmp_path)
    monkeypatch.delenv(rh.PASSPHRASE_ENV, raising=False)
    assert rh.main(["--state-path", str(tmp_path), "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True and out["files"]["registry.json"]["changed"] is True
    # A purge without backup/passphrase is refused before touching anything.
    assert rh.main(["--state-path", str(tmp_path)]) == 2
    assert rh.main(["--state-path", str(tmp_path), "--dry-run", "--claim", "alice"]) == 2
    assert "secreto" in (tmp_path / "projects" / "acme-api" / "meta.json").read_text()


def test_cli_purge_then_decrypt(tmp_path, monkeypatch, capsys):
    _seed(tmp_path)
    backup = tmp_path / "registry.enc"
    monkeypatch.setenv(rh.PASSPHRASE_ENV, "correct horse battery")
    assert rh.main(["--state-path", str(tmp_path), "--backup-to", str(backup), "--claim", "alice", "--all"]) == 0
    captured = capsys.readouterr()
    assert "Move it OFF this server" in captured.err
    assert rh.main(["--decrypt", str(backup)]) == 0
    bundle = json.loads(capsys.readouterr().out)
    assert set(bundle["files"]) == {"registry.json", "projects.json", "projects/acme-api/meta.json"}
    assert rh.main(["--state-path", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files"]["registry.json"]["changed"] is False


def test_purge_never_overwrites_an_existing_backup(tmp_path):
    """A second run with the same file name must not destroy the earlier copy —
    it may be the only one that still holds the original content."""
    _seed(tmp_path)
    backup = tmp_path / "out" / "registry.enc"
    backup.parent.mkdir()
    backup.write_bytes(b"previous copy")
    with pytest.raises(ValueError, match="never overwritten"):
        rh.run(tmp_path, dry_run=False, backup_to=backup, passphrase="correct horse battery")
    assert backup.read_bytes() == b"previous copy"
    assert "secreto" in (tmp_path / "projects" / "acme-api" / "meta.json").read_text()  # nothing purged


def test_unclaim_entries_only_named_and_only_that_owner():
    reg = json.loads(json.dumps(REGISTRY))
    rh.claim_entries(reg, "alice", ["acme-api", "clean"])
    # bob's entry is not alice's → untouched; unknown names ignored; no --all.
    assert rh.unclaim_entries(reg, "alice", ["acme-api", "win-proj", "ghost"]) == ["acme-api"]
    assert REGISTERED_BY_FIELD not in reg["projects"]["acme-api"]
    assert reg["projects"]["win-proj"][REGISTERED_BY_FIELD] == "bob"
    assert reg["projects"]["clean"][REGISTERED_BY_FIELD] == "alice"


def test_cli_unclaim_releases_a_project_after_an_overreaching_claim(tmp_path, monkeypatch, capsys):
    _seed(tmp_path)
    monkeypatch.setenv(rh.PASSPHRASE_ENV, "correct horse battery")
    assert rh.main(["--state-path", str(tmp_path), "--backup-to", str(tmp_path / "b1.enc"), "--claim", "alice", "--all"]) == 0
    capsys.readouterr()
    # Guards: names required, and never together with --claim.
    assert rh.main(["--state-path", str(tmp_path), "--dry-run", "--unclaim", "alice"]) == 2
    assert rh.main(["--state-path", str(tmp_path), "--dry-run", "--claim", "alice", "--unclaim", "alice", "x"]) == 2
    capsys.readouterr()
    assert rh.main(["--state-path", str(tmp_path), "--backup-to", str(tmp_path / "b2.enc"), "--unclaim", "alice", "clean"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["unclaimed"] == ["registry.json:clean"]
    assert "1 released" in out["summary"]
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert REGISTERED_BY_FIELD not in registry["projects"]["clean"]
    assert registry["projects"]["acme-api"][REGISTERED_BY_FIELD] == "alice"


def test_summary_says_when_nothing_sensitive_was_found(tmp_path):
    (tmp_path / "registry.json").write_text(json.dumps({"projects": {"clean": {"stack": "go"}}}), encoding="utf-8")
    report = rh.run(tmp_path, dry_run=True)
    assert report["summary"].startswith("0 sensitive field(s) removed, 0 local path(s) blanked")
    assert "No sensitive content found" in report["summary"]
