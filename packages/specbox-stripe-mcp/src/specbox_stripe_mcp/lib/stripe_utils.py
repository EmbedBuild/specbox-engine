"""Stripe SDK object → plain dict normalization.

The Stripe Python SDK returns instances of ``stripe.StripeObject`` for every
API response. That class implements ``__getattr__`` to expose fields as
attributes, which in Python 3.14 collides with dict-style method lookups like
``.get(...)``. Accessing ``stripe_object.get("key", default)`` on some Python
versions raises ``AttributeError: get`` because ``__getattr__`` treats ``get``
as a data field. Likewise, ``dict(stripe_object)`` returns ``{}`` on
Python 3.14 because StripeObject isn't mapping-like in the strict sense.

The robust path is to convert the StripeObject (and any nested StripeObjects)
to a plain ``dict`` once, at the boundary of each tool, and then operate on
plain dicts from there on.

Two SDK serialization methods coexist in the wild:
  - ``to_dict()`` — stripe SDK 7.x and newer (the canonical one today).
  - ``to_dict_recursive()`` — stripe SDK <=5 legacy. Some objects in older
    SDKs exposed only this; not present in 7.x.

We try ``to_dict()`` first because that's what every supported Python /
SDK combination returns today. ``to_dict_recursive()`` is the fallback for
projects pinned to legacy SDKs.

History:
  2026-04-18: ``as_dict()`` introduced after moto.fan integration broke on
              Python 3.14.3 + stripe SDK 7.x because direct ``.get(...)`` on
              StripeObject raised AttributeError. That fix only added
              ``to_dict_recursive()`` (assumed it was universal). It was not.
  2026-04-29: regression discovered. setup_products_and_prices crashed with
              ``KeyError: 'id'`` against a real sk_test account because
              ``as_dict()`` returned ``{}`` after every successful API call —
              ``to_dict_recursive`` doesn't exist in SDK 7 and ``dict(obj)``
              returned empty. Added ``to_dict()`` as the primary path.
              See tests/unit/test_stripe_object_sdk7.py for the regression
              suite. Account acct_1TGjUPCGmD421eNs.
"""

from __future__ import annotations

from typing import Any


def as_dict(obj: Any) -> dict[str, Any]:
    """Return a plain ``dict`` representation of a Stripe API response object.

    Strategy, in order:
      1. ``obj.to_dict()`` — stripe SDK 7+ canonical serialization.
      2. ``obj.to_dict_recursive()`` — legacy SDK <=5 serialization.
      3. ``dict(obj)`` — generic mapping-like fallback.
      4. ``{}`` — give up gracefully.

    Always returns a non-None dict. Never raises.
    """
    if obj is None:
        return {}

    # If it's already a plain dict, just return it.
    if isinstance(obj, dict):
        return obj

    # SDK 7+ canonical path.
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, dict):
                # Recursively normalize nested StripeObjects in case to_dict()
                # left them un-normalized.
                return _normalize_nested(result)
        except Exception:
            pass

    # Legacy SDK <=5 path (kept for backward compat).
    to_dict_recursive = getattr(obj, "to_dict_recursive", None)
    if callable(to_dict_recursive):
        try:
            result = to_dict_recursive()
            if isinstance(result, dict):
                return result
        except Exception:
            pass

    # Mapping-like fallback (older SDKs sometimes work this way).
    try:
        result = dict(obj)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _normalize_nested(d: dict[str, Any]) -> dict[str, Any]:
    """Walk a dict and replace any nested StripeObject-like values with their
    ``to_dict()`` form. SDK 7's ``to_dict()`` is non-recursive on some object
    types, so a top-level ``{"data": [<StripeObject>, ...]}`` can leak.
    """
    out: dict[str, Any] = {}
    for k, v in d.items():
        out[k] = _normalize_value(v)
    return out


def _normalize_value(v: Any) -> Any:
    if isinstance(v, dict):
        return _normalize_nested(v)
    if isinstance(v, list):
        return [_normalize_value(item) for item in v]
    # Detect non-dict objects that look like StripeObjects.
    if hasattr(v, "to_dict") and callable(v.to_dict):
        try:
            inner = v.to_dict()
            if isinstance(inner, dict):
                return _normalize_nested(inner)
        except Exception:
            pass
    if hasattr(v, "to_dict_recursive") and callable(v.to_dict_recursive):
        try:
            inner = v.to_dict_recursive()
            if isinstance(inner, dict):
                return inner
        except Exception:
            pass
    return v


def as_dict_list(items: Any) -> list[dict[str, Any]]:
    """Convert a Stripe ListObject (or any iterable of StripeObjects) into a
    list of plain dicts.

    Handles three common shapes:
      - ``ListObject`` with ``.data`` attribute / key
      - iterable of StripeObjects
      - None / unexpected shape → empty list
    """
    if items is None:
        return []
    # Prefer the canonical ListObject shape: {.data: [...]}
    data = getattr(items, "data", None)
    if data is None and isinstance(items, dict):
        data = items.get("data")
    if data is None:
        # Maybe it's directly iterable
        try:
            iterator = iter(items)
        except TypeError:
            return []
        return [as_dict(item) for item in iterator]
    try:
        return [as_dict(item) for item in data]
    except TypeError:
        return []
