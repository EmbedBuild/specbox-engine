"""Normalize a FreeForm *exploded* source into the canonical ``items.json`` array (UC-709).

Some repos keep their FreeForm tracking as a **nested ``index.json``** plus
*exploded* per-item markdown (``us/US-XX_*.md`` / ``uc/UC-XXX_*.md`` with the
acceptance criteria as ``- [x]`` checkboxes inside the markdown body), instead
of the flat ``items.json`` array that :class:`FreeformBackend` memory-mode and
``switch_project_backend`` consume. Migrating such a repo to Native failed at
the preview step with ``items_content must be a JSON array ... got dict`` — the
nested ``index.json`` is a ``dict``, not the flat ``list`` the migration path
expects (UC-709, discovered dogfooding ``Dental-Data/DDBoss-Web-Saas``).

This module is the bridge: a **pure, I/O-free** transform from the nested
``index.json`` shape

    {"user_stories": [
        {"us_id": "US-01", "name": "...", "status": "...", "hours": 200,
         "ac_total": 55, "ac_done": 54,
         "use_cases": [
            {"uc_id": "UC-001", "name": "...", "status": "review",
             "ac_total": 7, "ac_done": 7}, ...]}, ...]}

into the flat ``items.json`` array of US/UC/AC items the rest of the pipeline
already understands (``labels`` ``["US"]``/``["UC"]``/``["AC"]``, ``parent_id``,
``meta`` carrying ``us_id``/``uc_id``/``ac_id``).

**Acceptance-criteria caveat (documented degradation).** The AC *texts* live in
the markdown bodies, NOT in ``index.json``. A pure transform of ``index.json``
alone cannot recover them. Two modes:

- **Faithful** — the caller passes ``ac_texts`` (a ``{uc_id: [text, ...]}`` map
  it extracted from the markdown checkboxes). Each AC becomes a real item with
  its text and a ``done`` state derived from the checkbox.
- **Degraded** — no ``ac_texts``. We synthesize ``ac_total`` placeholder AC
  items per UC (``AC-01..AC-NN``) with a placeholder text and mark the first
  ``ac_done`` of them ``done`` (the index only carries counts, not which ones).
  The COUNTS round-trip exactly (so the count guard passes) but the AC texts are
  placeholders. The result flags ``ac_degraded=True`` so the skill can warn.

The function never raises on a well-formed nested dict; it raises
``ValueError`` only when the input is neither the nested shape nor already the
flat array.
"""

from __future__ import annotations

import json
from typing import Any


def looks_like_exploded(parsed: Any) -> bool:
    """True if ``parsed`` is the nested FreeForm dict (has ``user_stories``)."""
    return isinstance(parsed, dict) and isinstance(parsed.get("user_stories"), list)


def is_flat_items(parsed: Any) -> bool:
    """True if ``parsed`` is already the flat ``items.json`` array."""
    return isinstance(parsed, list)


def _ac_state(done: bool) -> str:
    return "done" if done else "backlog"


