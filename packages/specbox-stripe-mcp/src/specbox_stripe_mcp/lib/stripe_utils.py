"""Stripe SDK object → plain dict normalization.

The Stripe Python SDK returns instances of ``stripe.StripeObject`` for every
API response. That class implements ``__getattr__`` to expose fields as
attributes, which in Python 3.14 collides with dict-style method lookups like
``.get(...)``. Accessing ``stripe_object.get("key", default)`` on some Python
versions raises ``AttributeError: get`` because ``__getattr__`` treats ``get``
as a data field.

The robust path is to convert the StripeObject (and any nested StripeObjects)
to a plain ``dict`` once, at the boundary of each tool, and then operate on
plain dicts from there on.

Detected in moto.fan integration 2026-04-18, Python 3.14.3, stripe SDK 7.x.
Account acct_1TGSBuRjinbf6Ah6.
"""

from __future__ import annotations

from typing import Any


def as_dict(obj: Any) -> dict[str, Any]:
    """Return a plain ``dict`` representation of a Stripe API response object.

    Strategy, in order:
      1. If the object exposes ``to_dict_recursive()`` (every StripeObject does
         in SDK >=5), use it — this recursively converts nested StripeObjects.
      2. Else try ``dict(obj)`` for mapping-like inputs.
      3. Else return ``{}``.

    Never raises.
    """
    if obj is None:
        return {}
    to_dict_recursive = getattr(obj, "to_dict_recursive", None)
    if callable(to_dict_recursive):
        try:
            result = to_dict_recursive()
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    try:
        result = dict(obj)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


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
