"""Regression tests for Python 3.14 StripeObject.get() AttributeError.

Simulates a StripeObject that raises AttributeError on ``.get()`` (the real
behavior observed with stripe SDK under Python 3.14) and verifies every tool
still produces a correct response via the ``as_dict`` normalization.

Detected in moto.fan integration 2026-04-18. Cuenta acct_1TGSBuRjinbf6Ah6.
Pre-fix: tools crashed with "AttributeError: get".
Post-fix: tools normalize via ``lib.stripe_utils.as_dict`` at every boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from specbox_stripe_mcp.lib.stripe_utils import as_dict, as_dict_list
from specbox_stripe_mcp.tools.get_setup_status import get_setup_status
from specbox_stripe_mcp.tools.setup_products_and_prices import setup_products_and_prices
from specbox_stripe_mcp.tools.setup_webhook_endpoints import setup_webhook_endpoints
from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"


class StripeObjectLike:
    """Mimics stripe.StripeObject's Python-3.14 pathology:

    - It behaves like a dict (``[]``, iteration, to_dict_recursive() all work).
    - BUT ``.get(...)`` raises ``AttributeError: get`` because __getattr__
      intercepts attribute lookups that aren't in the underlying dict.

    The pre-fix code called ``.get("x", default)`` directly on this shape,
    which blew up. The fix is to normalize via ``as_dict()`` first, which
    calls ``to_dict_recursive()`` and returns a plain dict.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        # This is what breaks .get() — the real StripeObject re-raises
        # AttributeError from a KeyError when the attribute isn't a data field.
        data = object.__getattribute__(self, "_data")
        if name not in data:
            raise AttributeError(name)
        return _wrap(data[name])

    def __getitem__(self, key: str) -> Any:
        return _wrap(self._data[key])

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def keys(self):  # type: ignore[no-untyped-def]
        return self._data.keys()

    def to_dict_recursive(self) -> dict[str, Any]:
        """Mimics stripe SDK's recursive dict conversion."""
        return _to_plain(self._data)


class StripeListObjectLike:
    """Mimics stripe.ListObject: ``.data`` attribute with nested StripeObjects."""

    def __init__(self, data_items: list[dict[str, Any]]) -> None:
        object.__setattr__(self, "_items", [StripeObjectLike(item) for item in data_items])

    @property
    def data(self) -> list[StripeObjectLike]:
        return self._items

    def to_dict_recursive(self) -> dict[str, Any]:
        return {"data": [item.to_dict_recursive() for item in self._items]}


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return StripeObjectLike(value)
    if isinstance(value, list):
        return [_wrap(v) for v in value]
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


# --- Sanity check of the StripeObjectLike mock itself -----------------------


class TestStripeObjectLikeSanity:
    """Verify that the mock actually reproduces the Python 3.14 bug."""

    def test_get_raises_attribute_error(self) -> None:
        """The mock itself must raise AttributeError on .get — if this test
        ever fails, the regression suite is meaningless."""
        obj = StripeObjectLike({"foo": "bar"})
        with pytest.raises(AttributeError):
            obj.get("foo", "default")  # type: ignore[attr-defined]

    def test_getitem_and_iter_still_work(self) -> None:
        obj = StripeObjectLike({"foo": "bar", "nested": {"x": 1}})
        assert obj["foo"] == "bar"
        assert "foo" in obj
        assert list(obj) == ["foo", "nested"]

    def test_to_dict_recursive_flattens(self) -> None:
        obj = StripeObjectLike({"foo": "bar", "nested": {"x": 1}})
        plain = obj.to_dict_recursive()
        assert isinstance(plain, dict)
        assert plain == {"foo": "bar", "nested": {"x": 1}}
        assert plain.get("foo") == "bar"  # plain dict → .get works


