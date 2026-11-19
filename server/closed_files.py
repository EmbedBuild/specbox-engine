"""Los ficheros de una UC cerrada (US-126 · UC-12603).

Al cerrar una UC, ``complete_uc(files=[…])`` guarda en ``meta.closed_files`` los ficheros que cambió
su PR (/implement los saca con ``gh pr view <n> --json files``). Un cambio posterior en uno de esos
ficheros, desde otra UC o sin UC, sale en el informe de la puerta de desviación con la UC cerrada que
toca y la propuesta de revisar sus criterios. El engine no cambia la spec: lo decide una persona.

Una UC cerrada sin la lista (las cerradas antes de 6.46.0) no avisa: no hay con qué comparar.

Puro: no lee disco ni el tablero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Una PR grande cambia cientos de ficheros; más que esto es un volcado, no una PR.
MAX_CLOSED_FILES = 1000
MAX_CLOSED_PATH = 300

CLOSED_WITHOUT_FILES_NOTICE = (
    "{n} UC cerradas no tienen su lista de ficheros (se cerraron sin `files` en complete_uc): no "
    "avisan hasta que la tengan (complete_uc con `files` sobre la UC ya cerrada la añade)."
)
NO_FILES_AT_CLOSE_NOTICE = (
    "La UC se cerró sin `files`: un cambio posterior en sus ficheros no avisará. Pasa a complete_uc "
    "los ficheros de su PR (gh api repos/<owner>/<repo>/pulls/<n>/files --paginate) para que avise."
)
#: Los avisos que caben en un informe; el resto se cuenta.
MAX_TOUCHES = 20
NOT_SUPPORTED_NOTICE = (
    "Este tablero no guarda los ficheros de una UC cerrada (Trello y Plane no tienen dónde): "
    "el aviso de UC cerradas no está disponible."
)


class ClosedFilesError(ValueError):
    """La lista de ficheros de un cierre no es válida."""


def normalize_path(path: str) -> str:
    """``./server\\x.py`` → ``server/x.py``: la forma en que se guardan y se comparan."""
    clean = path.strip().replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def normalize_closed_files(raw: Any) -> list[str]:
    """Las rutas de un cierre: relativas al repo, sin ``..``, sin repetir, en su orden."""
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(f, str) for f in raw):
        raise ClosedFilesError("files debe ser una lista de rutas (texto)")
    out: list[str] = []
    for item in raw:
        path = normalize_path(item)
        if not path:
            continue
        if path.startswith("/") or ".." in path.split("/") or "\n" in path or "\r" in path:
            raise ClosedFilesError(f"files: {item!r} tiene que ser una ruta relativa al repositorio, sin «..»")
        if len(path) > MAX_CLOSED_PATH:
            raise ClosedFilesError(f"files: una ruta admite como mucho {MAX_CLOSED_PATH} caracteres")
        if path not in out:
            out.append(path)
    if len(out) > MAX_CLOSED_FILES:
        raise ClosedFilesError(f"files admite como mucho {MAX_CLOSED_FILES} rutas")
    return out


def merge_closed_files(existing: Any, new: list[str]) -> tuple[list[str], bool]:
    """``(lista, recortada)``: lo que ya tenía la UC más lo nuevo (una UC que se reabre y se vuelve a
    cerrar suma su PR nueva). Por encima del tope se quedan los más recientes y se dice."""
    before = [normalize_path(p) for p in existing if isinstance(p, str)] if isinstance(existing, list) else []
    fresh = set(new)
    out = [p for p in dict.fromkeys(before) if p and p not in fresh] + [p for p in new if p]
    return out[-MAX_CLOSED_FILES:], len(out) > MAX_CLOSED_FILES


@dataclass
class ClosedUc:
    """Una UC cerrada con lo que guardó su cierre."""

    uc_id: str
    us_id: str
    name: str
    files: list[str] | None  # None = se cerró sin lista
    closed_at: str | None = None  # el último cierre con lista
    repo: str | None = None  # el repositorio de su PR («owner/name»)
    satellite: str | None = None  # su satélite en multirepo
    extra: dict[str, Any] = field(default_factory=dict)


def proposal(uc_id: str, name: str, files: list[str]) -> str:
    """El aviso de una UC cerrada: propone revisar sus criterios y deja la decisión a una persona."""
    listed = ", ".join(f"`{f}`" for f in files[:5]) + (f" y {len(files) - 5} más" if len(files) > 5 else "")
    title = f" («{name}»)" if name else ""
    return (
        f"Este cambio toca {listed}, de {uc_id}{title}, ya cerrada: revisa si sus criterios siguen "
        "valiendo. La spec no cambia sola: si hay que cambiarla, lo decide una persona (update_ac, "
        "add_ac o delete_ac)."
    )


def _same_repo(uc: ClosedUc, repo: str | None, satellite: str | None) -> bool:
    """En multirepo una ruta solo es «la misma» en el mismo repositorio: por el de su PR si los dos lo
    saben; si no, por el satélite. Sin ninguno de los dos, cuenta."""
    if repo and uc.repo:
        return uc.repo.lower() == repo.lower()
    if satellite and uc.satellite:
        return uc.satellite.lower() == satellite.lower()
    return True


def closed_uc_touches(
    closed: list[ClosedUc],
    paths: list[str],
    exclude: list[str] | str | None = None,
    *,
    repo: str | None = None,
    satellite: str | None = None,
    limit: int = MAX_TOUCHES,
) -> dict[str, Any]:
    """Para unas rutas cambiadas, qué UC cerradas las cambiaron en su cierre.

    ``exclude`` son las UC de la rama (sus propios ficheros no son «otra UC»). ``repo`` y ``satellite``
    son los del cambio: una UC cerrada de otro repositorio no cuenta. Devuelve ``touches`` (las que más
    ficheros comparten primero, hasta ``limit``, con los ficheros y la propuesta), ``touches_total``,
    ``by_path`` (ruta → UC) y ``closed_without_files`` (las cerradas sin lista, que no avisan).
    """
    wanted = [p for p in dict.fromkeys(normalize_path(p) for p in paths if isinstance(p, str)) if p]
    skip = {u.upper() for u in ([exclude] if isinstance(exclude, str) else exclude or [])}
    by_path: dict[str, list[str]] = {}
    touches: list[dict[str, Any]] = []
    without = 0
    for uc in closed:
        if uc.files is None:
            without += 1
            continue
        if uc.uc_id.upper() in skip or not _same_repo(uc, repo, satellite):
            continue
        own = set(uc.files)
        hit = [p for p in wanted if p in own]
        if not hit:
            continue
        for path in hit:
            by_path.setdefault(path, []).append(uc.uc_id)
        touches.append({
            "uc_id": uc.uc_id,
            "us_id": uc.us_id,
            "name": uc.name,
            "closed_at": uc.closed_at,
            "files": hit,
            "proposal": proposal(uc.uc_id, uc.name, hit),
        })
    touches.sort(key=lambda t: (len(t["files"]), t["closed_at"] or ""), reverse=True)  # más ficheros, más recientes
    out: dict[str, Any] = {
        "touches": touches[:limit], "touches_total": len(touches), "by_path": by_path, "closed_without_files": without,
    }
    if without:
        out["notice"] = CLOSED_WITHOUT_FILES_NOTICE.format(n=without)
    return out
