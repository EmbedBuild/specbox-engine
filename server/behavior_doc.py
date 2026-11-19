"""El documento de comportamiento de una funcionalidad y el PRD superado (US-126 · UC-12605).

Los PRD cuentan cada cambio; ninguno dice lo que el sistema hace hoy. ``doc/spec/<funcionalidad>.md``
lo dice: una sección por historia con los criterios de sus UC cerradas, que se regenera desde el
tablero al cerrar cada UC.

* ``complete_uc(with_behavior_doc=True)`` devuelve ``behavior_doc``: la sección de la historia de la
  UC (``section``) y las historias con todas sus UC cerradas (``complete_stories``). El MCP remoto no
  escribe en el disco del cliente: lo escribe el hook ``app-docs-fragment`` en el repositorio que
  guarda el canon (el orquestador en multirepo), junto al PRD de la historia.
* Con FreeForm por fragmentos el servidor no ve el tablero entero (``render: "client"``): el hook
  calcula lo mismo con su items.json (``.claude/hooks/lib/behavior-doc.mjs``; una prueba los compara).
* Un PRD cuyas historias tienen todas sus UC cerradas (o archivadas, sustituidas) lleva la marca
  ``<!-- @specbox:prd status="superseded" date="…" by="doc/spec/<f>.md" -->``. Los lectores de PRD
  (``run_acceptance_check``, ``get_e2e_gap_report``, el localizador del PRD de una historia nueva) lo
  dejan fuera. Sin ningún PRD marcado, lo que leen es exactamente lo de antes.

Puro salvo ``behavior_doc_sync``, que lee el tablero.
"""

from __future__ import annotations

import functools
import inspect
import re
from datetime import datetime, timezone
from typing import Any

