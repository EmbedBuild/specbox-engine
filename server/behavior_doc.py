"""El documento de comportamiento de una funcionalidad y el PRD superado (US-126 · UC-12605).

Los PRD cuentan cada cambio; ninguno dice lo que el sistema hace hoy. ``doc/spec/<funcionalidad>.md``
lo dice: una sección por historia con los criterios de sus UC cerradas, que se regenera desde el
tablero al cerrar cada UC.

* ``complete_uc``, ``move_uc`` y ``add_uc`` con ``with_behavior_doc=True`` devuelven ``behavior_doc``:
  la sección de la historia de la UC (``section``), la de cada historia de ``behavior_doc_us_ids``
  (``sections``, las que define el PRD, hasta 20) y las historias sin nada pendiente
  (``complete_stories``). El MCP remoto no escribe en el disco del cliente: lo escribe el hook
  ``app-docs-fragment`` en el repositorio que guarda el canon (el orquestador en multirepo), junto al
  PRD de la historia.
* Con FreeForm por fragmentos el servidor no ve el tablero entero (``render: "client"``): el hook
  calcula lo mismo con su items.json (``.claude/hooks/lib/behavior-doc.mjs``); con el items.json
  entero, el servidor usa las mismas reglas que el hook (una prueba los compara).
* Un PRD cuyas historias están todas sin nada pendiente, y cuyo documento tiene recién escrita la
  sección de cada una, lleva en su cabecera la marca
  ``<!-- @specbox:prd status="superseded" date="…" by="doc/spec/<f>.md" -->``; si una de sus
  historias vuelve a tener trabajo, el hook se la quita. Solo cuenta como línea propia de la
  cabecera (antes del primer subtítulo y fuera de bloques de código). ``run_acceptance_check`` y
  ``get_e2e_gap_report`` dejan fuera los PRD superados; sin ninguno, leen exactamente lo de antes.

Puro salvo ``behavior_doc_sync``, que lee el tablero.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

SPEC_DIR = "doc/spec"
MAX_STORIES = 20
#: La marca de superado, como línea propia.
SUPERSEDED_RE = re.compile(
    r'^\s*<!--\s*@specbox:prd\s+status="superseded"(?:\s+date="([^"]*)")?(?:\s+by="([^"]*)")?\s*-->\s*$'
)
FORMAT_MARK_RE = re.compile(r'^\s*<!--\s*@specbox:prd\s+format="\d+"\s*-->\s*$')
#: Cualquier marca de PRD (formato, superado…) como línea propia.
PRD_MARK_RE = re.compile(r"^\s*<!--\s*@specbox:prd\b[^>]*-->\s*$")
FILE_MARK_RE = re.compile(r'^<!--\s*@specbox:file\s+path="([^"]*)"\s*-->\s*$')
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_SUBHEADING_RE = re.compile(r"^#{2,6}(\s|$)")
_DEFINING_RE = re.compile(r"^\s*[#>]")
_US_ID = re.compile(r"\bUS-\d+[a-z]?\b")
_US_ONLY = re.compile(r"^US-\d+[A-Z]?$")
_UC_NUM = re.compile(r"UC-(\d+)")
_AC_ID = re.compile(r"\bAC-(\d+)\b", re.IGNORECASE)
_UC_PREFIX = re.compile(r"^\[?UC-\d+[a-z]?\]?\s*[:—–-]?\s*")
_US_PREFIX = re.compile(r"^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*")
_AC_PREFIX = re.compile(r"^\[?AC-\d+\]?\s*[:—–-]?\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _safe(text: str) -> str:
    """Texto del tablero sin ``<!--`` ni ``-->``: un criterio no puede abrir ni cerrar una marca."""
    return text.replace("<!--", "&lt;!--").replace("-->", "--&gt;")


def _attr(value: str) -> str:
    """Un valor que va dentro de una marca, sin comillas ni ángulos."""
    return re.sub(r'["<>]', "", str(value or ""))


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
    title = _safe(_clean(story.get("title", "")))
    out = [start, f"## {story['us_id']}" + (f" — {title}" if title else ""), ""]
    for uc in sorted(ucs, key=_uc_order):
        uc_title = _safe(_clean(uc.get("title", "")))
        out.append(f"### {uc['uc_id']}" + (f": {uc_title}" if uc_title else ""))
        out.append("")
        for ac in sorted(uc.get("criteria") or [], key=lambda a: a["ac_id"]):
            out.append(f"- [{'x' if ac['done'] else ' '}] **{_safe(ac['ac_id'])}**: {_safe(ac['text'])}")
        out.append("")
    if not ucs:
        out += ["_(ninguna UC cerrada todavía)_", ""]
    out.append(end)
    return "\n".join(out)


def doc_header(feature: str) -> str:
    return (
        f"# Comportamiento: {feature}\n\n"
        "> Lo que el sistema hace hoy: una sección por historia, con los criterios de sus UC cerradas.\n"
        "> Lo escribe el engine al cerrar cada UC y se regenera desde el tablero: no lo\n"
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


# ── La cabecera de un PRD y su marca ────────────────────────────────


class _Fences:
    """Sigue los bloques de código vallados (``` o ~~~) línea a línea."""

    def __init__(self) -> None:
        self.open: str | None = None

    def code(self, line: str) -> bool:
        """True si la línea es código: está dentro de un bloque o es una de sus vallas."""
        m = _FENCE_RE.match(line)
        if self.open:
            fence = m.group(1) if m else ""
            if fence and fence[0] == self.open[0] and len(fence) >= len(self.open) and not line[m.end():].strip():
                self.open = None
            return True
        if m:
            self.open = m.group(1)
            return True
        return False


def _header(lines: list[str]) -> list[int]:
    """Los índices de la cabecera: las líneas antes del primer subtítulo (``## …``), fuera de código."""
    fences = _Fences()
    out: list[int] = []
    for i, line in enumerate(lines):
        if fences.code(line):
            continue
        if _SUBHEADING_RE.match(line):
            break
        out.append(i)
    return out


def is_superseded(text: str) -> bool:
    """¿Lleva el PRD la marca de superado como línea propia de su cabecera?"""
    lines = (text or "").split("\n")
    return any(SUPERSEDED_RE.match(lines[i]) for i in _header(lines))


def superseded_mark(date: str, by: str) -> str:
    return f'<!-- @specbox:prd status="superseded" date="{_attr(date)}" by="{_attr(by)}" -->'


def mark_superseded(prd: str, date: str, by: str) -> str:
    """El PRD con la marca de superado debajo de la de formato (o del título); igual si ya la tiene."""
    if is_superseded(prd):
        return prd
    mark = superseded_mark(date, by)
    lines = prd.split("\n")
    head = _header(lines)
    at = next((i for i in head if FORMAT_MARK_RE.match(lines[i])), None)
    if at is None:
        at = next((i for i in head if lines[i].startswith("# ")), None)
    if at is None:
        return mark + "\n" + prd
    return "\n".join([*lines[: at + 1], mark, *lines[at + 1:]])


def unmark_superseded(prd: str, by: str) -> str:
    """El PRD sin la marca de superado que puso el engine con ese documento; igual si no la tiene.

    Una marca con otro ``by`` (puesta a mano, o por otro documento) se queda.
    """
    lines = prd.split("\n")
    drop = {i for i in _header(lines) if (m := SUPERSEDED_RE.match(lines[i])) and m.group(2) == by}
    if not drop:
        return prd
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


def prd_stories(prd: str) -> list[str]:
    """Las historias que define un PRD: las que nombran sus encabezados o las líneas «>» de su cabecera.

    Fuera de bloques de código. Una «>» del cuerpo es una cita (otra historia de la que se habla), no
    una que el PRD defina.
    """
    lines = (prd or "").split("\n")
    head = set(_header(lines))
    found: list[str] = []
    fences = _Fences()
    for i, line in enumerate(lines):
        if fences.code(line) or not _DEFINING_RE.match(line):
            continue
        if line.lstrip().startswith(">") and i not in head:
            continue
        for us in _US_ID.findall(line):
            if us.upper() not in found:
                found.append(us.upper())
    return found


# ── Lectores: solo los PRD vigentes ─────────────────────────────────


def split_documents(content: str) -> list[str]:
    """El contenido de varios PRD juntos, partido por documento.

    Con las marcas ``<!-- @specbox:file path="…" -->`` que pone /acceptance-check delante de cada
    fichero, un documento por marca. Sin ellas, un documento empieza en un título ``# …`` fuera de
    bloques de código, junto con las marcas ``@specbox:prd`` que lleve justo encima (las de debajo ya
    son suyas). Sin ninguno, un solo documento. Unir las partes con «\\n» da el contenido de partida.
    """
    lines = (content or "").split("\n")
    docs: list[list[str]] = [[]]
    if any(FILE_MARK_RE.match(line) for line in lines):
        for line in lines:
            if FILE_MARK_RE.match(line) and any(x.strip() for x in docs[-1]):
                docs.append([])
            docs[-1].append(line)
        return ["\n".join(d) for d in docs]
    fences = _Fences()
    for line in lines:
        if not fences.code(line) and line.startswith("# "):
            cur = docs[-1]
            k = len(cur)
            while k > 0 and (not cur[k - 1].strip() or PRD_MARK_RE.match(cur[k - 1])):
                k -= 1
            tail = cur[k:]
            first_mark = next((n for n, x in enumerate(tail) if PRD_MARK_RE.match(x)), len(tail))
            head, moved = cur[: k + first_mark], tail[first_mark:]
            if any(x.strip() for x in head):
                docs[-1] = head
                docs.append(moved)
        docs[-1].append(line)
    return ["\n".join(d) for d in docs]


def _hides_a_title(doc: str) -> bool:
    """¿Lleva el documento, dentro de un bloque de código, una línea que empieza por «# »?

    Sin marcas de fichero, una valla de código que un PRD deja sin cerrar se come los PRD que van
    detrás, y su título acaba dentro del bloque. Un documento así no se deja fuera: podría llevar otro.
    """
    fences = _Fences()
    return any(fences.code(line) and line.startswith("# ") for line in doc.split("\n"))


def _partition(content: str) -> tuple[list[str], list[bool]]:
    """Los documentos y cuáles se dejan fuera por superados."""
    docs = split_documents(content)
    marked = any(FILE_MARK_RE.match(line) for line in (content or "").split("\n"))
    return docs, [is_superseded(d) and (marked or not _hides_a_title(d)) for d in docs]


def current_prd_content(content: str) -> tuple[str, int]:
    """El contenido sin los PRD superados, y cuántos se dejaron fuera.

    Sin ningún PRD superado devuelve el contenido tal cual, byte a byte (AC-05). Sin marcas de fichero,
    en la duda (un título dentro de un bloque de código) un PRD superado se queda: se lee de más, nunca
    de menos.
    """
    docs, flags = _partition(content)
    if not any(flags):
        return content, 0
    kept = [d for d, superseded in zip(docs, flags) if not superseded]
    return "\n".join(kept), sum(flags)


def superseded_prd_content(content: str) -> str:
    """Solo los PRD superados que ``current_prd_content`` deja fuera, unidos con «\\n» ('' si ninguno).

    Los lectores lo usan de respaldo: una UC pedida cuyos criterios no están en lo vigente (una historia
    reabierta por /prd antes de que el hook quitara la marca) los toma de aquí.
    """
    docs, flags = _partition(content)
    return "\n".join(d for d, superseded in zip(docs, flags) if superseded)


# ── Las historias del tablero (ítems de FreeForm o DTO de cualquier backend) ──


def _get(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _has(item: Any, label: str) -> bool:
    return label in (_get(item, "labels") or [])


def _ident(item: Any, prefix: str) -> str:
    from .spec_backend import parse_item_id

    meta = _get(item, "meta") or {}
    raw = meta.get(f"{prefix.lower()}_id") or parse_item_id(str(_get(item, "name") or "").strip(), prefix)[0] or ""
    return str(raw).upper()


def complete_stories(items: list[Any]) -> list[str]:
    """Las historias sin nada pendiente: archivadas, o con UC y todas las no archivadas cerradas.

    Una historia sin ninguna UC no está completa (no se ha hecho nada); una con todas sus UC archivadas
    sí (quedaron sustituidas).
    """
    rows: dict[Any, dict[str, Any]] = {}
    for item in items:
        if _has(item, "US"):
            us = _ident(item, "US")
            if _US_ONLY.match(us):
                rows[_get(item, "id")] = {"us_id": us, "archived": _get(item, "state") == "archived", "ucs": 0, "open": 0}
    for item in items:
        row = rows.get(_get(item, "parent_id")) if _has(item, "UC") else None
        if row is not None:
            row["ucs"] += 1
            if _get(item, "state") not in ("done", "archived"):
                row["open"] += 1
    out: list[str] = []
    for row in rows.values():
        if (row["archived"] or (row["ucs"] and not row["open"])) and row["us_id"] not in out:
            out.append(row["us_id"])
    return out


def _story(items: list[Any], *, uc_id: str | None = None, us_id: str | None = None) -> Any | None:
    if us_id:
        return next((i for i in items if _has(i, "US") and _ident(i, "US") == us_id.upper()), None)
    uc = next((i for i in items if _has(i, "UC") and _ident(i, "UC") == str(uc_id or "").upper()), None)
    if uc is None:
        return None
    return next((i for i in items if _has(i, "US") and _get(i, "id") == _get(uc, "parent_id")), None)


def freeform_criteria(items: list[Any], uc: Any) -> list[dict[str, Any]]:
    """Los criterios de una UC en items.json, sin los archivados: los mismos que lee el hook."""
    return [
        criterion((_get(ac, "meta") or {}).get("ac_id") or "", _get(ac, "name") or "", _get(ac, "state") == "done")
        for ac in items
        if _has(ac, "AC") and _get(ac, "parent_id") == _get(uc, "id") and _get(ac, "state") != "archived"
    ]


def wanted_stories(target: str, extra: list[str] | None) -> tuple[list[str], int]:
    """La historia de la UC y las pedidas (hasta ``MAX_STORIES``), y cuántas se ignoraron."""
    out, ignored = [target], 0
    for raw in extra or []:
        us = str(raw or "").strip().upper()
        if not _US_ONLY.match(us):
            ignored += 1
        elif us not in out:
            if len(out) > MAX_STORIES:
                ignored += 1
            else:
                out.append(us)
    return out, ignored


async def behavior_doc_from_items(
    items: list[Any],
    criteria_of: Callable[[Any], Awaitable[list[dict[str, Any]]]],
    *,
    uc_id: str | None = None,
    us_id: str | None = None,
    us_ids: list[str] | None = None,
) -> dict[str, Any]:
    """El ``behavior_doc`` a partir de los ítems del tablero y de cómo leer los criterios de una UC."""
    story = _story(items, uc_id=uc_id, us_id=us_id)
    target = _ident(story, "US") if story is not None else ""
    if not _US_ONLY.match(target):
        who = us_id or uc_id
        return {"ok": False, "error": "story_not_found", "reason": f"No se encontró la historia de {who}."}
    wanted, ignored = wanted_stories(target, us_ids)
    sections: dict[str, str] = {}
    for us in wanted:
        node = _story(items, us_id=us)
        if node is None:
            continue
        ucs = []
        for uc in items:
            if _has(uc, "UC") and _get(uc, "parent_id") == _get(node, "id") and _get(uc, "state") == "done":
                ucs.append({
                    "uc_id": _ident(uc, "UC"),
                    "title": _UC_PREFIX.sub("", _clean(_get(uc, "name"))),
                    "criteria": await criteria_of(uc),
                })
        sections[us] = render_section({"us_id": us, "title": _US_PREFIX.sub("", _clean(_get(node, "name")))}, ucs)
    out = {
        "ok": True,
        "us_id": target,
        "section": sections[target],
        "sections": sections,
        "complete_stories": complete_stories(items),
        "date": datetime.now(timezone.utc).date().isoformat(),
        "spec_dir": SPEC_DIR,
    }
    if ignored:
        out["ignored_us_ids"] = ignored
    return out


async def behavior_doc_from_backend(
    backend: Any, board_id: str, uc_id: str | None = None, *, us_id: str | None = None,
    us_ids: list[str] | None = None,
) -> dict[str, Any]:
    """La sección de la historia (y las pedidas) y las historias completas, leídas del tablero."""
    items = await backend.list_board_summary(board_id)

    async def criteria_of(uc: Any) -> list[dict[str, Any]]:
        acs = await backend.get_acceptance_criteria(board_id, _get(uc, "id"))
        return [criterion(ac.id, ac.text, ac.done) for ac in acs]

    return await behavior_doc_from_items(items, criteria_of, uc_id=uc_id, us_id=us_id, us_ids=us_ids)


async def behavior_doc_from_freeform(
    content: str, uc_id: str | None = None, *, us_id: str | None = None, us_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Lo mismo con el items.json entero de FreeForm, con las reglas del hook (prueba de paridad)."""
    items = json.loads(content or "[]")
    if not isinstance(items, list):
        return {"ok": False, "error": "items_not_a_list", "reason": "items.json no es una lista de ítems."}

    async def criteria_of(uc: Any) -> list[dict[str, Any]]:
        return freeform_criteria(items, uc)

    return await behavior_doc_from_items(items, criteria_of, uc_id=uc_id, us_id=us_id, us_ids=us_ids)


def _is_fragment(content: str) -> bool:
    try:
        parsed = json.loads(content or "[]")
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and "format" in parsed


async def behavior_doc_sync(ctx: Any, board_id: str, uc_id: str | None, items_content: str | None,
                            result: dict[str, Any], *, us_id: str | None = None,
                            us_ids: list[str] | None = None) -> dict[str, Any]:
    """El ``behavior_doc`` de la tool. Nunca lanza: un fallo va con ``ok: false``."""
    try:
        if items_content is not None:
            content = result.get("items_content") if isinstance(result.get("items_content"), str) else items_content
            if _is_fragment(content):
                return {"ok": True, "render": "client", "spec_dir": SPEC_DIR}
            return await behavior_doc_from_freeform(content, uc_id, us_id=us_id, us_ids=us_ids)
        from .auth_gateway import get_session_backend

        backend = await get_session_backend(ctx)
        try:
            return await behavior_doc_from_backend(backend, board_id, uc_id, us_id=us_id, us_ids=us_ids)
        finally:
            await backend.close()
    except Exception as exc:  # noqa: BLE001 — el documento nunca deshace el cambio
        return {"ok": False, "error": "behavior_doc_failed", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def with_behavior_doc_sync(fn):
    """Tras ``complete_uc``, ``move_uc`` o ``add_uc``, ``behavior_doc`` con las secciones (UC-12605).

    Solo si la llamada trae ``with_behavior_doc=True``, que pone el hook app-docs-fragment cuando el
    repositorio que guarda el canon está en su rama principal y el servidor es 6.47.0 o posterior: sin
    pedirlo, la respuesta queda como antes y no gasta contexto. ``behavior_doc_us_ids`` pide además la
    sección de esas historias (las que define el PRD). ``add_uc`` da la historia en ``us_id``; las otras,
    la UC en ``uc_id``. Va por fuera de ``@returns_items_content`` para ver el tablero ya cambiado.
    Nunca cambia el resultado de la tool más allá de añadir ``behavior_doc``, ni lanza.
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
            us_ids = bound.get("behavior_doc_us_ids")
            result["behavior_doc"] = await behavior_doc_sync(
                bound.get("ctx"), str(bound.get("board_id") or ""), bound.get("uc_id") or None,
                bound.get("items_content"), result,
                us_id=bound.get("us_id") or None,
                us_ids=list(us_ids) if isinstance(us_ids, (list, tuple)) else None,
            )
        except Exception as exc:  # noqa: BLE001 — el documento nunca deshace el cambio
            result["behavior_doc"] = {"ok": False, "error": "behavior_doc_failed", "reason": str(exc)[:200]}
        return result

    return wrapper
