"""Encrypted alias store for Stripe API credentials.

Goal: let SpecBox projects hold multiple Stripe credentials at once (e.g.
'prod', 'staging', 'legacy') addressed by a short name, without ever leaving
sk_*  keys in plaintext on disk. The store lives in the project at
``.claude/secrets/stripe_aliases.enc.json``.

Design constraints:
- Encryption: AES-256-GCM with a key derived from the macOS Keychain entry
  ``com.specbox.stripe-alias-store`` (or ``SPECBOX_ALIAS_PASSPHRASE`` fallback
  on Linux/CI). The keychain entry is created on first use.
- Never log a plaintext key. Only names + last_used_at + key mode (test/live).
- Unique per project_path: every project has its own store.
- Backward-compatible: tools still accept raw ``stripe_api_key``; alias is
  opt-in via ``account_alias`` argument.

Format on disk (only the ``aliases`` field is encrypted; the rest is metadata):

```
{
  "version": 1,
  "kdf": "macos_keychain" | "passphrase_pbkdf2",
  "kdf_meta": {...},      # salt + iterations for passphrase, empty for keychain
  "nonce": "<base64>",
  "ciphertext": "<base64>",
  "tag": "<base64>",
  "aliases_meta": [
    {"name": "prod",     "mode": "live", "last_used_at": "2026-04-29T..."},
    {"name": "staging",  "mode": "test", "last_used_at": null}
  ]
}
```

The plaintext after decryption is::

    {"prod": "sk_live_***", "staging": "sk_test_***"}
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import hashes as _hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover — optional dep, alias store is opt-in
    _HAS_CRYPTO = False


KEYCHAIN_SERVICE = "com.specbox.stripe-alias-store"
KEYCHAIN_ACCOUNT = "default"
DEFAULT_RELATIVE_PATH = ".claude/secrets/stripe_aliases.enc.json"
PBKDF2_ITERATIONS = 480_000
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32  # AES-256


class AliasStoreError(Exception):
    """Raised when the alias store cannot be opened, decrypted, or modified."""

    def __init__(self, code: str, message: str, remediation: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


@dataclass
class AliasMetadata:
    """Public, non-sensitive metadata for an alias entry."""

    name: str
    mode: str  # 'test' | 'live'
    last_used_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# ---------------------------------------------------------------------------
# Key derivation backends
# ---------------------------------------------------------------------------


def _derive_key_macos_keychain() -> bytes:
    """Use the macOS Keychain to store/retrieve a 32-byte master key.

    On first use we generate a random 256-bit key and store it. Subsequent
    calls retrieve it. The keychain entry is per-user; multiple projects
    share the same master key (they are still isolated by their own
    nonce + ciphertext, but a stolen keychain unlocks all of them).
    """
    if platform.system() != "Darwin":
        raise AliasStoreError(
            code="E_KEYCHAIN_UNSUPPORTED",
            message="macOS Keychain is only available on macOS.",
            remediation="Set SPECBOX_ALIAS_PASSPHRASE env var to use passphrase-based KDF instead.",
        )

    # Try retrieve.
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise AliasStoreError(
            code="E_KEYCHAIN_UNAVAILABLE",
            message=f"macOS 'security' tool unavailable: {exc}",
        ) from exc

    if result.returncode == 0:
        encoded = result.stdout.strip()
        try:
            return base64.b64decode(encoded)
        except ValueError as exc:
            raise AliasStoreError(
                code="E_KEYCHAIN_CORRUPT",
                message="Keychain entry is not valid base64. Manual fix required.",
                remediation=f"Run: security delete-generic-password -s {KEYCHAIN_SERVICE}",
            ) from exc

    # Not found — create.
    new_key = secrets.token_bytes(KEY_BYTES)
    encoded = base64.b64encode(new_key).decode("ascii")
    create = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w", encoded,
            "-T", "",  # accessible by no apps without explicit user allow
            "-U",       # update if already exists
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if create.returncode != 0:
        raise AliasStoreError(
            code="E_KEYCHAIN_WRITE_FAILED",
            message=f"Failed to store master key in keychain: {create.stderr.strip()}",
        )
    return new_key


def _derive_key_passphrase(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 key derivation from a passphrase. Used on Linux/CI."""
    if not _HAS_CRYPTO:
        raise AliasStoreError(
            code="E_CRYPTO_NOT_INSTALLED",
            message="Package 'cryptography' is required for the alias store.",
            remediation="Install with: pip install 'cryptography>=42'",
        )
    kdf = PBKDF2HMAC(
        algorithm=_hashes.SHA256(),
        length=KEY_BYTES,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _resolve_master_key(kdf_meta: dict[str, Any] | None) -> tuple[bytes, str, dict[str, Any]]:
    """Resolve the master key + return (key, kdf_name, kdf_meta).

    On first write kdf_meta=None; we pick macOS keychain if available, else
    passphrase fallback. On read we honor whatever the file says.
    """
    if kdf_meta is None:
        # First write: pick the best available backend. SPECBOX_ALIAS_PASSPHRASE
        # takes precedence over Keychain so users (and tests) can opt into
        # passphrase mode explicitly even on macOS.
        passphrase = os.environ.get("SPECBOX_ALIAS_PASSPHRASE", "")
        if passphrase:
            salt = secrets.token_bytes(SALT_BYTES)
            return (
                _derive_key_passphrase(passphrase, salt),
                "passphrase_pbkdf2",
                {"salt": base64.b64encode(salt).decode("ascii"), "iterations": PBKDF2_ITERATIONS},
            )
        if platform.system() == "Darwin":
            return _derive_key_macos_keychain(), "macos_keychain", {}
        raise AliasStoreError(
            code="E_NO_KEY_BACKEND",
            message="No key backend available (not on macOS, SPECBOX_ALIAS_PASSPHRASE unset).",
            remediation="Run on macOS, or export SPECBOX_ALIAS_PASSPHRASE.",
        )

    if isinstance(kdf_meta, dict) and "salt" in kdf_meta:
        # passphrase mode
        passphrase = os.environ.get("SPECBOX_ALIAS_PASSPHRASE", "")
        if not passphrase:
            raise AliasStoreError(
                code="E_PASSPHRASE_MISSING",
                message="Alias store was created with passphrase KDF but SPECBOX_ALIAS_PASSPHRASE is not set.",
            )
        salt = base64.b64decode(kdf_meta["salt"])
        return (
            _derive_key_passphrase(passphrase, salt),
            "passphrase_pbkdf2",
            kdf_meta,
        )
    # else macos_keychain (no metadata needed)
    return _derive_key_macos_keychain(), "macos_keychain", {}


# ---------------------------------------------------------------------------
# AliasStore implementation
# ---------------------------------------------------------------------------


class AliasStore:
    """Encrypted alias store living in a project's .claude/secrets/ directory."""

    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path).resolve()
        self.store_path = self.project_path / DEFAULT_RELATIVE_PATH

    # --- Public API --------------------------------------------------------

    def store(self, alias_name: str, stripe_api_key: str) -> AliasMetadata:
        """Add or update an alias. Returns the public metadata (no key value)."""
        self._validate_alias_name(alias_name)
        mode = self._detect_key_mode(stripe_api_key)
        if mode == "invalid":
            raise AliasStoreError(
                code="E_INVALID_KEY",
                message="Stripe API key must be sk_test_* or sk_live_*.",
            )

        plain, kdf_meta, aliases_meta = self._load_or_init()
        plain[alias_name] = stripe_api_key

        # Update or insert metadata.
        existing = next((m for m in aliases_meta if m.name == alias_name), None)
        if existing is None:
            existing = AliasMetadata(name=alias_name, mode=mode)
            aliases_meta.append(existing)
        else:
            existing.mode = mode

        self._write(plain, kdf_meta, aliases_meta)
        self._ensure_gitignored()
        return existing

    def list(self) -> list[AliasMetadata]:
        """Return alias metadata (names + modes + last_used_at). NEVER values."""
        if not self.store_path.exists():
            return []
        try:
            _, _, aliases_meta = self._load()
        except AliasStoreError:
            raise
        return list(aliases_meta)

    def resolve(self, alias_name: str, *, mark_used: bool = True) -> str:
        """Return the plaintext API key for ``alias_name``.

        If ``mark_used=True`` (default), bump the last_used_at metadata.
        """
        plain, kdf_meta, aliases_meta = self._load()
        if alias_name not in plain:
            raise AliasStoreError(
                code="E_ALIAS_NOT_FOUND",
                message=f"Alias {alias_name!r} not found in {self.store_path}",
                remediation="Run store_stripe_alias() with this alias_name first.",
            )

        if mark_used:
            now = datetime.now(UTC).isoformat()
            for m in aliases_meta:
                if m.name == alias_name:
                    m.last_used_at = now
                    break
            self._write(plain, kdf_meta, aliases_meta)

        return plain[alias_name]

    def delete(self, alias_name: str, confirm_token: str) -> bool:
        """Delete an alias. Requires the literal confirmation token."""
        expected = f"I want to delete the {alias_name} alias"
        if confirm_token != expected:
            raise AliasStoreError(
                code="E_CONFIRMATION_REQUIRED",
                message="Delete requires the literal confirm_token.",
                remediation=f"Pass confirm_token='{expected}'.",
            )

        if not self.store_path.exists():
            return False
        plain, kdf_meta, aliases_meta = self._load()
        if alias_name not in plain:
            return False

        del plain[alias_name]
        aliases_meta = [m for m in aliases_meta if m.name != alias_name]

        if not plain:
            # Empty store: remove the file entirely.
            self.store_path.unlink()
            return True
        self._write(plain, kdf_meta, aliases_meta)
        return True

    # --- Internals ---------------------------------------------------------

    def _load_or_init(self) -> tuple[dict[str, str], dict[str, Any], list[AliasMetadata]]:
        if self.store_path.exists():
            return self._load()
        return {}, {}, []

    def _load(self) -> tuple[dict[str, str], dict[str, Any], list[AliasMetadata]]:
        if not _HAS_CRYPTO:
            raise AliasStoreError(
                code="E_CRYPTO_NOT_INSTALLED",
                message="Package 'cryptography' is required to read the alias store.",
                remediation="Install with: pip install 'cryptography>=42'",
            )
        try:
            with self.store_path.open("r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise AliasStoreError(
                code="E_STORE_CORRUPT",
                message=f"Cannot read alias store at {self.store_path}: {exc}",
            ) from exc

        version = blob.get("version")
        if version != 1:
            raise AliasStoreError(
                code="E_UNSUPPORTED_VERSION",
                message=f"Unsupported alias store version {version!r}.",
            )

        # Resolve master key per file's KDF.
        kdf_name = blob.get("kdf")
        kdf_meta_persisted = blob.get("kdf_meta") or {}
        if kdf_name == "passphrase_pbkdf2":
            key, _, kdf_meta = _resolve_master_key(kdf_meta_persisted)
        else:
            key, _, kdf_meta = _resolve_master_key(None)
            kdf_meta = {}

        nonce = base64.b64decode(blob["nonce"])
        ciphertext = base64.b64decode(blob["ciphertext"])
        # GCM tag is appended to ciphertext by AESGCM.encrypt; we stored them
        # together in 'ciphertext' to keep the on-disk format simple.

        try:
            plaintext_bytes = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise AliasStoreError(
                code="E_DECRYPT_FAILED",
                message=(
                    "Cannot decrypt alias store. Wrong passphrase, "
                    "missing keychain entry, or tampered file."
                ),
            ) from exc

        try:
            plain = json.loads(plaintext_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AliasStoreError(
                code="E_PLAINTEXT_CORRUPT",
                message="Decrypted plaintext is not valid JSON.",
            ) from exc

        if not isinstance(plain, dict) or any(not isinstance(v, str) for v in plain.values()):
            raise AliasStoreError(
                code="E_PLAINTEXT_SHAPE",
                message="Decrypted plaintext shape is unexpected (expected {alias: api_key}).",
            )

        aliases_meta_raw = blob.get("aliases_meta", [])
        aliases_meta = [
            AliasMetadata(
                name=m["name"],
                mode=m.get("mode", "test"),
                last_used_at=m.get("last_used_at"),
                created_at=m.get("created_at", datetime.now(UTC).isoformat()),
            )
            for m in aliases_meta_raw
        ]
        return plain, kdf_meta, aliases_meta

    def _write(
        self,
        plain: dict[str, str],
        kdf_meta: dict[str, Any],
        aliases_meta: list[AliasMetadata],
    ) -> None:
        if not _HAS_CRYPTO:
            raise AliasStoreError(
                code="E_CRYPTO_NOT_INSTALLED",
                message="Package 'cryptography' is required to write the alias store.",
            )

        if not plain:
            # Nothing to persist — remove the file if any.
            if self.store_path.exists():
                self.store_path.unlink()
            return

        # If kdf_meta is empty we're writing for the first time — pick backend.
        if not kdf_meta:
            key, kdf_name, kdf_meta = _resolve_master_key(None)
        else:
            key, kdf_name, kdf_meta = _resolve_master_key(kdf_meta)

        nonce = secrets.token_bytes(NONCE_BYTES)
        plaintext = json.dumps(plain, sort_keys=True).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

        out = {
            "version": 1,
            "kdf": kdf_name,
            "kdf_meta": kdf_meta,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "aliases_meta": [
                {
                    "name": m.name,
                    "mode": m.mode,
                    "last_used_at": m.last_used_at,
                    "created_at": m.created_at,
                }
                for m in aliases_meta
            ],
        }

        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp + rename.
        tmp = self.store_path.with_suffix(self.store_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
            fh.write("\n")
        tmp.replace(self.store_path)
        # Tighten permissions to 0600 (best effort; Windows ignores).
        try:
            os.chmod(self.store_path, 0o600)
        except OSError:
            pass

    def _ensure_gitignored(self) -> None:
        """Append .claude/secrets/ to .gitignore if not already present."""
        gitignore = self.project_path / ".gitignore"
        line = ".claude/secrets/"
        try:
            existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
            if line in existing.splitlines():
                return
            with gitignore.open("a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(f"# specbox-stripe-mcp alias store\n{line}\n")
        except OSError:
            # Don't fail the store operation just because we couldn't update .gitignore.
            # The user will see a warning elsewhere.
            pass

    @staticmethod
    def _validate_alias_name(name: str) -> None:
        if not name or not name.strip():
            raise AliasStoreError(code="E_INVALID_ALIAS_NAME", message="Alias name cannot be empty.")
        if len(name) > 64:
            raise AliasStoreError(
                code="E_INVALID_ALIAS_NAME",
                message="Alias name cannot exceed 64 characters.",
            )
        # Allow letters, digits, hyphen, underscore.
        for ch in name:
            if not (ch.isalnum() or ch in "-_"):
                raise AliasStoreError(
                    code="E_INVALID_ALIAS_NAME",
                    message=f"Alias name {name!r} has invalid characters. Use [A-Za-z0-9_-].",
                )

    @staticmethod
    def _detect_key_mode(api_key: str) -> str:
        if not isinstance(api_key, str):
            return "invalid"
        if api_key.startswith("sk_test_") and len(api_key) > 12:
            return "test"
        if api_key.startswith("sk_live_") and len(api_key) > 12:
            return "live"
        return "invalid"


# ---------------------------------------------------------------------------
# Convenience module-level helpers (used by the FastMCP tools)
# ---------------------------------------------------------------------------


def store_alias(*, alias_name: str, stripe_api_key: str, project_path: str) -> dict[str, Any]:
    store = AliasStore(project_path)
    meta = store.store(alias_name, stripe_api_key)
    return {
        "alias_name": meta.name,
        "mode": meta.mode,
        "last_used_at": meta.last_used_at,
        "created_at": meta.created_at,
        "store_path": str(store.store_path),
    }


def list_aliases(*, project_path: str) -> list[dict[str, Any]]:
    store = AliasStore(project_path)
    return [
        {
            "alias_name": m.name,
            "mode": m.mode,
            "last_used_at": m.last_used_at,
            "created_at": m.created_at,
        }
        for m in store.list()
    ]


def delete_alias(*, alias_name: str, project_path: str, confirm_token: str) -> bool:
    store = AliasStore(project_path)
    return store.delete(alias_name, confirm_token)


def resolve_alias(*, alias_name: str, project_path: str) -> str:
    store = AliasStore(project_path)
    return store.resolve(alias_name)


# Avoid mypy unused import warnings when crypto is missing.
_ = (hashlib, time)
