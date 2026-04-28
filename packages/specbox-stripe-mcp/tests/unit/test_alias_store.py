"""Unit tests for the encrypted alias store (UC-017).

These tests use the passphrase KDF backend (SPECBOX_ALIAS_PASSPHRASE) so they
run in CI on Linux/macOS without depending on the macOS Keychain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specbox_stripe_mcp.lib.alias_store import (
    DEFAULT_RELATIVE_PATH,
    AliasStore,
    AliasStoreError,
    delete_alias,
    list_aliases,
    resolve_alias,
    store_alias,
)

TEST_KEY_TEST = "sk_" + "test_" + "AliasStoreFixtureNotRealNotFromStripe"
TEST_KEY_LIVE = "sk_" + "live_" + "AliasStoreFixtureNotRealNotFromStripe"


@pytest.fixture(autouse=True)
def _passphrase_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the passphrase KDF for every test in this module."""
    monkeypatch.setenv("SPECBOX_ALIAS_PASSPHRASE", "test-passphrase-1234567890")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A throwaway project root for each test."""
    return tmp_path


# ---------------------------------------------------------------------------
# AC-01..AC-03: store / list / delete contract
# ---------------------------------------------------------------------------


class TestStoreAndList:
    def test_store_creates_encrypted_file(self, project: Path) -> None:
        """AC-01: store_stripe_alias creates the encrypted JSON at the expected path."""
        store_alias(
            alias_name="prod",
            stripe_api_key=TEST_KEY_TEST,
            project_path=str(project),
        )
        store_path = project / DEFAULT_RELATIVE_PATH
        assert store_path.exists()
        blob = json.loads(store_path.read_text())
        assert blob["version"] == 1
        # Plaintext key MUST NOT appear in the file.
        raw = store_path.read_text()
        assert TEST_KEY_TEST not in raw
        assert "AliasStoreFixture" not in raw

    def test_store_returns_metadata_only(self, project: Path) -> None:
        result = store_alias(
            alias_name="prod",
            stripe_api_key=TEST_KEY_TEST,
            project_path=str(project),
        )
        assert result["alias_name"] == "prod"
        assert result["mode"] == "test"
        assert "store_path" in result
        # Plaintext NEVER returned.
        assert TEST_KEY_TEST not in json.dumps(result)

    def test_store_detects_live_mode(self, project: Path) -> None:
        result = store_alias(
            alias_name="prod_live",
            stripe_api_key=TEST_KEY_LIVE,
            project_path=str(project),
        )
        assert result["mode"] == "live"

    def test_store_rejects_invalid_key(self, project: Path) -> None:
        with pytest.raises(AliasStoreError) as exc_info:
            store_alias(
                alias_name="garbage",
                stripe_api_key="not-a-stripe-key",
                project_path=str(project),
            )
        assert exc_info.value.code == "E_INVALID_KEY"

    def test_list_returns_metadata_no_values(self, project: Path) -> None:
        """AC-02: list_stripe_aliases returns names+modes, never values."""
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_LIVE, project_path=str(project))
        store_alias(alias_name="staging", stripe_api_key=TEST_KEY_TEST, project_path=str(project))

        items = list_aliases(project_path=str(project))
        names = sorted(i["alias_name"] for i in items)
        assert names == ["prod", "staging"]
        # Values must not leak via list().
        for item in items:
            assert TEST_KEY_TEST not in json.dumps(item)
            assert TEST_KEY_LIVE not in json.dumps(item)
            assert "stripe_api_key" not in item

    def test_list_empty_when_store_missing(self, project: Path) -> None:
        items = list_aliases(project_path=str(project))
        assert items == []


class TestResolve:
    def test_resolve_returns_plaintext(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        resolved = resolve_alias(alias_name="prod", project_path=str(project))
        assert resolved == TEST_KEY_TEST

    def test_resolve_unknown_raises_alias_not_found(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        with pytest.raises(AliasStoreError) as exc_info:
            resolve_alias(alias_name="missing", project_path=str(project))
        assert exc_info.value.code == "E_ALIAS_NOT_FOUND"

    def test_resolve_marks_last_used_at(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        before_meta = list_aliases(project_path=str(project))[0]
        assert before_meta["last_used_at"] is None
        resolve_alias(alias_name="prod", project_path=str(project))
        after_meta = list_aliases(project_path=str(project))[0]
        assert after_meta["last_used_at"] is not None


class TestDelete:
    """AC-03: delete requires literal confirm_token."""

    def test_delete_requires_confirm_token(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        with pytest.raises(AliasStoreError) as exc_info:
            delete_alias(alias_name="prod", project_path=str(project), confirm_token="wrong")
        assert exc_info.value.code == "E_CONFIRMATION_REQUIRED"
        # Alias still present.
        assert len(list_aliases(project_path=str(project))) == 1

    def test_delete_with_correct_token(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        ok = delete_alias(
            alias_name="prod",
            project_path=str(project),
            confirm_token="I want to delete the prod alias",
        )
        assert ok is True
        assert list_aliases(project_path=str(project)) == []

    def test_delete_unknown_alias_returns_false(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        ok = delete_alias(
            alias_name="missing",
            project_path=str(project),
            confirm_token="I want to delete the missing alias",
        )
        assert ok is False

    def test_delete_last_alias_removes_file(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        delete_alias(
            alias_name="prod",
            project_path=str(project),
            confirm_token="I want to delete the prod alias",
        )
        store_path = project / DEFAULT_RELATIVE_PATH
        assert not store_path.exists()


# ---------------------------------------------------------------------------
# AC-06: gitignore enforcement
# ---------------------------------------------------------------------------


class TestGitignore:
    def test_first_store_writes_gitignore_entry(self, project: Path) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        gitignore = project / ".gitignore"
        assert gitignore.exists()
        assert ".claude/secrets/" in gitignore.read_text()

    def test_existing_gitignore_is_appended_to(self, project: Path) -> None:
        gitignore = project / ".gitignore"
        gitignore.write_text("node_modules/\n*.log\n")
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        text = gitignore.read_text()
        assert "node_modules/" in text
        assert "*.log" in text
        assert ".claude/secrets/" in text

    def test_gitignore_not_duplicated(self, project: Path) -> None:
        gitignore = project / ".gitignore"
        gitignore.write_text(".claude/secrets/\n")
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        # The line should appear exactly once.
        text = gitignore.read_text()
        assert text.count(".claude/secrets/") == 1


# ---------------------------------------------------------------------------
# AC-07: round-trip + cross-call persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_full_lifecycle(self, project: Path) -> None:
        # store
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_LIVE, project_path=str(project))
        # list
        items = list_aliases(project_path=str(project))
        assert len(items) == 1
        # use
        assert resolve_alias(alias_name="prod", project_path=str(project)) == TEST_KEY_LIVE
        # delete
        assert delete_alias(
            alias_name="prod",
            project_path=str(project),
            confirm_token="I want to delete the prod alias",
        )
        assert list_aliases(project_path=str(project)) == []

    def test_wrong_passphrase_fails_decryption(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store_alias(alias_name="prod", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        monkeypatch.setenv("SPECBOX_ALIAS_PASSPHRASE", "different-passphrase")
        with pytest.raises(AliasStoreError) as exc_info:
            resolve_alias(alias_name="prod", project_path=str(project))
        assert exc_info.value.code == "E_DECRYPT_FAILED"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_alias_name_empty_rejected(self, project: Path) -> None:
        with pytest.raises(AliasStoreError) as exc_info:
            store_alias(alias_name="", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        assert exc_info.value.code == "E_INVALID_ALIAS_NAME"

    def test_alias_name_with_invalid_chars_rejected(self, project: Path) -> None:
        with pytest.raises(AliasStoreError) as exc_info:
            store_alias(
                alias_name="prod/cluster",  # slash not allowed
                stripe_api_key=TEST_KEY_TEST,
                project_path=str(project),
            )
        assert exc_info.value.code == "E_INVALID_ALIAS_NAME"

    def test_alias_name_too_long_rejected(self, project: Path) -> None:
        with pytest.raises(AliasStoreError) as exc_info:
            store_alias(
                alias_name="x" * 65,
                stripe_api_key=TEST_KEY_TEST,
                project_path=str(project),
            )
        assert exc_info.value.code == "E_INVALID_ALIAS_NAME"


class TestStoreClassDirect:
    """Direct AliasStore instantiation (used by switch_account internals)."""

    def test_constructor_resolves_path(self, project: Path) -> None:
        store = AliasStore(project)
        assert store.store_path == project / DEFAULT_RELATIVE_PATH

    def test_two_aliases_share_kdf(self, project: Path) -> None:
        store_alias(alias_name="a", stripe_api_key=TEST_KEY_TEST, project_path=str(project))
        store_alias(alias_name="b", stripe_api_key=TEST_KEY_LIVE, project_path=str(project))
        assert resolve_alias(alias_name="a", project_path=str(project)) == TEST_KEY_TEST
        assert resolve_alias(alias_name="b", project_path=str(project)) == TEST_KEY_LIVE
