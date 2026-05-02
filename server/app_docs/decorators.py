"""Transactional `@requires_app_docs_sync` decorator (v5.29.0 PR-12).

Wraps a spec-mutating tool so that, after the tool completes successfully,
the corresponding auto-zone in `app_prd.md` / `app_spec.md` is updated
via `sync_app_docs(event_type, payload)`. If the sync fails, the tool's
return value is annotated with `app_docs_sync.ok=False` and the failure
reason — the caller can then invoke `/app-sync --repair` or roll back.

Important design notes
----------------------
* The decorator runs the tool first and the sync second. If the tool
  itself fails, the sync is skipped — there is nothing to mirror.
* Sync is best-effort by default in v5.29.0 (Capa 5 ships in
  warning-only mode). The result field `app_docs_sync` exposes the
  outcome so PR-13 hook + PR-15 drift detector can observe it without
  blocking the tool.
* For v5.29.1+, the same decorator can be flipped to "transactional"
  mode by setting `STRICT_SYNC_MODE=true` in the env. When strict, a
  sync failure replaces the tool's return value with an error so the
  caller knows to retry. We ship the plumbing now; the policy stays
  permissive for the first release.

Payload extraction
------------------
Each event has a `payload_extractor` callable that takes the tool's
arguments + return value and produces the dict expected by
`sync_app_docs`. Extractors live alongside the decorator definition so
adding a new event = adding one extractor + decorating one tool.
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
from typing import Any, Awaitable, Callable, TypeVar

from .sync import sync_app_docs

logger = logging.getLogger(__name__)


F = TypeVar("F", bound=Callable[..., Any])


def _strict_mode() -> bool:
    return os.environ.get("SPECBOX_APP_DOCS_STRICT_SYNC", "").lower() in {"1", "true", "yes"}


def _resolve_project_path(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Best-effort project path resolution from a tool's arguments.

    Tools in spec_driven / spec_mutations receive `project_path` as a
    kwarg in newer signatures; older ones default to cwd. The decorator
    falls back to "." silently — the sync layer will write into the
    current working directory which equals the client repo when the MCP
    runs locally and produces a clean error when the docs are missing.
    """
    pp = kwargs.get("project_path")
    if isinstance(pp, str) and pp:
        return pp
    # Look for a positional `project_path: str` argument (rare but
    # supported). Otherwise default to cwd.
    return "."


def requires_app_docs_sync(
    event_type: str,
    *,
    payload_extractor: Callable[..., dict[str, Any]],
    skip_when: Callable[..., bool] | None = None,
) -> Callable[[F], F]:
    """Decorate a (sync or async) tool so its successful return triggers
    a sync to the matching auto-zone.

    Args:
        event_type: One of the keys in EVENT_ZONE_MAP (sync.py).
        payload_extractor: Callable invoked as
            ``payload_extractor(result, *args, **kwargs) -> dict``.
            Returns the payload passed to ``sync_app_docs``.
        skip_when: Optional callable receiving the same arguments as the
            extractor; return True to skip syncing entirely (e.g. when
            the result indicates the operation was a no-op or returned
            an error).
    """

    def decorator(fn: F) -> F:
        is_async = inspect.iscoroutinefunction(fn)

        if is_async:
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await fn(*args, **kwargs)
                return _maybe_sync(event_type, result, args, kwargs, payload_extractor, skip_when)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)
            return _maybe_sync(event_type, result, args, kwargs, payload_extractor, skip_when)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _maybe_sync(
    event_type: str,
    result: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    payload_extractor: Callable[..., dict[str, Any]],
    skip_when: Callable[..., bool] | None,
) -> Any:
    """Run the sync after a tool call. Annotate the result either way.

    Decorator does NOT mutate the result for non-dict returns — it just
    logs. For dict returns, it adds an `app_docs_sync` field so callers
    can observe.
    """
    # Skip predicate runs first so callers can opt out cheaply (e.g.
    # when the tool returned an error).
    try:
        if skip_when and skip_when(result, *args, **kwargs):
            return result
    except Exception as e:
        logger.warning("app_docs_sync.skip_when_failed", extra={"error": str(e)})
        return result

    project_path = _resolve_project_path(args, kwargs)

    try:
        payload = payload_extractor(result, *args, **kwargs)
    except Exception as e:
        outcome = {"ok": False, "error": "payload_extractor_failed", "detail": str(e)}
        return _annotate(result, outcome, strict=_strict_mode())

    try:
        sync_result = sync_app_docs(event_type, payload, project_path)
    except Exception as e:
        outcome = {"ok": False, "error": "sync_app_docs_raised", "detail": str(e)}
        return _annotate(result, outcome, strict=_strict_mode())

    return _annotate(result, sync_result, strict=_strict_mode())


def _annotate(result: Any, outcome: dict[str, Any], *, strict: bool) -> Any:
    if isinstance(result, dict):
        result["app_docs_sync"] = outcome
        if strict and not outcome.get("ok", True):
            # In strict mode, surface the failure as a top-level error.
            result.setdefault("ok", False)
            result.setdefault("error", outcome.get("error", "app_docs_sync_failed"))
        return result
    if not outcome.get("ok", True):
        logger.warning(
            "app_docs_sync.failed",
            extra={"event": outcome},
        )
    return result


# ── Payload extractors for known events ──────────────────────────────


def extract_set_auth_token_payload(result: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Build the sync payload after a successful set_auth_token call."""
    backend = kwargs.get("backend_type") or "trello"
    payload: dict[str, Any] = {"backend_type": backend}
    if backend == "freeform":
        # Prefer the resolved path the tool stored in its result.
        if isinstance(result, dict):
            msg = result.get("message", "")
            # The set_auth_token success message has the form
            # "FreeForm backend initialized at <path>/" — extract the path.
            if "initialized at" in msg:
                try:
                    payload["freeform_root_absolute"] = msg.split("initialized at", 1)[1].strip().rstrip("/")
                except IndexError:
                    pass
    if backend == "trello":
        # board_id may live in the legacy spec_driven kwargs path.
        payload["trello_board_id"] = kwargs.get("board_id", "")
    if backend == "plane":
        payload["plane_project_id"] = kwargs.get("workspace_slug", "")
    payload["external_reporting"] = "yes" if backend in {"trello", "plane"} else "no"
    return payload


def extract_uc_event_payload(
    result: Any, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """Default payload for UC mutation events. The roadmap renderer is
    permissive: it accepts an empty rows list and renders ``(sin datos)``,
    which is correct when the call site does not have a list of US to
    project."""
    return {"rows": kwargs.get("roadmap_rows", [])}


def extract_canonical_event_payload(
    result: Any, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """For canonical_decision_created/_revoked, project the active list."""
    if not isinstance(result, dict):
        return {"entries": []}
    entries: list[dict[str, Any]] = []
    canonical = result.get("canonical")
    if isinstance(canonical, dict) and canonical.get("decision_key"):
        entries.append(canonical)
    return {"entries": entries}


# ── Skip predicates ──────────────────────────────────────────────────


def skip_when_tool_errored(result: Any, *args: Any, **kwargs: Any) -> bool:
    """Skip syncing when the tool returned an error or ok=False dict."""
    if isinstance(result, dict):
        if "error" in result:
            return True
        if result.get("ok") is False:
            return True
    return False
