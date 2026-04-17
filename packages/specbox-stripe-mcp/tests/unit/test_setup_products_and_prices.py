"""Unit tests for T3 setup_products_and_prices.

Covers AC-01..AC-07 of UC-3.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from specbox_stripe_mcp.tools.setup_products_and_prices import setup_products_and_prices

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"

CATALOG_3 = [
    {"tier_key": "bronce", "product_name": "Sponsor Bronce", "unit_amount": 500, "currency": "eur"},
    {"tier_key": "plata",  "product_name": "Sponsor Plata",  "unit_amount": 700, "currency": "eur"},
    {"tier_key": "oro",    "product_name": "Sponsor Oro",    "unit_amount": 900, "currency": "eur"},
]


class _Listing(dict):
    """Mimics a stripe ListObject."""


def _product(
    *,
    pid: str,
    tier: str,
    name: str = "",
    description: str | None = None,
    active: bool = True,
    managed: bool = True,
) -> dict[str, Any]:
    return {
        "id": pid,
        "name": name or f"Sponsor {tier.capitalize()}",
        "description": description,
        "active": active,
        "metadata": ({"specbox_managed": "true", "tier_key": tier} if managed else {"tier_key": tier}),
    }


def _price(
    *,
    prid: str,
    product: str,
    tier: str,
    unit_amount: int,
    currency: str = "eur",
    interval: str = "month",
    managed: bool = True,
    active: bool = True,
) -> dict[str, Any]:
    return {
        "id": prid,
        "product": product,
        "unit_amount": unit_amount,
        "currency": currency,
        "recurring": {"interval": interval},
        "active": active,
        "metadata": ({"specbox_managed": "true", "tier_key": tier} if managed else {"tier_key": tier}),
    }


@pytest.fixture
def patch_stripe():  # type: ignore[no-untyped-def]
    with patch("stripe.Product.list") as m_plist, patch(
        "stripe.Product.create"
    ) as m_pcreate, patch("stripe.Product.modify") as m_pmodify, patch(
        "stripe.Price.list"
    ) as m_prlist, patch("stripe.Price.create") as m_prcreate, patch(
        "stripe.Price.modify"
    ) as m_prmodify:
        yield m_plist, m_pcreate, m_pmodify, m_prlist, m_prcreate, m_prmodify


class TestAcceptance:
    def test_create_all_when_none_exist(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-01: catalog with 3 new tiers → creates 3 products + 3 prices, all created."""
        m_plist, m_pcreate, _m_pmodify, m_prlist, m_prcreate, _m_prmodify = patch_stripe
        m_plist.return_value = _Listing(data=[])
        m_pcreate.side_effect = [
            _product(pid=f"prod_{t}", tier=t, name=f"Sponsor {t.capitalize()}")
            for t in ("bronce", "plata", "oro")
        ]
        m_prlist.return_value = _Listing(data=[])
        m_prcreate.side_effect = [
            _price(prid=f"price_{t}", product=f"prod_{t}", tier=t,
                   unit_amount=amount)
            for t, amount in [("bronce", 500), ("plata", 700), ("oro", 900)]
        ]

        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=CATALOG_3,
            project_hint="motofan",
        )

        assert out["success"] is True
        data = out["data"]
        assert [p["created_or_reused"] for p in data["products"]] == ["created"] * 3
        assert [p["created_or_reused"] for p in data["prices"]] == ["created"] * 3
        assert data["tier_mapping"]["bronce"]["product_id"] == "prod_bronce"
        assert data["tier_mapping"]["bronce"]["price_id"] == "price_bronce"
        # metadata must carry tier_key + specbox_managed
        for call in m_pcreate.call_args_list:
            md = call.kwargs["metadata"]
            assert md["specbox_managed"] == "true"
            assert "tier_key" in md

    def test_reuse_all_when_products_and_prices_match(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02: re-run with existing matching catalog → all reused, no creates."""
        m_plist, m_pcreate, _m_pmodify, m_prlist, m_prcreate, _m_prmodify = patch_stripe
        m_plist.return_value = _Listing(data=[
            _product(pid=f"prod_{t}", tier=t, name=f"Sponsor {t.capitalize()}")
            for t in ("bronce", "plata", "oro")
        ])
        # Price list per product
        prices_by_product = {
            "prod_bronce": [_price(prid="price_bronce", product="prod_bronce", tier="bronce", unit_amount=500)],
            "prod_plata":  [_price(prid="price_plata",  product="prod_plata",  tier="plata",  unit_amount=700)],
            "prod_oro":    [_price(prid="price_oro",    product="prod_oro",    tier="oro",    unit_amount=900)],
        }
        def fake_price_list(product: str, **_):
            return _Listing(data=prices_by_product.get(product, []))
        m_prlist.side_effect = fake_price_list

        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=CATALOG_3,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert all(p["created_or_reused"] == "reused" for p in out["data"]["products"])
        assert all(p["created_or_reused"] == "reused" for p in out["data"]["prices"])
        m_pcreate.assert_not_called()
        m_prcreate.assert_not_called()

    def test_product_name_update_no_price_create(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: product name changed but price shape unchanged → product updated, price reused."""
        m_plist, m_pcreate, m_pmodify, m_prlist, m_prcreate, _m_prmodify = patch_stripe
        m_plist.return_value = _Listing(data=[
            _product(pid="prod_bronce", tier="bronce", name="Old Name", description="old"),
        ])
        m_pmodify.return_value = _product(
            pid="prod_bronce", tier="bronce", name="Sponsor Bronce",
        )
        m_prlist.return_value = _Listing(
            data=[_price(prid="price_bronce", product="prod_bronce",
                         tier="bronce", unit_amount=500)]
        )

        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=[CATALOG_3[0]],
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["products"][0]["created_or_reused"] == "updated"
        assert out["data"]["prices"][0]["created_or_reused"] == "reused"
        m_pcreate.assert_not_called()
        m_prcreate.assert_not_called()

    def test_price_amount_changed_creates_new_and_archives_old(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-04: unit_amount change → new price + old one archived with active=false."""
        m_plist, _m_pcreate, _m_pmodify, m_prlist, m_prcreate, m_prmodify = patch_stripe
        m_plist.return_value = _Listing(data=[
            _product(pid="prod_bronce", tier="bronce", name="Sponsor Bronce"),
        ])
        m_prlist.return_value = _Listing(
            data=[_price(prid="price_old", product="prod_bronce",
                         tier="bronce", unit_amount=500)]
        )
        m_prcreate.return_value = _price(
            prid="price_new", product="prod_bronce", tier="bronce",
            unit_amount=999,
        )

        changed_catalog = [
            {**CATALOG_3[0], "unit_amount": 999},
        ]
        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=changed_catalog,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["prices"][0]["created_or_reused"] == "created"
        assert out["data"]["prices"][0]["id"] == "price_new"
        # old price archived via modify(price_old, active=False)
        archive_calls = [c for c in m_prmodify.call_args_list
                         if c.kwargs.get("active") is False]
        assert any(c.args[0] == "price_old" for c in archive_calls)

    def test_archive_unmanaged_tiers_removes_extra_products(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05: tier no longer in catalog + archive_unmanaged_tiers=true → archived."""
        m_plist, _m_pcreate, m_pmodify, m_prlist, _m_prcreate, _m_prmodify = patch_stripe
        # Existing: bronce + platino (removed in new catalog)
        m_plist.return_value = _Listing(data=[
            _product(pid="prod_bronce", tier="bronce", name="Sponsor Bronce"),
            _product(pid="prod_platino", tier="platino", name="Sponsor Platino"),
        ])
        m_prlist.return_value = _Listing(
            data=[_price(prid="price_bronce", product="prod_bronce",
                         tier="bronce", unit_amount=500)]
        )
        m_pmodify.return_value = _product(pid="prod_platino", tier="platino", active=False)

        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=[CATALOG_3[0]],
            archive_unmanaged_tiers=True,
            project_hint="motofan",
        )

        assert out["success"] is True
        archived_tiers = {a["tier_key"] for a in out["data"]["archived"]}
        assert "platino" in archived_tiers

    def test_duplicate_tier_key_rejected(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-06: catalog with 2 items same tier_key → E_DUPLICATE_TIER_KEY, zero Stripe calls."""
        m_plist, m_pcreate, *_ = patch_stripe

        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=[
                {"tier_key": "bronce", "product_name": "A", "unit_amount": 500, "currency": "eur"},
                {"tier_key": "bronce", "product_name": "B", "unit_amount": 600, "currency": "eur"},
            ],
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_DUPLICATE_TIER_KEY"
        m_plist.assert_not_called()
        m_pcreate.assert_not_called()

    def test_heartbeat_idempotency_hit_when_all_reused(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-07: full reuse → heartbeat.idempotency_hit=true + engram observation written."""
        m_plist, _m_pcreate, _m_pmodify, m_prlist, _m_prcreate, _m_prmodify = patch_stripe
        m_plist.return_value = _Listing(data=[
            _product(pid="prod_bronce", tier="bronce", name="Sponsor Bronce"),
        ])
        m_prlist.return_value = _Listing(
            data=[_price(prid="price_bronce", product="prod_bronce",
                         tier="bronce", unit_amount=500)]
        )

        captured_hb: list[dict[str, Any]] = []

        def fake_hb(*, project: str, event_type: str, payload: dict) -> None:
            captured_hb.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.setup_products_and_prices.report_heartbeat",
            side_effect=fake_hb,
        ), patch(
            "specbox_stripe_mcp.tools.setup_products_and_prices.write_config_observation",
            return_value="obs_xyz",
        ):
            out = setup_products_and_prices(
                stripe_api_key=TEST_KEY,
                catalog=[CATALOG_3[0]],
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["evidence"]["engram_observation_id"] == "obs_xyz"
        assert captured_hb[-1]["idempotency_hit"] is True
