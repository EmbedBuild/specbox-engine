"""Tests for the stitch_orchestration module (v5.31.0 Phase 4).

Covers fallback chain behaviour and batched build_site partitioning +
unified theme pass. Uses an in-memory ``StitchOps`` mock — no network.
"""

from __future__ import annotations

from typing import Any

import pytest

from server.stitch_orchestration.batching import (
    ScreenSpec,
    build_site_batched,
    partition_screens,
    plan_build,
)
from server.stitch_orchestration.fallback import (
    FallbackOutcome,
    FallbackStrategy,
    classify_error,
    generate_screen_with_fallback,
)


# ── Mock client ─────────────────────────────────────────────────────────


class FakeOps:
    """A scriptable in-memory stand-in for StitchClient."""

    def __init__(self, scripts: dict[str, list]):
        """``scripts`` maps method name → list of either values or
        Exception instances. Each call pops the head."""
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.calls: list[dict] = []

    def _consume(self, method: str, **kwargs) -> Any:
        self.calls.append({"method": method, **kwargs})
        seq = self.scripts.get(method, [])
        if not seq:
            raise RuntimeError(f"no script entries left for {method}")
        nxt = seq.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    async def generate_screen(
        self, project_id, prompt, *, device_type="DESKTOP", model_id="GEMINI_3_PRO"
    ):
        return self._consume(
            "generate_screen",
            project_id=project_id,
            prompt=prompt,
            device_type=device_type,
            model_id=model_id,
        )

    async def edit_screens(
        self, project_id, screen_id, prompt, *, device_type=None, model_id=None
    ):
        return self._consume(
            "edit_screens",
            project_id=project_id,
            screen_id=screen_id,
            prompt=prompt,
            model_id=model_id,
        )

    async def generate_variants(
        self,
        project_id,
        screen_id,
        *,
        prompt=None,
        variant_count=1,
        creative_range="REFINE",
        aspects=None,
    ):
        return self._consume(
            "generate_variants",
            project_id=project_id,
            screen_id=screen_id,
            prompt=prompt,
            creative_range=creative_range,
        )

    async def build_site(self, project_id, routes):
        return self._consume("build_site", project_id=project_id, routes=routes)


# ── Error classification ───────────────────────────────────────────────


class TestClassifyError:
    @pytest.mark.parametrize(
        "msg, expected",
        [
            ("Read timeout after 360s", "transient"),
            ("HTTP 503 Service Unavailable", "transient"),
            ("connection reset by peer", "transient"),
            ("rate limit exceeded", "quota"),
            ("monthly quota exhausted", "quota"),
            ("HTTP 429 Too Many Requests", "quota"),
            ("content policy violation: unsafe", "content"),
            ("something wholly unexpected", "unknown"),
        ],
    )
    def test_classify(self, msg, expected):
        assert classify_error(RuntimeError(msg)) == expected


# ── Fallback chain ─────────────────────────────────────────────────────


class TestFallbackHappyPath:
    @pytest.mark.asyncio
    async def test_first_try_returns_immediately(self):
        ops = FakeOps({"generate_screen": [{"screen_id": "s1"}]})
        r = await generate_screen_with_fallback(ops, "p1", "Login screen")
        assert r.outcome == FallbackOutcome.OK_FIRST_TRY
        assert r.final_strategy == FallbackStrategy.REGENERATE.value
        assert r.degraded is False
        assert len(ops.calls) == 1


