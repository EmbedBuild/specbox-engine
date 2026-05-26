"""Tests for v6.3.0 onboard_project default: native (was freeform pre-v6.3.0).

Covers the resolve_default_backend_type helper isolated from the MCP closure,
plus the validation set surface.
"""

from __future__ import annotations

import pytest

from server.tools.onboarding import (
    DEFAULT_BACKEND_TYPE,
    VALID_BACKEND_TYPES,
    resolve_default_backend_type,
)


class TestDefaultBackendType:
    def test_canonical_default_is_native(self):
        # v6.3.0 — explicit assertion so future drift is caught loudly.
        assert DEFAULT_BACKEND_TYPE == "native"

    def test_valid_set_includes_all_four_backends(self):
        assert VALID_BACKEND_TYPES == frozenset(
            {"freeform", "trello", "plane", "native"}
        )


class TestResolveDefaultBackendType:
    def test_no_args_returns_native(self):
        assert resolve_default_backend_type(None, None) == "native"

    def test_empty_string_treated_as_unset(self):
        # Empty string is the FastMCP-decoded value when the param is omitted
        # by the client. resolve_default_backend_type must treat it the same
        # as None.
        assert resolve_default_backend_type("", None) == "native"
        assert resolve_default_backend_type("", "") == "native"

    def test_trello_board_name_infers_trello(self):
        # Back-compat: pre-v5.29 onboards only knew the Trello path and never
        # passed backend_type. We honor that even in v6.3.0.
        assert resolve_default_backend_type(None, "MyBoard") == "trello"
        assert resolve_default_backend_type("", "MyBoard") == "trello"

    def test_explicit_backend_type_wins_over_trello_hint(self):
        # If the caller is explicit, we respect it — even if a board name is
        # also present (suggesting a config drift the caller knows about).
        assert resolve_default_backend_type("freeform", "MyBoard") == "freeform"
        assert resolve_default_backend_type("plane", "MyBoard") == "plane"
        assert resolve_default_backend_type("native", "MyBoard") == "native"

    def test_explicit_freeform_still_supported(self):
        # FreeForm is no longer the default but remains first-class. Solo /
        # air-gapped users explicitly opt-in here.
        assert resolve_default_backend_type("freeform", None) == "freeform"

    @pytest.mark.parametrize("explicit", ["freeform", "trello", "plane", "native"])
    def test_all_explicit_values_passthrough(self, explicit):
        assert resolve_default_backend_type(explicit, None) == explicit
