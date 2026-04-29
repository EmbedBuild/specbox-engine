"""Regression tests for as_dict() against stripe SDK 7.x objects.

Pathology:
    The original lib/stripe_utils.as_dict() implementation looked for
    ``to_dict_recursive()`` first, falling back to ``dict(obj)``. That worked
    for stripe SDK <=5 where ``to_dict_recursive()`` was the canonical
    serialization method on every StripeObject.

    Stripe SDK 7.x renamed it to ``to_dict()`` (without the ``_recursive``
    suffix). On Python 3.14, ``dict(stripe_object)`` returns an empty ``{}``
    instead of the field map (because StripeObject is not mapping-like the
    way ``dict()`` expects).

    Net effect: every tool in the package received an empty dict from
    ``as_dict()`` after a successful Stripe API call, and crashed with
    ``KeyError: 'id'`` (or similar) on the next ``obj["id"]`` access.

    Detected against real Stripe test account on 2026-04-29 by reproducing
    setup_products_and_prices on a clean account: KeyError 'id' at
    setup_products_and_prices.py:320 inside _reconcile_tier after
    Product.create succeeded.

    Fix: as_dict() now tries ``to_dict()`` (SDK 7+) BEFORE
    ``to_dict_recursive()`` (legacy SDK <=5). Both fall back to ``dict()`` /
    ``{}`` if neither method exists.
"""

from __future__ import annotations

from typing import Any

from specbox_stripe_mcp.lib.stripe_utils import as_dict, as_dict_list


class StripeSdk7Object:
    """Mimics stripe SDK 7.x StripeObject shape.

    Differences from stripe SDK <=5 (StripeObjectLike in the sibling test file):
      - Has ``to_dict()`` (not ``to_dict_recursive``).
      - ``dict(obj)`` returns ``{}`` (the type is iterable but not a mapping).
      - Attribute access on data fields works via __getattr__.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def to_dict(self) -> dict[str, Any]:
        """SDK 7.x serialization method."""
        out: dict[str, Any] = {}
        for k, v in self._data.items():
            if isinstance(v, StripeSdk7Object):
                out[k] = v.to_dict()
            elif isinstance(v, list):
                out[k] = [
                    item.to_dict() if isinstance(item, StripeSdk7Object) else item
                    for item in v
                ]
            else:
                out[k] = v
        return out

    def __getattr__(self, name: str) -> Any:
        data = object.__getattribute__(self, "_data")
        if name not in data:
            raise AttributeError(name)
        return data[name]

    def __iter__(self):  # type: ignore[no-untyped-def]
        # Iterating returns keys, like SDK 7.x StripeObject.
        return iter(self._data)


# --- Sanity checks ----------------------------------------------------------


class TestSdk7MockSanity:
    def test_to_dict_recursive_does_not_exist(self) -> None:
        """Confirm the mock does NOT have to_dict_recursive — that's the whole point."""
        obj = StripeSdk7Object({"id": "prod_X", "name": "X"})
        assert not hasattr(obj, "to_dict_recursive")

    def test_to_dict_returns_field_map(self) -> None:
        obj = StripeSdk7Object({"id": "prod_X", "name": "X"})
        d = obj.to_dict()
        assert d == {"id": "prod_X", "name": "X"}

    def test_dict_constructor_is_not_useful(self) -> None:
        """dict(stripe_sdk7_obj) does not return the field map — this is the bug.

        On a SDK 7.x StripeObject, dict(obj) iterates the keys and tries to pair
        them with values. Our mock replicates that — iterating returns keys but
        without value lookup. The pre-fix code reached this branch and got {}.
        """
        obj = StripeSdk7Object({"id": "prod_X", "name": "X"})
        try:
            result = dict(obj)
        except (TypeError, ValueError):
            return  # Acceptable shape — also caught by as_dict.
        # If dict() does succeed, it should NOT contain the data fields
        # (it would only succeed if the object is genuinely mapping-like).
        assert "id" not in result or result == {}, (
            "If dict() succeeded, it must be empty — otherwise the SDK 7 mock "
            "is wrong. The whole point of this test is the SDK 7 KeyError bug."
        )


# --- Regression tests for as_dict() ------------------------------------------


class TestAsDictAgainstSdk7Object:
    def test_as_dict_extracts_id_from_to_dict(self) -> None:
        """REGRESSION: this is exactly the failing path that produced KeyError 'id'
        in setup_products_and_prices.py:320 against a real Stripe sk_test account.
        """
        product_raw = StripeSdk7Object(
            {
                "id": "prod_UQJijff3TyUq49",
                "name": "Debug Basic",
                "active": True,
                "metadata": {"specbox_managed": "true", "tier_key": "debug_basic"},
            }
        )
        d = as_dict(product_raw)
        assert isinstance(d, dict)
        assert d.get("id") == "prod_UQJijff3TyUq49", (
            f"as_dict() must extract id from to_dict() (SDK 7+); "
            f"got d={d!r}"
        )
        assert d.get("name") == "Debug Basic"

    def test_as_dict_handles_nested_objects(self) -> None:
        nested = StripeSdk7Object({"key": "metadata-value"})
        outer = StripeSdk7Object({"id": "prod_X", "metadata": nested})
        d = as_dict(outer)
        assert d["id"] == "prod_X"
        assert d["metadata"] == {"key": "metadata-value"}

    def test_as_dict_list_against_sdk7_list_object(self) -> None:
        """ListObject in SDK 7.x has .data with StripeObjects inside."""
        listing = StripeSdk7Object(
            {
                "object": "list",
                "data": [
                    StripeSdk7Object({"id": "prod_A", "name": "A"}),
                    StripeSdk7Object({"id": "prod_B", "name": "B"}),
                ],
                "has_more": False,
            }
        )
        items = as_dict_list(listing)
        assert len(items) == 2
        assert items[0]["id"] == "prod_A"
        assert items[1]["id"] == "prod_B"


# --- Backward-compat with the SDK <=5 path ----------------------------------


class StripeSdk5ObjectLike:
    """Older SDK shape: has to_dict_recursive(), no to_dict()."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict_recursive(self) -> dict[str, Any]:
        return dict(self._data)


class TestAsDictBackwardCompat:
    def test_legacy_to_dict_recursive_still_works(self) -> None:
        obj = StripeSdk5ObjectLike({"id": "prod_LEGACY", "name": "Old"})
        d = as_dict(obj)
        assert d.get("id") == "prod_LEGACY"

    def test_plain_dict_pass_through(self) -> None:
        d = as_dict({"id": "prod_X"})
        assert d == {"id": "prod_X"}

    def test_none_returns_empty(self) -> None:
        assert as_dict(None) == {}

    def test_unrecognizable_object_returns_empty(self) -> None:
        class Random:
            pass

        assert as_dict(Random()) == {}