class TestAsDictHelper:
    """Unit tests for the helper itself."""

    def test_stripe_object_normalized(self) -> None:
        obj = StripeObjectLike({"a": 1, "nested": {"b": 2}})
        result = as_dict(obj)
        assert isinstance(result, dict)
        assert result.get("a") == 1
        assert result.get("nested", {}).get("b") == 2

    def test_plain_dict_pass_through(self) -> None:
        assert as_dict({"x": 1}) == {"x": 1}

    def test_none_returns_empty_dict(self) -> None:
        assert as_dict(None) == {}

    def test_list_object_normalized(self) -> None:
        lst = StripeListObjectLike([{"a": 1}, {"a": 2}])
        result = as_dict_list(lst)
        assert len(result) == 2
        assert result[0].get("a") == 1
        assert result[1].get("a") == 2

    def test_empty_list_inputs(self) -> None:
        assert as_dict_list(None) == []
        assert as_dict_list([]) == []

    def test_plain_list_of_dicts(self) -> None:
        result = as_dict_list([{"x": 1}, {"x": 2}])
        assert result == [{"x": 1}, {"x": 2}]


# --- End-to-end: tools must not crash on StripeObjectLike -------------------


class TestT1SurvivesStripeObject:
    def test_verify_connect_enabled_happy_path_with_stripe_object(self) -> None:
        """AC-01 regression: T1 must handle StripeObject Account + probe, not crash."""
        account = StripeObjectLike({
            "id": "acct_1TGSBuRjinbf6Ah6",
            "country": "ES",
            "default_currency": "eur",
            "capabilities": {"card_payments": "active", "transfers": "active"},
            "business_profile": {"name": "Moto.Fan"},
            "email": "owner@motofan.test",
        })
        probe = StripeObjectLike({"id": "acct_PROBE"})

        with patch("stripe.Account.retrieve", return_value=account), \
             patch("stripe.Account.create", return_value=probe), \
             patch("stripe.Account.delete", return_value={"deleted": True}):
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        assert out["data"]["platform_account_id"] == "acct_1TGSBuRjinbf6Ah6"
        assert out["data"]["display_name"] == "Moto.Fan"
        assert "card_payments" in out["data"]["capabilities_available"]

    def test_verify_connect_enabled_connect_disabled_with_stripe_object(self) -> None:
        """AC-02 regression: moto.fan real case — Connect NOT enabled."""
        account = StripeObjectLike({
            "id": "acct_1TGSBuRjinbf6Ah6",
            "country": "ES",
            "default_currency": "eur",
            "capabilities": {},
            "business_profile": {},
            "email": "owner@motofan.test",
        })
        import stripe as _stripe
        with patch("stripe.Account.retrieve", return_value=account), \
             patch("stripe.Account.create", side_effect=_stripe.error.PermissionError(  # type: ignore[attr-defined]
                 "Your account has not activated Connect."
             )):
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        # Pre-fix: crashed with AttributeError. Post-fix: shaped response.
        assert out["success"] is True
        assert out["data"]["enabled"] is False
        assert out["error"]["code"] == "E_CONNECT_NOT_ENABLED"
        assert out["data"]["platform_account_id"] == "acct_1TGSBuRjinbf6Ah6"


