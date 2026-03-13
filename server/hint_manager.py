"""Hint system for contextual onboarding hints in skills.

UC-005: Hints contextuales en skills existentes.
- AC-21: First /prd shows hint about PRD, US/UC/AC, Definition Quality Gate
- AC-22: First /implement shows hint about Orchestrator, quality gates, GO/NO-GO
- AC-23: Hints controlled by .quality/hint_counters.json, disappear after 3 uses
- AC-24: No hints if project has > 5 completed UCs
- AC-25: Hints don't interfere with flow (shown before execution, no confirmation needed)
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum number of times a hint is shown before it disappears
MAX_HINT_COUNT = 3

# Threshold of completed UCs above which hints are suppressed
COMPLETED_UC_THRESHOLD = 5

# Hint texts for each skill
_HINT_TEXTS: dict[str, str] = {
    "prd": (
        "Hint: /prd genera un PRD (Product Requirements Document) estructurado. "
        "El PRD se descompone en US (User Stories) → UC (Use Cases) → AC (Acceptance Criteria). "
        "Cada AC pasa por el Definition Quality Gate que rechaza criterios vagos o no-testables. "
        "Este flujo garantiza que todo lo que se implementa tiene requisitos claros y medibles."
    ),
    "implement": (
        "Hint: /implement ejecuta un plan en modo autopilot. El Orchestrator coordina agentes "
        "especializados (AG-01 a AG-10) que implementan, testean y validan. Cada fase pasa por "
        "quality gates con veredicto GO/NO-GO. Al final, AG-09 ejecuta acceptance tests y solo "
        "si pasan se crea el PR. Si algo falla, el protocolo de self-healing intenta reparar."
    ),
    "plan": (
        "Hint: /plan genera un plan tecnico detallado por UC (Use Case). Incluye fases de "
        "implementacion, dependencias, y genera diseños visuales con Stitch si el proyecto "
        "tiene UI. El plan es el input que /implement consume para ejecutar autonomamente."
    ),
    "feedback": (
        "Hint: /feedback captura resultados de testing manual del desarrollador. Crea evidencia "
        "local (FB-NNN.json) y un GitHub issue. Feedback de severidad critical/major bloquea "
        "el merge y puede invalidar el veredicto de acceptance de AG-09b."
    ),
    "quality-gate": (
        "Hint: /quality-gate verifica que el codigo cumple los umbrales de calidad definidos "
        "en el baseline del proyecto. Incluye lint (zero-tolerance), coverage (ratchet — solo "
        "puede subir), y tests (no-regression). Es la ultima barrera antes del merge."
    ),
}


def _read_counters(project_path: Path) -> dict[str, int]:
    """Read hint counters from .quality/hint_counters.json."""
    counters_file = project_path / ".quality" / "hint_counters.json"
    if not counters_file.exists():
        return {}
    try:
        data = json.loads(counters_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}
        return {}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _write_counters(project_path: Path, counters: dict[str, int]) -> None:
    """Write hint counters to .quality/hint_counters.json."""
    quality_dir = project_path / ".quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    counters_file = quality_dir / "hint_counters.json"
    try:
        counters_file.write_text(
            json.dumps(counters, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("Failed to write hint counters: %s", e)


def _count_completed_ucs(project_path: Path) -> int:
    """Count completed UCs by scanning .quality/evidence/*/checkpoint.json files.

    A UC is considered completed if its checkpoint.json has status 'complete'
    and represents a final phase.
    """
    evidence_dir = project_path / ".quality" / "evidence"
    if not evidence_dir.exists():
        return 0

    count = 0
    try:
        for feature_dir in evidence_dir.iterdir():
            if not feature_dir.is_dir():
                continue
            checkpoint = feature_dir / "checkpoint.json"
            if checkpoint.exists():
                try:
                    data = json.loads(checkpoint.read_text(encoding="utf-8"))
                    if data.get("status") == "complete":
                        count += 1
                except (json.JSONDecodeError, OSError):
                    continue
    except OSError:
        pass

    return count


def should_show_hint(project_path: str, skill_name: str) -> bool:
    """Check whether a hint should be shown for the given skill.

    Returns False if:
    - The skill has no hint text defined
    - The hint has been shown >= MAX_HINT_COUNT times
    - The project has > COMPLETED_UC_THRESHOLD completed UCs
    """
    if skill_name not in _HINT_TEXTS:
        return False

    pp = Path(project_path)
    if not pp.exists():
        return False

    # AC-24: No hints if project has > 5 completed UCs
    if _count_completed_ucs(pp) > COMPLETED_UC_THRESHOLD:
        return False

    # AC-23: Disappear after 3 uses
    counters = _read_counters(pp)
    current_count = counters.get(skill_name, 0)
    return current_count < MAX_HINT_COUNT


def record_hint_shown(project_path: str, skill_name: str) -> None:
    """Record that a hint was shown for the given skill, incrementing the counter."""
    pp = Path(project_path)
    counters = _read_counters(pp)
    counters[skill_name] = counters.get(skill_name, 0) + 1
    _write_counters(pp, counters)


def get_hint_text(skill_name: str) -> str:
    """Return the hint text for a skill, or empty string if none defined."""
    return _HINT_TEXTS.get(skill_name, "")


def get_available_hints() -> list[str]:
    """Return list of skill names that have hints defined."""
    return sorted(_HINT_TEXTS.keys())