def normalize_exploded_index(
    index: dict[str, Any],
    ac_texts: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Convert a nested ``index.json`` dict into the flat items.json array.

    Args:
        index: The parsed ``index.json`` (``{"user_stories": [...]}``).
        ac_texts: Optional ``{uc_id: [text, ...]}`` extracted from the markdown
            checkboxes. When given, AC items carry real texts + done state.
            When omitted, AC items are synthesized from ``ac_total`` counts
            (degraded — texts are placeholders).

    Returns:
        ``{"items": [...], "counts": {"us","uc","ac"}, "ac_degraded": bool}``.
        ``items`` is the flat array ready to be ``json.dumps``-ed and passed as
        ``source_content`` / chunked for batch ingest.

    Raises:
        ValueError: if ``index`` is not the nested shape.
    """
    if not looks_like_exploded(index):
        raise ValueError(
            "normalize_exploded_index expects the nested FreeForm shape "
            '{"user_stories": [...]}, got '
            f"{type(index).__name__}"
            + (
                " with keys " + ", ".join(sorted(index.keys()))
                if isinstance(index, dict)
                else ""
            )
        )

    ac_texts = ac_texts or {}
    items: list[dict[str, Any]] = []
    n_us = n_uc = n_ac = 0
    ac_degraded = False

    for us in index["user_stories"]:
        us_id = us.get("us_id") or us.get("id") or ""
        us_name = us.get("name", "")
        us_status = us.get("status", "user_stories")
        items.append(
            {
                "id": us_id,
                "name": f"{us_id}: {us_name}" if us_name else us_id,
                "state": us_status,
                "labels": ["US"],
                "parent_id": None,
                "meta": {
                    "tipo": "US",
                    "us_id": us_id,
                    "horas": us.get("hours", ""),
                    # keep traceability fields the index carries
                    **({"adr": us["adr"]} if us.get("adr") else {}),
                },
            }
        )
        n_us += 1

        for uc in us.get("use_cases", []):
            uc_id = uc.get("uc_id") or uc.get("id") or ""
            uc_name = uc.get("name", "")
            uc_status = uc.get("status", "backlog")
            items.append(
                {
                    "id": uc_id,
                    "name": f"{uc_id}: {uc_name}" if uc_name else uc_id,
                    "state": uc_status,
                    "labels": ["UC"],
                    "parent_id": us_id,
                    "meta": {
                        "tipo": "UC",
                        "uc_id": uc_id,
                        "us_id": us_id,
                        "horas": uc.get("hours", ""),
                    },
                }
            )
            n_uc += 1

            texts = ac_texts.get(uc_id)
            if texts is not None:
                # Faithful: one AC item per extracted checkbox.
                for idx, entry in enumerate(texts, 1):
                    text, done = _coerce_ac_entry(entry)
                    ac_id = f"AC-{idx:02d}"
                    items.append(_ac_item(uc_id, us_id, ac_id, text, done))
                    n_ac += 1
            else:
                # Degraded: synthesize from ac_total / ac_done counts.
                ac_total = int(uc.get("ac_total", 0) or 0)
                ac_done = int(uc.get("ac_done", 0) or 0)
                if ac_total:
                    ac_degraded = True
                for idx in range(1, ac_total + 1):
                    ac_id = f"AC-{idx:02d}"
                    done = idx <= ac_done
                    items.append(
                        _ac_item(
                            uc_id,
                            us_id,
                            ac_id,
                            f"[AC text not in index.json — see {uc_id} markdown]",
                            done,
                        )
                    )
                    n_ac += 1

    return {
        "items": items,
        "counts": {"us": n_us, "uc": n_uc, "ac": n_ac},
        "ac_degraded": ac_degraded,
    }


def _coerce_ac_entry(entry: Any) -> tuple[str, bool]:
    """Accept either a plain ``str`` (pending) or ``{"text","done"}`` dict."""
    if isinstance(entry, dict):
        return str(entry.get("text", "")), bool(entry.get("done", False))
    return str(entry), False


def _ac_item(uc_id: str, us_id: str, ac_id: str, text: str, done: bool) -> dict[str, Any]:
    return {
        "id": f"{uc_id}::{ac_id}",
        "name": f"{ac_id}: {text}" if text else ac_id,
        "state": _ac_state(done),
        "labels": ["AC"],
        "parent_id": uc_id,
        "meta": {"tipo": "AC", "ac_id": ac_id, "uc_id": uc_id, "us_id": us_id},
    }


def normalize_source_content(
    source_content: str,
    ac_texts: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Parse + normalize a freeform ``source_content`` string into flat items.

    Detects the dialect:

    - already a flat array → returned as-is (``converted=False``).
    - nested ``index.json`` dict → converted (``converted=True``).
    - anything else → ``ValueError``.

    Returns ``{"items_content": str, "counts": {...}, "converted": bool,
    "ac_degraded": bool}`` where ``items_content`` is the flat JSON string ready
    to feed the migration path.
    """
    parsed = json.loads(source_content)
    if is_flat_items(parsed):
        n_us = sum(1 for i in parsed if "US" in i.get("labels", []))
        n_uc = sum(1 for i in parsed if "UC" in i.get("labels", []))
        n_ac = sum(1 for i in parsed if "AC" in i.get("labels", []))
        return {
            "items_content": source_content,
            "counts": {"us": n_us, "uc": n_uc, "ac": n_ac},
            "converted": False,
            "ac_degraded": False,
        }
    if looks_like_exploded(parsed):
        result = normalize_exploded_index(parsed, ac_texts)
        return {
            "items_content": json.dumps(result["items"], ensure_ascii=False),
            "counts": result["counts"],
            "converted": True,
            "ac_degraded": result["ac_degraded"],
        }
    raise ValueError(
        "source_content is neither a flat items.json array nor a nested "
        'FreeForm index.json ({"user_stories": [...]}); got '
        f"{type(parsed).__name__}"
    )