class TestT2SurvivesStripeObject:
    def test_setup_webhook_endpoints_list_with_stripe_objects(self) -> None:
        """T2 must handle a ListObject of StripeObjects without crashing."""
        listing = StripeListObjectLike([])  # empty — triggers create path
        created_platform = StripeObjectLike({
            "id": "we_platform",
            "url": "https://x.test/wh",
            "connect": False,
            "enabled_events": ["account.updated"],
            "secret": "whsec_platform_secret",
            "status": "enabled",
            "metadata": {"specbox_managed": "true"},
        })
        created_connect = StripeObjectLike({
            "id": "we_connect",
            "url": "https://x.test/wh",
            "connect": True,
            "enabled_events": ["customer.subscription.created"],
            "secret": "whsec_connect_secret",
            "status": "enabled",
            "metadata": {"specbox_managed": "true"},
        })

        with patch("stripe.WebhookEndpoint.list", return_value=listing), \
             patch("stripe.WebhookEndpoint.create",
                   side_effect=[created_platform, created_connect]):
            out = setup_webhook_endpoints(
                stripe_api_key=TEST_KEY,
                platform_url="https://x.test/wh",
                platform_events=["account.updated"],
                connect_events=["customer.subscription.created"],
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["data"]["platform"]["id"] == "we_platform"
        assert out["data"]["platform"]["secret"] == "whsec_platform_secret"
        assert out["data"]["connect"]["id"] == "we_connect"


class TestT3SurvivesStripeObject:
    def test_setup_products_and_prices_with_stripe_objects(self) -> None:
        """T3 must handle StripeObject products + prices without crashing."""
        products_listing = StripeListObjectLike([])
        prices_listing = StripeListObjectLike([])
        created_product = StripeObjectLike({
            "id": "prod_bronce",
            "name": "Sponsor Bronce",
            "description": None,
            "metadata": {"specbox_managed": "true", "tier_key": "bronce"},
            "active": True,
        })
        created_price = StripeObjectLike({
            "id": "price_bronce",
            "product": "prod_bronce",
            "unit_amount": 500,
            "currency": "eur",
            "recurring": {"interval": "month"},
            "metadata": {"specbox_managed": "true", "tier_key": "bronce"},
            "active": True,
        })

        with patch("stripe.Product.list", return_value=products_listing), \
             patch("stripe.Product.create", return_value=created_product), \
             patch("stripe.Price.list", return_value=prices_listing), \
             patch("stripe.Price.create", return_value=created_price):
            out = setup_products_and_prices(
                stripe_api_key=TEST_KEY,
                catalog=[{
                    "tier_key": "bronce",
                    "product_name": "Sponsor Bronce",
                    "unit_amount": 500,
                    "currency": "eur",
                }],
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["data"]["products"][0]["id"] == "prod_bronce"
        assert out["data"]["prices"][0]["id"] == "price_bronce"


class TestT4SurvivesStripeObject:
    def test_get_setup_status_with_stripe_objects(self) -> None:
        """T4 must handle StripeObject Account + ListObjects without crashing."""
        account = StripeObjectLike({
            "id": "acct_1TGSBuRjinbf6Ah6",
            "country": "ES",
            "capabilities": {"card_payments": "active"},
            "settings": {"dashboard": {"display_name": "Moto.Fan"}},
            "charges_enabled": True,
        })
        webhooks = StripeListObjectLike([
            {
                "id": "we_pf", "url": "https://x.test/wh", "connect": False,
                "enabled_events": ["account.updated"],
                "metadata": {"specbox_managed": "true"},
                "status": "enabled",
            },
            {
                "id": "we_cn", "url": "https://x.test/wh", "connect": True,
                "enabled_events": ["customer.subscription.created"],
                "metadata": {"specbox_managed": "true"},
                "status": "enabled",
            },
        ])

        with patch("stripe.Account.retrieve", return_value=account), \
             patch("stripe.WebhookEndpoint.list", return_value=webhooks):
            out = get_setup_status(
                stripe_api_key=TEST_KEY,
                expected_webhook_url="https://x.test/wh",
                expected_platform_events=["account.updated"],
                expected_connect_events=["customer.subscription.created"],
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["data"]["verdict"] == "ready"
        assert out["data"]["checks"]["platform_webhook_endpoint"]["id"] == "we_pf"
        assert out["data"]["checks"]["connect_webhook_endpoint"]["id"] == "we_cn"


# --- Proof that the pre-fix code would have crashed -------------------------


class TestPreFixCodeWouldHaveCrashed:
    """Negative control: confirms that calling .get() directly on StripeObjectLike
    reproduces the exact Python 3.14 failure mode — so this regression test
    actually catches the bug if someone ever reverts the fix."""

    def test_raw_get_still_raises(self) -> None:
        account = StripeObjectLike({"id": "x", "capabilities": {}})
        with pytest.raises(AttributeError, match="get"):
            _ = account.get("capabilities", {})  # type: ignore[attr-defined]