class TestFallbackPaths:
    @pytest.mark.asyncio
    async def test_falls_back_to_edit_baseline(self):
        ops = FakeOps(
            {
                "generate_screen": [TimeoutError("Read timeout after 360s")],
                "edit_screens": [{"screen_id": "s_edited"}],
            }
        )
        r = await generate_screen_with_fallback(
            ops, "p1", "Login screen", baseline_screen_id="s_existing"
        )
        assert r.outcome == FallbackOutcome.OK_AFTER_FALLBACK
        assert r.final_strategy == FallbackStrategy.EDIT_BASELINE.value
        assert r.attempts[0]["status"] == "error"
        assert r.attempts[0]["error_class"] == "transient"

    @pytest.mark.asyncio
    async def test_skips_baseline_strategies_when_no_baseline(self):
        ops = FakeOps(
            {
                "generate_screen": [
                    TimeoutError("Read timeout"),
                    {"screen_id": "s_regen"},
                ],
            }
        )
        r = await generate_screen_with_fallback(
            ops, "p1", "Login", baseline_screen_id=None
        )
        # We try REGENERATE in the natural call (fail), then again as
        # the explicit ladder step (succeed).
        assert r.outcome == FallbackOutcome.OK_AFTER_FALLBACK
        assert r.final_strategy == FallbackStrategy.REGENERATE.value
        assert all(
            a["strategy"] != FallbackStrategy.EDIT_BASELINE.value
            for a in r.attempts
        )

    @pytest.mark.asyncio
    async def test_variants_refine_after_edit_fails(self):
        ops = FakeOps(
            {
                "generate_screen": [TimeoutError("Read timeout")],
                "edit_screens": [TimeoutError("Read timeout")],
                "generate_variants": [{"screen_id": "s_variant"}],
            }
        )
        r = await generate_screen_with_fallback(
            ops, "p1", "Login", baseline_screen_id="s_existing"
        )
        assert r.outcome == FallbackOutcome.OK_AFTER_FALLBACK
        assert r.final_strategy == FallbackStrategy.VARIANTS_REFINE.value


class TestFlashSafetyNet:
    @pytest.mark.asyncio
    async def test_off_by_default(self):
        ops = FakeOps(
            {
                "generate_screen": [
                    RuntimeError("monthly quota exhausted"),
                    RuntimeError("monthly quota exhausted"),
                ],
            }
        )
        r = await generate_screen_with_fallback(
            ops, "p1", "Login", baseline_screen_id=None
        )
        assert r.outcome == FallbackOutcome.FAILED
        assert r.degraded is False
        # Only PRO calls were made.
        assert all(c.get("model_id") == "GEMINI_3_PRO" for c in ops.calls)

    @pytest.mark.asyncio
    async def test_engaged_when_opted_in_and_pro_exhausted(self):
        ops = FakeOps(
            {
                "generate_screen": [
                    RuntimeError("monthly quota exhausted"),
                    RuntimeError("monthly quota exhausted"),
                    {"screen_id": "s_flash", "model": "FLASH"},
                ],
            }
        )
        r = await generate_screen_with_fallback(
            ops,
            "p1",
            "Login",
            baseline_screen_id=None,
            enable_flash_safety_net=True,
            max_total_attempts=5,
        )
        assert r.outcome == FallbackOutcome.OK_DEGRADED
        assert r.degraded is True
        assert r.model_used == "GEMINI_3_FLASH"
        assert "quota" in (r.degraded_reason or "").lower()

    @pytest.mark.asyncio
    async def test_does_not_engage_if_pro_succeeds_via_fallback(self):
        ops = FakeOps(
            {
                "generate_screen": [
                    TimeoutError("Read timeout"),
                    {"screen_id": "s_regen"},
                ],
            }
        )
        r = await generate_screen_with_fallback(
            ops,
            "p1",
            "Login",
            baseline_screen_id=None,
            enable_flash_safety_net=True,
        )
        assert r.outcome == FallbackOutcome.OK_AFTER_FALLBACK
        assert r.degraded is False
        assert r.model_used == "GEMINI_3_PRO"


class TestFallbackBudget:
    @pytest.mark.asyncio
    async def test_respects_max_total_attempts(self):
        ops = FakeOps(
            {
                "generate_screen": [
                    TimeoutError("t1"),
                    TimeoutError("t2"),
                    TimeoutError("t3"),
                ],
                "edit_screens": [TimeoutError("t-edit")],
                "generate_variants": [TimeoutError("t-var")],
            }
        )
        r = await generate_screen_with_fallback(
            ops,
            "p1",
            "Login",
            baseline_screen_id="s_existing",
            max_total_attempts=2,
        )
        assert r.outcome == FallbackOutcome.FAILED
        assert len(r.attempts) <= 2


# ── Batching ───────────────────────────────────────────────────────────


def _spec(name, route="/", order=0, group=None):
    return ScreenSpec(name=name, prompt=f"prompt for {name}", route=route, order=order, group=group)


