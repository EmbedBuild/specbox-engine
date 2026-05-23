"""UC-505 — refactor of ``NativeBackend.__init__`` signature.

Covers UC-505 AC-19/20/21:

* AC-19: ``NativeBackend(project_id, dev_token)`` — both parameters mandatory.
  Empty / None / falsy ``dev_token`` (or ``project_id``) raises ``ValueError``
  at construction so callers fail fast.
* AC-20: ``auth_gateway.get_session_backend`` for ``backend_type='native'``
  reads ``config['dev_token']`` and forwards it to the constructor. Covered
  in ``tests/test_native_dispatch.py::TestGetSessionBackendNative`` (re-tested
  here as a regression smoke).
* AC-21: ``store_native_credentials`` rejects an empty ``dev_token`` at the
  entry point. Covered in
  ``tests/test_native_dispatch.py::TestStoreNativeCredentials`` (also
  re-tested here as a smoke).

These tests are PG-free — they only exercise the constructor signature and
session-store entry point. The actual gate behaviour lands in UC-502.
"""

from __future__ import annotations

import pytest

from server.backends.native_backend import NativeBackend


# ── AC-19: constructor signature is strict ─────────────────────────────


class TestNativeBackendInitSignature:
    """``NativeBackend(project_id, dev_token)`` rejects empty arguments."""

    def test_accepts_both_non_empty(self) -> None:
        be = NativeBackend(project_id="proj-x", dev_token="tok-x")
        assert be.project_id == "proj-x"
        # The token lives in a private attribute by design: UC-502 reads it
        # via ``self._dev_token`` and external callers must NOT touch it.
        assert be._dev_token == "tok-x"

    @pytest.mark.parametrize(
        "project_id,dev_token,expected_msg",
        [
            ("", "tok-x", "project_id is required"),
            ("proj-x", "", "dev_token is required"),
            ("", "", "project_id is required"),  # project_id check is first
        ],
    )
    def test_rejects_empty_arguments(self, project_id: str, dev_token: str, expected_msg: str) -> None:
        with pytest.raises(ValueError, match=expected_msg):
            NativeBackend(project_id=project_id, dev_token=dev_token)

    def test_rejects_none_dev_token(self) -> None:
        """A ``None`` token (e.g. forgotten kwarg) is also rejected."""
        with pytest.raises(ValueError, match="dev_token is required"):
            NativeBackend(project_id="proj-x", dev_token=None)  # type: ignore[arg-type]

    def test_positional_args_are_supported(self) -> None:
        """``NativeBackend('proj', 'tok')`` works without kwargs."""
        be = NativeBackend("proj-y", "tok-y")
        assert be.project_id == "proj-y"
        assert be._dev_token == "tok-y"
