"""Thin httpx wrapper for the Supabase Management API with retry + logging.

Supabase exposes:
- GET /v1/projects/{ref}/secrets      — list names + updated_at
- POST /v1/projects/{ref}/secrets     — bulk create/overwrite
- DELETE /v1/projects/{ref}/secrets   — bulk delete

Auth via `Authorization: Bearer <PAT>`. Rate limit 120 req/min.

The wrapper retries on 429 and connection errors with exponential backoff and
emits ``report_healing`` on successful recovery (same contract as the Stripe
MCP's StripeClient).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .heartbeat import report_healing
from .safety import redact_log_line

DEFAULT_BASE_URL = "https://api.supabase.com"
USER_AGENT = "specbox-supabase-mcp/0.1.0"
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_S = 0.5
REQUEST_TIMEOUT_S = 30.0

logger = logging.getLogger("specbox_supabase_mcp.client")


class SupabaseAPIError(Exception):
    """Non-retryable Supabase Management API error (4xx excluding 429)."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class SupabaseClient:
    """Thin wrapper that scopes a PAT to a base URL and applies retry policy.

    Not async — matches the sync patterns of the rest of the SpecBox MCPs. If
    a caller needs concurrency it can run multiple clients in threads.
    """

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str | None = None,
        project_hint: str = "unknown",
    ) -> None:
        self.access_token = access_token
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.project_hint = project_hint

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    def call(
        self,
        op: str,
        method: str,
        path: str,
        *,
        json: Any = None,
    ) -> httpx.Response:
        """Execute a single request with retry on transient errors.

        `op` is a human-readable label for logs (e.g. 'secrets.list').
        Retries on 429 and httpx.ConnectError / httpx.ReadTimeout. Everything
        else propagates as SupabaseAPIError with its original status_code.
        """
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
                    response = client.request(
                        method,
                        url,
                        headers=self._headers(),
                        json=json,
                    )
                if response.status_code == 429:
                    last_exc = SupabaseAPIError(
                        status_code=429,
                        message="Supabase rate limit exceeded",
                    )
                    sleep_s = RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        redact_log_line(
                            f"supabase.{op} rate-limited (attempt={attempt}), "
                            f"retrying in {sleep_s:.2f}s"
                        )
                    )
                    time.sleep(sleep_s)
                    continue
                if response.status_code >= 400:
                    # Non-retryable 4xx — let caller classify into error codes.
                    raise SupabaseAPIError(
                        status_code=response.status_code,
                        message=_safe_error_message(response),
                    )
                if attempt > 1:
                    logger.info(
                        redact_log_line(
                            f"supabase.{op} recovered on attempt={attempt}"
                        )
                    )
                    _emit_healing(
                        self.project_hint,
                        op,
                        root_cause=(
                            "rate_limit"
                            if isinstance(last_exc, SupabaseAPIError)
                            and last_exc.status_code == 429
                            else "connection_error"
                        ),
                    )
                return response
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                sleep_s = RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    redact_log_line(
                        f"supabase.{op} connection error (attempt={attempt}), "
                        f"retrying in {sleep_s:.2f}s: {exc}"
                    )
                )
                time.sleep(sleep_s)
        # Retries exhausted
        assert last_exc is not None
        logger.error(redact_log_line(f"supabase.{op} exhausted retries: {last_exc}"))
        raise last_exc


def _safe_error_message(response: httpx.Response) -> str:
    """Extract a human-readable error message from a Supabase response.

    Supabase returns JSON like {"message": "..."} on errors. Fall back to
    status-line if parsing fails.
    """
    try:
        body = response.json()
        if isinstance(body, dict):
            msg = body.get("message") or body.get("error") or ""
            if msg:
                return redact_log_line(str(msg))
    except Exception:
        pass
    return f"HTTP {response.status_code}"


def _emit_healing(project_hint: str, op: str, *, root_cause: str) -> None:
    try:
        report_healing(
            project=project_hint,
            hook=op,
            root_cause=root_cause,
            resolution="retry",
        )
    except Exception as exc:
        logger.debug("healing report skipped: %s", exc)