class TestPartitioning:
    def test_under_batch_size_returns_single_batch(self):
        specs = [_spec(f"s{i}") for i in range(3)]
        batches = partition_screens(specs, batch_size=4)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_above_batch_size_splits(self):
        specs = [_spec(f"s{i}", order=i) for i in range(10)]
        batches = partition_screens(specs, batch_size=4)
        assert all(len(b) <= 4 for b in batches)
        flat = [s.name for b in batches for s in b]
        assert sorted(flat) == sorted(s.name for s in specs)

    def test_explicit_group_keeps_screens_together(self):
        specs = [
            _spec("a1", group="admin"),
            _spec("a2", group="admin"),
            _spec("p1", group="public"),
            _spec("p2", group="public"),
            _spec("p3", group="public"),
            _spec("p4", group="public"),
            _spec("p5", group="public"),
        ]
        batches = partition_screens(specs, batch_size=4)
        # admin batch is its own; public splits into ≤4 chunks
        admin_batch = next(b for b in batches if b[0].name.startswith("a"))
        assert {s.name for s in admin_batch} == {"a1", "a2"}

    def test_route_prefix_groups_when_no_explicit_group(self):
        specs = [
            _spec("a1", route="/admin/list"),
            _spec("a2", route="/admin/detail"),
            _spec("p1", route="/public/home"),
            _spec("p2", route="/public/about"),
            _spec("p3", route="/public/contact"),
            _spec("p4", route="/public/pricing"),
            _spec("p5", route="/public/blog"),
            _spec("p6", route="/public/faq"),
        ]
        batches = partition_screens(specs, batch_size=4)
        admin_batch = next(b for b in batches if b[0].name.startswith("a"))
        assert {s.name for s in admin_batch} == {"a1", "a2"}

    def test_invalid_batch_size_raises(self):
        with pytest.raises(ValueError):
            partition_screens([_spec("x")], batch_size=0)


class TestPlanBuild:
    def test_no_unified_pass_when_under_threshold(self):
        specs = [_spec(f"s{i}") for i in range(3)]
        plan = plan_build(specs, batch_size=4, apply_unified_theme_pass=True)
        assert plan.unified_pass_planned is False

    def test_unified_pass_when_above_threshold(self):
        specs = [_spec(f"s{i}") for i in range(8)]
        plan = plan_build(specs, batch_size=4, apply_unified_theme_pass=True)
        assert plan.unified_pass_planned is True

    def test_unified_pass_disabled_when_flag_off(self):
        specs = [_spec(f"s{i}") for i in range(8)]
        plan = plan_build(specs, batch_size=4, apply_unified_theme_pass=False)
        assert plan.unified_pass_planned is False


# ── build_site_batched end-to-end with mock ────────────────────────────


class TestBuildSiteBatchedIntegration:
    @pytest.mark.asyncio
    async def test_single_batch_no_unified_pass(self):
        specs = [_spec(f"s{i}") for i in range(3)]
        ops = FakeOps(
            {
                "build_site": [{"site_id": "site-1"}],
                "edit_screens": [],  # never called
            }
        )
        out = await build_site_batched(ops, "p1", specs, batch_size=4)
        assert out["total_screens"] == 3
        assert out["total_batches"] == 1
        assert out["unified_pass_applied"] is False
        assert out["batches"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_multiple_batches_apply_unified_pass(self):
        specs = [_spec(f"s{i}", order=i) for i in range(8)]
        ops = FakeOps(
            {
                "build_site": [
                    {"site_id": "batch-1"},
                    {"site_id": "batch-2"},
                ],
                "edit_screens": [{"ok": True}] * 8,
            }
        )
        out = await build_site_batched(ops, "p1", specs, batch_size=4)
        assert out["total_batches"] == 2
        assert out["unified_pass_applied"] is True
        assert len(out["unified_pass"]) == 8

    @pytest.mark.asyncio
    async def test_failed_batch_recorded_but_does_not_abort(self):
        specs = [_spec(f"s{i}", order=i) for i in range(8)]
        ops = FakeOps(
            {
                "build_site": [
                    RuntimeError("502 Bad Gateway"),
                    {"site_id": "batch-2"},
                ],
                "edit_screens": [{"ok": True}] * 8,
            }
        )
        out = await build_site_batched(ops, "p1", specs, batch_size=4)
        statuses = [b["status"] for b in out["batches"]]
        assert "error" in statuses
        assert "ok" in statuses
        # Unified pass still ran for screens of the successful batch.
        assert out["unified_pass_applied"] is True