SPEC_DIR = "doc/spec"
SUPERSEDED_RE = re.compile(r'<!--\s*@specbox:prd\s+status="superseded"(?:\s+date="([^"]*)")?(?:\s+by="([^"]*)")?\s*-->')
FORMAT_MARK_RE = re.compile(r'^\s*<!--\s*@specbox:prd\s+format="\d+"\s*-->\s*$')
FILE_MARK_RE = re.compile(r'^<!--\s*@specbox:file\s+path="([^"]*)"\s*-->\s*$')
_US_ID = re.compile(r"\bUS-\d+[a-z]?\b")
_UC_NUM = re.compile(r"UC-(\d+)")
_AC_ID = re.compile(r"\bAC-(\d+)\b", re.IGNORECASE)
_UC_PREFIX = re.compile(r"^\[?UC-\d+[a-z]?\]?\s*[:—–-]?\s*")
_US_PREFIX = re.compile(r"^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*")
_AC_PREFIX = re.compile(r"^\[?AC-\d+\]?\s*[:—–-]?\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _uc_order(uc: dict[str, Any]) -> tuple[int, str]:
    m = _UC_NUM.match(uc["uc_id"])
    return (int(m.group(1)) if m else 10**9, uc["uc_id"])


def _ac_id(raw_id: str, text: str) -> str:
    m = _AC_ID.search(raw_id or "") or _AC_ID.match(_clean(text))
    return f"AC-{int(m.group(1)):02d}" if m else _clean(raw_id)


def criterion(raw_id: str, text: str, done: bool) -> dict[str, Any]:
    """Un criterio normalizado: ``{ac_id, text, done}`` (el texto sin su «[AC-01]» delante)."""
    return {"ac_id": _ac_id(raw_id, text), "text": _clean(_AC_PREFIX.sub("", _clean(text))), "done": bool(done)}


def section_marks(us_id: str) -> tuple[str, str]:
    return f'<!-- @specbox:spec us="{us_id}" start -->', f'<!-- @specbox:spec us="{us_id}" end -->'


def render_section(story: dict[str, Any], ucs: list[dict[str, Any]]) -> str:
    """La sección de una historia: sus UC cerradas, por número, con sus criterios.

    ``story``: ``{us_id, title}``; ``ucs``: ``[{uc_id, title, criteria: [{ac_id, text, done}]}]``.
    Solo depende del tablero: la misma foto da el mismo texto.
    """
    start, end = section_marks(story["us_id"])
    title = _clean(story.get("title", ""))
    out = [start, f"## {story['us_id']}" + (f" — {title}" if title else ""), ""]
    for uc in sorted(ucs, key=_uc_order):
        uc_title = _clean(uc.get("title", ""))
        out.append(f"### {uc['uc_id']}" + (f": {uc_title}" if uc_title else ""))
        out.append("")
        for ac in sorted(uc.get("criteria") or [], key=lambda a: a["ac_id"]):
            out.append(f"- [{'x' if ac['done'] else ' '}] **{ac['ac_id']}**: {ac['text']}")
        out.append("")
    if not ucs:
        out += ["_(ninguna UC cerrada todavía)_", ""]
    out.append(end)
    return "\n".join(out)


def doc_header(feature: str) -> str:
    return (
        f"# Comportamiento: {feature}\n\n"
        "> Lo que el sistema hace hoy: una sección por historia, con los criterios de sus UC cerradas.\n"
        "> Lo escribe el engine al cerrar cada UC (UC-12605) y se regenera desde el tablero: no lo\n"
        "> edites a mano. Los PRD siguen siendo el historial de cada cambio.\n"
    )


def replace_story_section(doc: str, us_id: str, section: str, feature: str) -> str:
    """El documento con la sección de la historia puesta (sustituida si estaba, añadida si no)."""
    text = doc if doc.strip() else doc_header(feature)
    start, end = section_marks(us_id)
    i = text.find(start)
    j = text.find(end, i) if i >= 0 else -1
    if i >= 0 and j >= 0:
        return text[:i] + section + text[j + len(end):]
    return text.rstrip("\n") + "\n\n" + section + "\n"


def is_superseded(text: str) -> bool:
    return bool(SUPERSEDED_RE.search(text or ""))


def superseded_mark(date: str, by: str) -> str:
    return f'<!-- @specbox:prd status="superseded" date="{date}" by="{by}" -->'


def mark_superseded(prd: str, date: str, by: str) -> str:
    """El PRD con la marca de superado debajo de la de formato (o del título); igual si ya la tiene."""
    if is_superseded(prd):
        return prd
    mark = superseded_mark(date, by)
    lines = prd.split("\n")
    at = next((i for i, line in enumerate(lines) if FORMAT_MARK_RE.match(line)), None)
    if at is None:
        at = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if at is None:
        return mark + "\n" + prd
    return "\n".join([*lines[: at + 1], mark, *lines[at + 1:]])


def prd_stories(prd: str) -> list[str]:
    """Las historias que define un PRD: las que nombran sus encabezados."""
    found: list[str] = []
    for line in (prd or "").splitlines():
        if line.lstrip().startswith("#"):
            for us in _US_ID.findall(line):
                if us not in found:
                    found.append(us)
    return found


# ── Lectores: solo los PRD vigentes ─────────────────────────────────


def split_documents(content: str) -> list[str]:
    """El contenido de varios PRD juntos, partido por documento.

    Por las marcas ``<!-- @specbox:file path="…" -->`` que pone /acceptance-check delante de cada
    fichero; sin ellas, por los títulos ``# …`` (un PRD empieza por el suyo). Sin ninguno, un solo
    documento.
    """
    lines = (content or "").split("\n")
    has_marks = any(FILE_MARK_RE.match(line) for line in lines)
    docs: list[list[str]] = [[]]
    for line in lines:
        starts = FILE_MARK_RE.match(line) if has_marks else line.startswith("# ")
        if starts and any(x.strip() for x in docs[-1]):
            docs.append([])
        docs[-1].append(line)
    return ["\n".join(d) for d in docs]


def current_prd_content(content: str) -> tuple[str, int]:
    """El contenido sin los PRD superados, y cuántos se dejaron fuera.

    Sin ningún PRD superado devuelve el contenido tal cual, byte a byte (AC-05).
    """
    if not is_superseded(content):
        return content, 0
    docs = split_documents(content)
    kept = [d for d in docs if not is_superseded(d)]
    return "\n".join(kept), len(docs) - len(kept)


# ── Lo que devuelve complete_uc ─────────────────────────────────────


def _story_of(items: list[Any], uc_id: str) -> tuple[Any | None, list[Any]]:
    from .spec_backend import parse_item_id

    def ident(item: Any, prefix: str) -> str:
        meta = item.meta or {}
        return (meta.get(f"{prefix.lower()}_id") or parse_item_id(item.name, prefix)[0] or "").upper()

    uc = next((i for i in items if "UC" in i.labels and ident(i, "UC") == uc_id.upper()), None)
    story = next((i for i in items if "US" in i.labels and uc is not None and i.id == uc.parent_id), None)
    if story is None:
        return None, []
    done = [i for i in items if "UC" in i.labels and i.parent_id == story.id and i.state == "done"]
    return story, done


async def behavior_doc_from_backend(backend: Any, board_id: str, uc_id: str) -> dict[str, Any]:
    """La sección de la historia de ``uc_id`` y las historias completas, leídas del tablero."""
    from .app_docs.roadmap import rows_from_items
    from .spec_backend import parse_item_id

    items = await backend.list_board_summary(board_id)
    story, done = _story_of(items, uc_id)
    if story is None:
        return {"ok": False, "error": "story_not_found", "reason": f"No se encontró la historia de {uc_id}."}
    us_id = ((story.meta or {}).get("us_id") or parse_item_id(story.name, "US")[0]).upper()
    ucs = []
    for item in done:
        uc = ((item.meta or {}).get("uc_id") or parse_item_id(item.name, "UC")[0]).upper()
        acs = await backend.get_acceptance_criteria(board_id, item.id)
        ucs.append({
            "uc_id": uc,
            "title": _UC_PREFIX.sub("", _clean(item.name)),
            "criteria": [criterion(ac.id, ac.text, ac.done) for ac in acs],
        })
    story_dict = {"us_id": us_id, "title": _US_PREFIX.sub("", _clean(story.name))}
    complete = [r["us_id"] for r in rows_from_items(items) if r["total"] and r["done"] == r["total"]]
    return {
        "ok": True,
        "us_id": us_id,
        "section": render_section(story_dict, ucs),
        "complete_stories": complete,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "spec_dir": SPEC_DIR,
    }


def _is_fragment(content: str) -> bool:
    import json

    try:
        parsed = json.loads(content or "[]")
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and "format" in parsed


async def behavior_doc_sync(ctx: Any, board_id: str, uc_id: str, items_content: str | None,
                            result: dict[str, Any]) -> dict[str, Any]:
    """El ``behavior_doc`` de ``complete_uc``. Nunca lanza: un fallo va con ``ok: false``."""
    try:
        if items_content is not None:
            content = result.get("items_content") if isinstance(result.get("items_content"), str) else items_content
            if _is_fragment(content):
                return {"ok": True, "render": "client", "spec_dir": SPEC_DIR}
            from .backends.freeform_backend import FreeformBackend

            return await behavior_doc_from_backend(FreeformBackend(items_content=content), board_id, uc_id)
        from .auth_gateway import get_session_backend

        backend = await get_session_backend(ctx)
        try:
            return await behavior_doc_from_backend(backend, board_id, uc_id)
        finally:
            await backend.close()
    except Exception as exc:  # noqa: BLE001 — el documento nunca deshace el cierre
        return {"ok": False, "error": "behavior_doc_failed", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def with_behavior_doc_sync(fn):
    """Tras ``complete_uc``, ``behavior_doc`` con la sección de la historia (UC-12605).

    Solo si la llamada trae ``with_behavior_doc=True``, que pone el hook app-docs-fragment cuando el
    repositorio que guarda el canon está en su rama principal: sin pedirlo, la respuesta queda como
    antes y no gasta contexto. Va por fuera de ``@returns_items_content`` para ver el tablero ya
    cambiado. Nunca cambia el resultado de la tool más allá de añadir ``behavior_doc``, ni lanza.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)
        if not isinstance(result, dict) or result.get("error") or result.get("success") is False:
            return result
        try:
            bound = signature.bind_partial(*args, **kwargs).arguments
            if bound.get("with_behavior_doc") is not True:
                return result
            result["behavior_doc"] = await behavior_doc_sync(
                bound.get("ctx"), str(bound.get("board_id") or ""), str(bound.get("uc_id") or ""),
                bound.get("items_content"), result,
            )
        except Exception as exc:  # noqa: BLE001 — el documento nunca deshace el cierre
            result["behavior_doc"] = {"ok": False, "error": "behavior_doc_failed", "reason": str(exc)[:200]}
        return result

    return wrapper
