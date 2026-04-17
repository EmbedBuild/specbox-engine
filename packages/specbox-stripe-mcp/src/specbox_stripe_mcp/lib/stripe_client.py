"""Wrapper around the official Stripe SDK with retry + structured logging.

Keeps SDK construction and request options in one place so all tools share the same
User-Agent, api_version, and retry policy.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import stripe

from .heartbeat import report_healing
from .safety import redact_log_line

T = TypeVar("T")

DEFAULT_API_VERSION = "2024-11-20.acacia"
USER_AGENT = "specbox-stripe-mcp/0.1.0"
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_S = 0.5

logger = logging.getLogger("specbox_stripe_mcp.client")


class StripeClient:
    """Thin wrapper that configures the stripe SDK and runs calls with retry.

    The Stripe SDK is module-global; we scope configuration to a per-call context
    by setting stripe.api_key before each invocation. Concurrency across requests
    is not a concern for the MCP use case (single request in flight per tool call).
    """

    def __init__(self, api_key: str, *, api_version: str | None = None) -> None:
        self.api_key = api_key
        self.api_version = api_version or DEFAULT_API_VERSION

    def _activate(self) -> None:
        stripe.api_key = self.api_key
        stripe.api_version = self.api_version
        stripe.set_app_info(name="specbox-stripe-mcp", version="0.1.0")

    def call(self, op: str, func: Callable[[], T]) -> T:
        """Execute a Stripe SDK call with retry on transient errors.

        `op` is a human-readable operation label for logs (e.g. "accounts.retrieve").
        Retries on RateLimitError and APIConnectionError. Does not retry on
        AuthenticationError, InvalidRequestError, or CardError.
        """
        self._activate()
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = func()
                if attempt > 1:
                    logger.info(
                        redact_log_line(
                            f"stripe.{op} recovered on attempt={attempt}"
                        )
                    )
                    # Report healing when we recover from a transient error.
                    try:
                        report_healing(
                            project="stripe-mcp",
                            hook=op,
                            root_cause="rate_limit" if isinstance(last_exc, stripe.error.RateLimitError) else "connection_error",  # type: ignore[attr-defined]
                            resolution="retry",
                        )
                    except Exception as exc:
                        logger.debug("healing report skipped: %s", exc)
                return result
            except stripe.error.RateLimitError as e:  # type: ignore[attr-defined]
                last_exc = e
                sleep_s = RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    redact_log_line(
                        f"stripe.{op} rate-limited (attempt={attempt}), retrying in {sleep_s:.2f}s"
                    )
                )
                time.sleep(sleep_s)
            except stripe.error.APIConnectionError as e:  # type: ignore[attr-defined]
                last_exc = e
                sleep_s = RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    redact_log_line(
                        f"stripe.{op} connection error (attempt={attempt}), retrying in {sleep_s:.2f}s"
                    )
                )
                time.sleep(sleep_s)
            except stripe.error.StripeError as e:  # type: ignore[attr-defined]
                logger.error(redact_log_line(f"stripe.{op} failed: {e}"))
                raise
        assert last_exc is not None
        logger.error(redact_log_line(f"stripe.{op} exhausted retries: {last_exc}"))
        raise last_exc
