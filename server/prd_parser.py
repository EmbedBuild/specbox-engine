"""PRD Parser — UC-003 of US-01 Spec-Code Sync Layer.

Parses Implementation Status sections from PRD files into structured data.

Pure Python module — no FastMCP or backend dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PhaseStatus:
    """Status of a single implementation phase."""
    phase_number: int
    phase_name: str
    status: str  # complete | failed | needs_healing
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    deltas: str = ""
    decisions: list[str] = field(default_factory=list)
    healing: str | None = None
    error: str | None = None


@dataclass
class UCImplementationStatus:
    """Implementation status for a single UC."""
    uc_id: str
    timestamp: str | None = None
    branch: str | None = None
    phases: list[PhaseStatus] = field(default_factory=list)
    overall_status: str = "not_implemented"  # conforme | con_deltas | parcial | not_implemented
    delta_count: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_implementation_status(
    prd_content: str,
    target_id: str,
) -> list[UCImplementationStatus]:
    """Parse Implementation Status sections from a PRD.

    Args:
        prd_content: Full text content of the PRD markdown.
        target_id: US-id (e.g. "US-01") or UC-id (e.g. "UC-001").

    Returns:
        List of UCImplementationStatus objects.
        - If target_id is UC-XXX: list with 0 or 1 element.
        - If target_id is US-XX: list with all matching UCs.
    """
    # Extract all Implementation Status blocks
    all_statuses = _extract_all_uc_statuses(prd_content)

    if not all_statuses:
        if target_id.upper().startswith("UC-"):
            return [UCImplementationStatus(uc_id=target_id, overall_status="not_implemented")]
        return []

    # Filter by target
    if target_id.upper().startswith("UC-"):
        matches = [s for s in all_statuses if s.uc_id.upper() == target_id.upper()]
        if not matches:
            return [UCImplementationStatus(uc_id=target_id, overall_status="not_implemented")]
        return matches

    elif target_id.upper().startswith("US-"):
        # Map US-XX to its UCs: UC-XX1, UC-XX2, etc.
        us_num = _extract_us_number(target_id)
        if us_num is not None:
            matches = [s for s in all_statuses if _uc_belongs_to_us(s.uc_id, us_num)]
            return matches
        # Fallback: return all
        return all_statuses

    return []


def get_not_implemented(uc_id: str) -> UCImplementationStatus:
    """Return a not-implemented status for a UC (AC-12)."""
    return UCImplementationStatus(uc_id=uc_id, overall_status="not_implemented")


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------

_UC_STATUS_HEADER = re.compile(
    r"^###\s+Implementation Status\s*[-—]\s*(UC-\d+)",
    re.IGNORECASE | re.MULTILINE,
)

_PHASE_HEADER = re.compile(
    r"^####\s+Fase\s+(\d+):\s+(.+)",
    re.MULTILINE,
)

_FIELD_PATTERN = re.compile(
    r"^-\s+\*\*(.+?):\*\*\s*(.*)",
    re.MULTILINE,
)

_TIMESTAMP_PATTERN = re.compile(
    r"\*\*Timestamp:\*\*\s*(.+)",
    re.IGNORECASE,
)

_BRANCH_PATTERN = re.compile(
    r"\*\*Branch:\*\*\s*(.+)",
    re.IGNORECASE,
)


def _extract_all_uc_statuses(content: str) -> list[UCImplementationStatus]:
    """Extract all UC Implementation Status blocks from PRD content."""
    # Find the main ## Implementation Status section
    impl_section_match = re.search(r"^## Implementation Status", content, re.MULTILINE)
    if not impl_section_match:
        return []

    impl_content = content[impl_section_match.start():]

    # Split by UC status headers
    uc_headers = list(_UC_STATUS_HEADER.finditer(impl_content))
    if not uc_headers:
        return []

    results: list[UCImplementationStatus] = []

    for i, header_match in enumerate(uc_headers):
        uc_id = header_match.group(1)
        start = header_match.start()
        end = uc_headers[i + 1].start() if i + 1 < len(uc_headers) else len(impl_content)
        uc_block = impl_content[start:end]

        status = _parse_uc_block(uc_id, uc_block)
        results.append(status)

    return results


def _parse_uc_block(uc_id: str, block: str) -> UCImplementationStatus:
    """Parse a single UC Implementation Status block."""
    # Extract timestamp
    ts_match = _TIMESTAMP_PATTERN.search(block)
    timestamp = ts_match.group(1).strip() if ts_match else None

    # Extract branch
    br_match = _BRANCH_PATTERN.search(block)
    branch = br_match.group(1).strip() if br_match else None

    # Extract phases
    phase_headers = list(_PHASE_HEADER.finditer(block))
    phases: list[PhaseStatus] = []

    for i, ph_match in enumerate(phase_headers):
        phase_num = int(ph_match.group(1))
        phase_name = ph_match.group(2).strip()
        ph_start = ph_match.start()
        ph_end = phase_headers[i + 1].start() if i + 1 < len(phase_headers) else len(block)
        phase_block = block[ph_start:ph_end]

        phase = _parse_phase_block(phase_num, phase_name, phase_block)
        phases.append(phase)

    # Compute overall status and delta count
    delta_count = 0
    has_failed = False
    has_deltas = False

    for phase in phases:
        if phase.status == "failed":
            has_failed = True
        if phase.deltas and "sin deltas" not in phase.deltas.lower():
            has_deltas = True
            delta_count += 1
        if phase.healing:
            delta_count += 1

    if has_failed:
        overall_status = "parcial"
    elif has_deltas:
        overall_status = "con_deltas"
    elif phases:
        overall_status = "conforme"
    else:
        overall_status = "not_implemented"

    return UCImplementationStatus(
        uc_id=uc_id,
        timestamp=timestamp,
        branch=branch,
        phases=phases,
        overall_status=overall_status,
        delta_count=delta_count,
    )


def _parse_phase_block(phase_num: int, phase_name: str, block: str) -> PhaseStatus:
    """Parse a single phase block."""
    fields: dict[str, str] = {}
    for match in _FIELD_PATTERN.finditer(block):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        fields[key] = value

    status = fields.get("estado", "complete")
    files_created = _parse_file_list(fields.get("archivos creados", ""))
    files_modified = _parse_file_list(fields.get("archivos modificados", ""))
    deltas = fields.get("deltas vs plan", "")
    decisions_raw = fields.get("decisiones", "")
    decisions = [d.strip() for d in decisions_raw.split(";") if d.strip()] if decisions_raw and decisions_raw != "ninguna" else []
    healing = fields.get("self-healing")
    error = fields.get("error")

    return PhaseStatus(
        phase_number=phase_num,
        phase_name=phase_name,
        status=status,
        files_created=files_created,
        files_modified=files_modified,
        deltas=deltas,
        decisions=decisions,
        healing=healing,
        error=error,
    )


def _parse_file_list(text: str) -> list[str]:
    """Parse a comma-separated file list, stripping backticks."""
    if not text or text.strip().lower() == "ninguno":
        return []
    # Extract paths from backtick-wrapped items
    files = re.findall(r"`([^`]+)`", text)
    if files:
        return files
    # Fallback: split by comma
    return [f.strip() for f in text.split(",") if f.strip()]


def _extract_us_number(us_id: str) -> int | None:
    """Extract the numeric part from a US-id (e.g. 'US-01' -> 1)."""
    match = re.search(r"US-(\d+)", us_id, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _uc_belongs_to_us(uc_id: str, us_number: int) -> bool:
    """Heuristic: UC-001..UC-003 belong to US-01, UC-004..UC-006 to US-02, etc.

    This works when UCs follow the PRD numbering convention.
    Fallback: check if first digit(s) of UC number match US number.
    """
    match = re.search(r"UC-(\d+)", uc_id, re.IGNORECASE)
    if not match:
        return False
    uc_num = int(match.group(1))
    # Convention: UC-001..UC-003 → US-01, UC-004..UC-006 → US-02, etc.
    # More robust: look at the hundreds/tens digit
    # For the v5.0 PRD: US-01 has UC-001..003, US-02 has UC-004..006, etc.
    # We use a simple heuristic: check if UC is in the range of that US
    # based on the PRD structure (3 UCs per US average)
    # Better approach: just check prefix match
    uc_str = match.group(1)
    if len(uc_str) == 3:
        # UC-001 → prefix "0" → matches US-01? No, better: UC-001 first digit "0" → US number?
        # Actually the safest heuristic is: for UC-NNN, if floor((NNN-1)/3)+1 == US number
        # But this only works for 3 UCs per US. Instead, let's use a range approach.
        pass

    # Pragmatic mapping based on common PRD structures:
    # US-01: UC-001..UC-003, US-02: UC-004..UC-006, US-03: UC-007..UC-009
    # US-04: UC-010..UC-012, US-05: UC-013..UC-014
    # This is specific to v5.0 but works as a reasonable heuristic
    us_ranges: dict[int, tuple[int, int]] = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12),
        5: (13, 14),
    }
    if us_number in us_ranges:
        low, high = us_ranges[us_number]
        return low <= uc_num <= high

    # Generic fallback: check hundreds digit
    return (uc_num - 1) // 3 + 1 == us_number
