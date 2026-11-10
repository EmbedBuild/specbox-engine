"""Evidencia estructurada de un criterio de aceptación (US-56 / UC-5601).

Hasta ahora `mark_ac` dejaba la evidencia como texto libre en un comentario de
la UC («AC-01: PASSED — texto [fecha]»), sin autor, tipo ni enlace. El panel y
el portal no pueden enseñar un recibo con eso. Este módulo define la forma
única de una evidencia y las dos maneras de obtenerla:

- **Escrita**: `normalize_evidence` valida lo que llega a `mark_ac` /
  `mark_ac_batch` (texto libre u objeto) y devuelve siempre la misma forma
  ``{type, label, link, detail}``. Quién y cuándo los pone el backend que la
  guarda, nunca el llamante.
- **Leída de los comentarios**: `evidence_from_comments` y
  `verdicts_from_comments` reconstruyen evidencias y veredictos a partir de los
  comentarios de siempre, con autor desconocido (``by: None``). Es lo que ven
  los backends sin almacén por AC (Trello, Plane, FreeForm) y lo mismo que hace
  la migración 0028 en el board native, con las mismas expresiones regulares.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal, Required, TypedDict

EVIDENCE_TYPES: tuple[str, ...] = ("test", "screenshot", "diff", "url", "pr")

#: Tipo que recibe una evidencia escrita en texto libre (AC-02): el texto
#: completo es la etiqueta y no hay enlace.
FREE_TEXT_TYPE = "url"

_FIELDS = ("type", "label", "link", "detail", "commit", "repo")

#: UC-11702: el commit con el que se comprobó el criterio (lo manda quien marca:
#: el servidor no ve su git) y el repositorio donde vive, para enlazarlo.
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class AcEvidenceInput(TypedDict, total=False):
    """Evidencia estructurada tal como la envía el llamante de `mark_ac`."""

    type: Required[Literal["test", "screenshot", "diff", "url", "pr"]]
    label: Required[str]
    link: str | None
    detail: str | None
    #: UC-11702: commit con el que pasó la comprobación (7–40 hexadecimales).
    commit: str | None
    #: UC-11702: repositorio del commit, «owner/nombre» (p. ej. EmbedBuild/specbox-engine).
    repo: str | None


class EvidenceError(ValueError):
    """La evidencia recibida no tiene la forma esperada."""


def normalize_evidence(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Devuelve la evidencia en su forma única, o ``None`` si no hay.

    - ``None`` o texto vacío → ``None`` (sin evidencia, como antes).
    - Texto → ``{type: "url", label: <texto completo>, link: None, detail: None,
      commit: None, repo: None}``.
    - Objeto → se valida campo a campo; lanza `EvidenceError` con el motivo. El
      commit (UC-11702) se guarda en minúsculas; uno que no tenga entre 7 y 40
      caracteres hexadecimales se rechaza y no se marca nada.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return None
        return {"type": FREE_TEXT_TYPE, "label": raw, "link": None, "detail": None, "commit": None, "repo": None}
    if not isinstance(raw, dict):
        raise EvidenceError("evidence debe ser un texto o un objeto {type, label, link, detail}")

    unknown = sorted(set(raw) - set(_FIELDS))
    if unknown:
        raise EvidenceError(
            f"campos desconocidos en evidence: {', '.join(unknown)} "
            f"(admitidos: {', '.join(_FIELDS)})"
        )

    ev_type = raw.get("type")
    if ev_type not in EVIDENCE_TYPES:
        raise EvidenceError(
            f"evidence.type debe ser uno de {', '.join(EVIDENCE_TYPES)}; llegó {ev_type!r}"
        )

    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        raise EvidenceError("evidence.label es obligatorio y no puede estar vacío")

    link = raw.get("link")
    if link is not None:
        if not isinstance(link, str) or not re.match(r"^https?://\S+$", link.strip()):
            raise EvidenceError("evidence.link debe ser una URL http(s) o null")
        link = link.strip()

    detail = raw.get("detail")
    if detail is not None and not isinstance(detail, str):
        raise EvidenceError("evidence.detail debe ser un texto o null")
    if isinstance(detail, str) and not detail.strip():
        detail = None

    commit = raw.get("commit")
    if commit is not None:
        if not isinstance(commit, str) or not COMMIT_RE.match(commit.strip().lower()):
            raise EvidenceError(
                "evidence.commit debe tener entre 7 y 40 caracteres hexadecimales (el hash del commit) o ser null"
            )
        commit = commit.strip().lower()

    repo = raw.get("repo")
    if repo is not None:
        if not isinstance(repo, str) or not REPO_RE.match(repo.strip()):
            raise EvidenceError("evidence.repo debe ser «owner/nombre» (p. ej. EmbedBuild/specbox-engine) o null")
        repo = repo.strip()

    return {
        "type": ev_type,
        "label": label.strip(),
        "link": link,
        "detail": detail,
        "commit": commit,
        "repo": repo,
    }


def evidence_comment_text(evidence: dict[str, Any]) -> str:
    """Texto de la evidencia en el comentario de la UC.

    Una evidencia en texto libre se escribe tal cual, así el comentario de las
    llamadas de siempre no cambia ni un carácter (AC-02). El commit (UC-11702)
    va al final, `` · commit owner/nombre@sha``, y `evidence_from_comments` lo
    recupera.
    """
    commit = evidence.get("commit")
    if (
        evidence["type"] == FREE_TEXT_TYPE
        and evidence["link"] is None
        and evidence["detail"] is None
        and not commit
    ):
        return evidence["label"]
    text = f"[{evidence['type']}] {evidence['label']}"
    if evidence["link"]:
        text += f" <{evidence['link']}>"
    if evidence["detail"]:
        text += f" — {evidence['detail']}"
    if commit:
        repo = evidence.get("repo")
        text += f" · commit {repo}@{commit}" if repo else f" · commit {commit}"
    return text


#: Lo que escribe `evidence_comment_text` para una evidencia estructurada.
_STRUCTURED_RE = re.compile(r"^\[(test|screenshot|diff|url|pr)\] (.+)$", re.DOTALL)
_COMMIT_SUFFIX_RE = re.compile(r" · commit (?:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@)?([0-9a-f]{7,40})$")
_LINK_RE = re.compile(r"^(.*?) <(https?://\S+)>(?: — (.*))?$", re.DOTALL)


def _receipt_from_text(text: str) -> dict[str, Any]:
    """Recibo a partir del texto de un comentario.

    Si el texto tiene la forma que escribe `evidence_comment_text` para una
    evidencia estructurada, se recuperan tipo, etiqueta, enlace, detalle y
    commit (UC-11702 AC-05). Si no, es texto libre, como siempre: tipo «url» y
    el texto entero como etiqueta, sin commit (nunca se deduce uno, AC-06).
    """
    free = {"type": FREE_TEXT_TYPE, "label": text, "link": None, "detail": None, "commit": None, "repo": None}
    structured = _STRUCTURED_RE.match(text)
    if not structured:
        return free
    ev_type, rest = structured[1], structured[2]
    commit = repo = None
    suffix = _COMMIT_SUFFIX_RE.search(rest)
    if suffix:
        repo, commit = suffix[1], suffix[2]
        rest = rest[: suffix.start()]
    link = detail = None
    linked = _LINK_RE.match(rest)
    if linked:
        label, link, detail = linked[1], linked[2], linked[3]
    elif " — " in rest:
        label, detail = rest.split(" — ", 1)
    else:
        label = rest
    if not label.strip():
        return free
    return {"type": ev_type, "label": label, "link": link, "detail": detail, "commit": commit, "repo": repo}


# ── Lectura de los comentarios de siempre ────────────────────────────────
#
# Las mismas expresiones que usa server/db/migrations/0028_ac_evidence_backfill.sql.

#: «AC-01: PASSED — texto [2026-10-01 17:29 UTC]» — lo escribe `mark_ac`.
SINGLE_RE = re.compile(
    r"^(AC-[0-9]+): (PASSED|FAILED)(?: — (.*))? \[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}) UTC\]$",
    re.DOTALL,
)

#: «Validacion AG-09b [2026-10-01 17:29 UTC]:» seguido de una línea por AC — lo escribe `mark_ac_batch`.
BATCH_HEADER_RE = re.compile(r"^Validacion AG-09b \[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}) UTC\]:")
BATCH_LINE_RE = re.compile(r"^\s+(AC-[0-9]+): (PASSED|FAILED)(?: — (.*))?$", re.MULTILINE)


def _stamp(bracketed: str, created_at: str | None) -> str:
    """Fecha ISO de un comentario: su `created_at` si lo tiene, si no la del texto."""
    if created_at:
        return created_at
    return datetime.strptime(bracketed, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).isoformat()


def _parse(comments: list[Any]) -> list[dict[str, Any]]:
    """Cada veredicto que dejan los comentarios: {ac_id, passed, text, at}."""
    found: list[dict[str, Any]] = []
    for c in comments:
        text = getattr(c, "text", None) if not isinstance(c, dict) else c.get("text")
        created = getattr(c, "created_at", None) if not isinstance(c, dict) else c.get("created_at")
        if not text:
            continue
        m = SINGLE_RE.match(text)
        if m:
            found.append(
                {"ac_id": m[1], "passed": m[2] == "PASSED", "text": m[3], "at": _stamp(m[4], created)}
            )
            continue
        header = BATCH_HEADER_RE.match(text)
        if header:
            at = _stamp(header[1], created)
            for line in BATCH_LINE_RE.finditer(text):
                found.append({"ac_id": line[1], "passed": line[2] == "PASSED", "text": line[3], "at": at})
    return found


def evidence_from_comments(comments: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """Evidencias por AC reconstruidas de los comentarios, en orden; autor desconocido."""
    out: dict[str, list[dict[str, Any]]] = {}
    for v in _parse(comments):
        if not v["text"]:
            continue
        out.setdefault(v["ac_id"], []).append(
            {**_receipt_from_text(v["text"]), "by": None, "at": v["at"], "passed": v["passed"]}
        )
    return out


#: UC-11703: marca de un criterio hecho al que ninguna prueba automática vuelve a comprobar.
NO_REPEATABLE_TEST = "sin_prueba_que_se_repita"


def repeatable_test(done: bool, evidence: list[dict[str, Any]]) -> bool | None:
    """Si un criterio hecho tiene al menos un recibo de tipo «test» que pasa (UC-11703).

    La suite de no regresión vuelve a pasar las pruebas en cada UC; un criterio cuyo único recibo
    es una captura, un enlace o una nota no tiene nada que lo vuelva a comprobar solo. Se calcula
    al leer (AC-04), sin guardar nada. Un criterio sin hacer no lleva marca: ``None``.
    """
    if not done:
        return None
    return any(e.get("type") == "test" and e.get("passed") is not False for e in evidence)


def verdicts_from_comments(comments: list[Any]) -> dict[str, dict[str, Any]]:
    """Último veredicto de cada AC según los comentarios; autor desconocido."""
    out: dict[str, dict[str, Any]] = {}
    for v in _parse(comments):
        out[v["ac_id"]] = {"passed": v["passed"], "by": None, "at": v["at"]}
    return out


def accepted_from(done: bool, verdict: dict[str, Any] | None) -> dict[str, Any] | None:
    """Quién aceptó el AC y cuándo, si está hecho y su último veredicto lo aceptó.

    Si el AC está hecho pero el veredicto no lo respalda (se marcó por otra vía,
    p. ej. `update_ac`), devuelve ``None``: no se atribuye una aceptación que no
    consta.
    """
    if not done or not verdict or not verdict.get("passed"):
        return None
    return {"by": verdict.get("by"), "at": verdict.get("at")}
