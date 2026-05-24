"""Zone parser for app_prd.md / app_spec.md (v5.29.0).

The canonical project documents under `doc/app/` are partitioned into
zones with explicit policies — what the user owns vs. what the engine
auto-syncs vs. what is hybrid append-only. The parser reads zone
markers, validates policy invariants, and computes a deterministic
signature for drift detection.

Zone marker syntax::

    <!-- @specbox:zone start kind="auto" id="roadmap" auto_sync_on="complete_uc,move_uc" -->
    ## 5. Roadmap de US
    {engine-managed content}
    <!-- @specbox:zone end -->

Zone kinds:
    manual  — only the user edits; engine reads but never writes.
    auto    — engine reads and rewrites; user edits trigger a warning
              hook and pause auto-sync until reconciled.
    hybrid  — append-only; user adds entries above, engine adds entries
              below with `<!-- engine-entry id=... -->` markers.

The parser is intentionally stateless and side-effect-free. PR-11 will
add a higher-level `app_sync.py` orchestrator on top.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ZoneKind(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"
    HYBRID = "hybrid"


@dataclass
class Zone:
    """One parsed zone with metadata and content."""

    kind: ZoneKind
    id: str
    auto_sync_on: tuple[str, ...] = ()
    merge: str | None = None  # for hybrid zones: append_only|prepend_only|...
    start_line: int = 0  # 1-based, line of the `start` marker
    end_line: int = 0    # 1-based, line of the `end` marker
    body: str = ""       # text strictly between the markers (excludes markers themselves)
    status: str | None = None  # optional; "template-pristine" marks zonas vacías de plantilla recién creada


@dataclass
class ParsedDoc:
    """Result of parsing one app_*.md file."""

    path: Path
    zones: list[Zone] = field(default_factory=list)
    # Lines outside any zone (preamble between markers). Kept verbatim so
    # we can re-emit the document without losing user-written headers
    # like the `# App PRD — {project}` title block.
    preamble_chunks: list[tuple[int, int, str]] = field(default_factory=list)
    # Errors encountered during parse. Empty list = doc is well-formed.
    errors: list[str] = field(default_factory=list)

    @property
    def is_well_formed(self) -> bool:
        return not self.errors

    def zone_by_id(self, zone_id: str) -> Zone | None:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def zones_of_kind(self, kind: ZoneKind) -> list[Zone]:
        return [z for z in self.zones if z.kind == kind]


# ── Marker grammar ───────────────────────────────────────────────────

_START_RE = re.compile(
    r"<!--\s*@specbox:zone\s+start\s+(?P<attrs>[^>]+?)\s*-->",
    re.IGNORECASE,
)
_END_RE = re.compile(r"<!--\s*@specbox:zone\s+end\s*-->", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _parse_attrs(attrs_str: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(attrs_str)}


# ── Parser ───────────────────────────────────────────────────────────


def parse_document(path: Path | str, *, content: str | None = None) -> ParsedDoc:
    """Parse an app_*.md file and return its zones.

    Args:
        path: Path to the document. Used for diagnostics and the returned
            ParsedDoc.path field.
        content: Optional in-memory content to parse. When omitted, the
            file at ``path`` is read.
    """
    p = Path(path)
    if content is None:
        content = p.read_text(encoding="utf-8")

    lines = content.splitlines(keepends=False)
    doc = ParsedDoc(path=p)

    open_zone: Zone | None = None
    open_zone_body_lines: list[str] = []
    last_emitted = 0  # 1-based index up to which we've consumed

    for idx, line in enumerate(lines, start=1):
        m_start = _START_RE.search(line)
        m_end = _END_RE.search(line)

        if m_start and m_end:
            doc.errors.append(
                f"line {idx}: zone start and end markers on the same line"
            )
            continue

        if m_start:
            if open_zone is not None:
                doc.errors.append(
                    f"line {idx}: nested zone start before closing zone "
                    f"{open_zone.id!r} (opened at line {open_zone.start_line})"
                )
                # Reset to avoid cascading errors
                open_zone = None
                open_zone_body_lines = []

            attrs = _parse_attrs(m_start.group("attrs"))
            kind = attrs.get("kind", "")
            zone_id = attrs.get("id", "")
            if kind not in {k.value for k in ZoneKind}:
                doc.errors.append(
                    f"line {idx}: invalid kind={kind!r} (expected manual|auto|hybrid)"
                )
                continue
            if not zone_id:
                doc.errors.append(f"line {idx}: zone start missing id")
                continue

            # Capture preamble between the previous emission and this start.
            if last_emitted < idx - 1:
                preamble_text = "\n".join(lines[last_emitted : idx - 1])
                doc.preamble_chunks.append(
                    (last_emitted + 1, idx - 1, preamble_text)
                )

            auto_sync_on_raw = attrs.get("auto_sync_on", "")
            auto_sync_on = tuple(
                e.strip() for e in auto_sync_on_raw.split(",") if e.strip()
            )
            open_zone = Zone(
                kind=ZoneKind(kind),
                id=zone_id,
                auto_sync_on=auto_sync_on,
                merge=attrs.get("merge"),
                status=attrs.get("status"),  # v6.0: "template-pristine" para plantillas vacías
                start_line=idx,
            )
            open_zone_body_lines = []
            continue

        if m_end:
            if open_zone is None:
                doc.errors.append(f"line {idx}: zone end without matching start")
                continue
            open_zone.end_line = idx
            open_zone.body = "\n".join(open_zone_body_lines)
            doc.zones.append(open_zone)
            last_emitted = idx
            open_zone = None
            open_zone_body_lines = []
            continue

        if open_zone is not None:
            open_zone_body_lines.append(line)

    if open_zone is not None:
        doc.errors.append(
            f"unclosed zone {open_zone.id!r} (started line {open_zone.start_line})"
        )

    # Trailing preamble (anything after the last zone).
    if last_emitted < len(lines):
        trailing = "\n".join(lines[last_emitted:])
        if trailing:
            doc.preamble_chunks.append((last_emitted + 1, len(lines), trailing))

    return doc


# ── Validation ───────────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    zone_id: str | None
    message: str


def validate_document(doc: ParsedDoc, *, required_zones: dict[str, ZoneKind] | None = None) -> list[ValidationIssue]:
    """Check structural invariants of a parsed document.

    Args:
        doc: Result of parse_document.
        required_zones: Optional map of zone_id → expected ZoneKind. Each
            missing or kind-mismatched zone yields an error.
    """
    issues: list[ValidationIssue] = []

    # Re-emit parser errors as validation issues so callers have a single
    # surface to inspect.
    for err in doc.errors:
        issues.append(ValidationIssue(severity="error", zone_id=None, message=err))

    # Duplicate IDs.
    seen: dict[str, int] = {}
    for z in doc.zones:
        if z.id in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    zone_id=z.id,
                    message=(
                        f"duplicate zone id {z.id!r} at line {z.start_line} "
                        f"(first seen at line {seen[z.id]})"
                    ),
                )
            )
        else:
            seen[z.id] = z.start_line

    # auto_sync_on only meaningful for auto/hybrid zones.
    for z in doc.zones:
        if z.kind == ZoneKind.MANUAL and z.auto_sync_on:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    zone_id=z.id,
                    message=(
                        f"zone {z.id!r} is manual but declares auto_sync_on="
                        f"{','.join(z.auto_sync_on)} — attribute will be ignored"
                    ),
                )
            )

    if required_zones:
        present = {z.id: z for z in doc.zones}
        for zid, expected_kind in required_zones.items():
            zone = present.get(zid)
            if zone is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        zone_id=zid,
                        message=f"required zone {zid!r} missing",
                    )
                )
            elif zone.kind != expected_kind:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        zone_id=zid,
                        message=(
                            f"zone {zid!r} has kind={zone.kind.value}, expected "
                            f"{expected_kind.value}"
                        ),
                    )
                )

    return issues


# ── Signature (for drift detection) ──────────────────────────────────


def compute_signature(doc: ParsedDoc) -> str:
    """Compute a deterministic signature of a parsed document.

    Used by the drift detector (PR-15) and the sync guard (PR-13) to
    detect when a doc has changed since the last sync without diffing
    the entire file. Hashes only zone bodies + ids + kinds, not
    preambles or marker line numbers, so cosmetic edits (adding a
    blank line between zones) do not break the signature.
    """
    h = hashlib.sha256()
    for z in sorted(doc.zones, key=lambda z: z.id):
        h.update(z.id.encode("utf-8"))
        h.update(b"\x00")
        h.update(z.kind.value.encode("utf-8"))
        h.update(b"\x00")
        h.update(z.body.encode("utf-8"))
        h.update(b"\x00\x00")
    return h.hexdigest()


# ── Zone replacement (for auto-sync) ─────────────────────────────────


def replace_zone_body(content: str, zone_id: str, new_body: str) -> str:
    """Return ``content`` with the body of zone ``zone_id`` replaced.

    Preserves the start/end markers and everything outside the zone
    verbatim. Raises ``KeyError`` if the zone is not found, ``ValueError``
    if the zone is malformed.
    """
    doc = parse_document(Path("<inline>"), content=content)
    zone = doc.zone_by_id(zone_id)
    if zone is None:
        raise KeyError(f"zone {zone_id!r} not found")
    if zone.start_line == 0 or zone.end_line == 0:
        raise ValueError(f"zone {zone_id!r} is malformed (missing markers)")

    lines = content.splitlines(keepends=False)
    pre = lines[: zone.start_line]  # includes the start marker line
    post = lines[zone.end_line - 1 :]  # includes the end marker line

    # Body of the new zone keeps surrounding blank-line ergonomics.
    new_lines = new_body.splitlines() if new_body else []
    rebuilt = pre + new_lines + post
    # Preserve trailing newline if the original had one.
    out = "\n".join(rebuilt)
    if content.endswith("\n"):
        out += "\n"
    return out
