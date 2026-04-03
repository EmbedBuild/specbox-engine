"""Benchmark generator — aggregates metrics from state data for public benchmarking.

Reads project state (sessions, healing, acceptance validations, checkpoints)
and produces anonymized, aggregated metrics suitable for public display.

AC-59: Aggregated Markdown with total UCs, coverage avg, healing rate,
       acceptance rate, time per UC, delta_count average.
AC-60: Project names anonymized as "Proyecto A", "Proyecto B", etc.
AC-61: Includes "Metodología" section explaining calculations.
AC-62: File generated at docs/benchmarks/snapshot_{date}.md
"""

import json
import string
from datetime import datetime, timezone
from pathlib import Path


def _read_registry(state_path: Path) -> dict:
    """Read state/registry.json, returning empty structure if missing."""
    registry_file = state_path / "registry.json"
    if registry_file.exists():
        try:
            return json.loads(registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": {}}


def _read_jsonl(file_path: Path) -> list[dict]:
    """Read all records from a JSONL file."""
    records: list[dict] = []
    if not file_path.exists():
        return records
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _read_meta(project_dir: Path) -> dict:
    """Read meta.json for a project."""
    meta_file = project_dir / "meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def anonymize_project_name(index: int) -> str:
    """Return 'Proyecto A', 'Proyecto B', ..., 'Proyecto Z', 'Proyecto AA', etc."""
    if index < 26:
        return f"Proyecto {string.ascii_uppercase[index]}"
    # For > 26 projects, use AA, AB, etc.
    first = string.ascii_uppercase[index // 26 - 1]
    second = string.ascii_uppercase[index % 26]
    return f"Proyecto {first}{second}"


def _categorize_stack(stack: str) -> str:
    """Map specific stack names to generic categories (AC-60)."""
    stack_lower = (stack or "unknown").lower()
    categories = {
        "flutter": "Mobile/Desktop (Flutter)",
        "react": "Web Frontend (React)",
        "go": "Backend (Go)",
        "golang": "Backend (Go)",
        "python": "Backend (Python)",
        "fastapi": "Backend (Python)",
        "google-apps-script": "Automation (Apps Script)",
        "gas": "Automation (Apps Script)",
    }
    return categories.get(stack_lower, "Other")


def generate_benchmark(state_path: Path, engine_version: str) -> dict:
    """Aggregate metrics from all projects in state.

    Returns dict with: total_ucs, projects (anonymized), coverage_avg,
    healing_resolution_rate, acceptance_rate, avg_time_per_uc,
    delta_count_avg, generated_at, engine_version.
    """
    registry = _read_registry(state_path)
    projects_raw = registry.get("projects", {})

    if not projects_raw:
        return {
            "total_projects": 0,
            "total_ucs": 0,
            "projects": [],
            "coverage_avg": 0.0,
            "healing_resolution_rate": 0.0,
            "acceptance_rate": 0.0,
            "avg_time_per_uc_hours": 0.0,
            "delta_count_avg": 0.0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine_version": engine_version,
        }

    project_metrics: list[dict] = []
    total_ucs = 0
    all_healing_total = 0
    all_healing_resolved = 0
    all_validations = 0
    all_accepted = 0
    all_delta_counts: list[int] = []
    all_uc_durations: list[float] = []

    for idx, (proj_name, proj_info) in enumerate(sorted(projects_raw.items())):
        project_dir = state_path / "projects" / proj_name
        if not project_dir.exists():
            continue

        meta = _read_meta(project_dir)
        sessions = _read_jsonl(project_dir / "sessions.jsonl")
        healing = _read_jsonl(project_dir / "healing.jsonl")
        validations = _read_jsonl(project_dir / "acceptance_validations.jsonl")
        checkpoints = _read_jsonl(project_dir / "checkpoints.jsonl")

        # UC count from meta or checkpoints
        uc_count = meta.get("uc_count", 0)
        if uc_count == 0:
            # Fallback: count unique UCs from checkpoints
            uc_ids = {c.get("uc_id") for c in checkpoints if c.get("uc_id")}
            uc_count = len(uc_ids)
        total_ucs += uc_count

        # Healing resolution rate
        healing_resolved = sum(1 for h in healing if h.get("result") == "resolved")
        all_healing_total += len(healing)
        all_healing_resolved += healing_resolved

        # Acceptance rate
        proj_accepted = sum(1 for v in validations if v.get("verdict") == "ACCEPTED")
        all_validations += len(validations)
        all_accepted += proj_accepted

        # Delta counts from sessions
        for s in sessions:
            dc = s.get("delta_count", s.get("files_modified", 0))
            if dc:
                all_delta_counts.append(dc)

        # Time per UC: estimate from checkpoints (start→complete timestamps)
        uc_starts: dict[str, str] = {}
        uc_ends: dict[str, str] = {}
        for cp in checkpoints:
            uc_id = cp.get("uc_id", "")
            ts = cp.get("timestamp", "")
            phase = cp.get("phase", "")
            if uc_id and ts:
                if phase in ("start", "1", "Phase 1") or uc_id not in uc_starts:
                    if uc_id not in uc_starts or ts < uc_starts[uc_id]:
                        uc_starts[uc_id] = ts
                if uc_id not in uc_ends or ts > uc_ends[uc_id]:
                    uc_ends[uc_id] = ts

        for uid in uc_starts:
            if uid in uc_ends and uc_starts[uid] != uc_ends[uid]:
                try:
                    start = datetime.fromisoformat(uc_starts[uid])
                    end = datetime.fromisoformat(uc_ends[uid])
                    hours = (end - start).total_seconds() / 3600
                    if 0 < hours < 720:  # Cap at 30 days to filter outliers
                        all_uc_durations.append(hours)
                except (ValueError, TypeError):
                    pass

        # Coverage from meta
        coverage = meta.get("coverage", None)

        stack = proj_info.get("stack", meta.get("stack", "unknown"))

        project_metrics.append({
            "name": anonymize_project_name(idx),
            "stack_category": _categorize_stack(stack),
            "uc_count": uc_count,
            "sessions": len(sessions),
            "healing_events": len(healing),
            "healing_resolved": healing_resolved,
            "healing_rate": round(healing_resolved / len(healing) * 100, 1) if healing else 100.0,
            "validations": len(validations),
            "accepted": proj_accepted,
            "acceptance_rate": round(proj_accepted / len(validations) * 100, 1) if validations else 0.0,
            "coverage": coverage,
        })

    coverage_values = [p["coverage"] for p in project_metrics if p["coverage"] is not None]
    coverage_avg = round(sum(coverage_values) / len(coverage_values), 1) if coverage_values else 0.0

    healing_rate = round(all_healing_resolved / all_healing_total * 100, 1) if all_healing_total else 100.0
    acceptance_rate = round(all_accepted / all_validations * 100, 1) if all_validations else 0.0
    avg_time = round(sum(all_uc_durations) / len(all_uc_durations), 2) if all_uc_durations else 0.0
    delta_avg = round(sum(all_delta_counts) / len(all_delta_counts), 1) if all_delta_counts else 0.0

    return {
        "total_projects": len(project_metrics),
        "total_ucs": total_ucs,
        "projects": project_metrics,
        "coverage_avg": coverage_avg,
        "healing_resolution_rate": healing_rate,
        "acceptance_rate": acceptance_rate,
        "avg_time_per_uc_hours": avg_time,
        "delta_count_avg": delta_avg,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": engine_version,
    }


def render_benchmark_markdown(metrics: dict) -> str:
    """Render metrics as publishable Markdown with Metodología section (AC-61)."""
    lines: list[str] = []
    generated = metrics.get("generated_at", "unknown")
    version = metrics.get("engine_version", "unknown")

    lines.append("# SpecBox Engine — Benchmark Snapshot")
    lines.append("")
    lines.append(f"> Generado: {generated}")
    lines.append(f"> Engine version: {version}")
    lines.append("")

    # Summary table
    lines.append("## Resumen Agregado")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Proyectos analizados | {metrics['total_projects']} |")
    lines.append(f"| Total Use Cases (UCs) | {metrics['total_ucs']} |")
    lines.append(f"| Cobertura promedio | {metrics['coverage_avg']}% |")
    lines.append(f"| Tasa de resolución healing | {metrics['healing_resolution_rate']}% |")
    lines.append(f"| Tasa de aceptación | {metrics['acceptance_rate']}% |")
    lines.append(f"| Tiempo promedio por UC | {metrics['avg_time_per_uc_hours']} horas |")
    lines.append(f"| Delta count promedio | {metrics['delta_count_avg']} archivos/sesión |")
    lines.append("")

    # Per-project table
    if metrics.get("projects"):
        lines.append("## Detalle por Proyecto")
        lines.append("")
        lines.append("| Proyecto | Categoría | UCs | Sesiones | Healing Rate | Acceptance Rate | Cobertura |")
        lines.append("|----------|-----------|-----|----------|-------------|-----------------|-----------|")
        for p in metrics["projects"]:
            cov = f"{p['coverage']}%" if p["coverage"] is not None else "N/A"
            lines.append(
                f"| {p['name']} | {p['stack_category']} | {p['uc_count']} | "
                f"{p['sessions']} | {p['healing_rate']}% | "
                f"{p['acceptance_rate']}% | {cov} |"
            )
        lines.append("")

    # Methodology section (AC-61)
    lines.append("## Metodología")
    lines.append("")
    lines.append("Las métricas de este benchmark se calculan de la siguiente forma:")
    lines.append("")
    lines.append("- **Total UCs**: Suma de Use Cases registrados en la metadata de cada proyecto, ")
    lines.append("  o contados desde los checkpoints de implementación si no hay metadata.")
    lines.append("- **Cobertura promedio**: Media aritmética de la cobertura de tests reportada ")
    lines.append("  en `meta.json` de cada proyecto. Solo incluye proyectos con datos de cobertura.")
    lines.append("- **Tasa de resolución healing**: Porcentaje de eventos de self-healing que ")
    lines.append("  se resolvieron automáticamente (resultado = `resolved`) sobre el total de eventos.")
    lines.append("- **Tasa de aceptación**: Porcentaje de validaciones de aceptación (AG-09b) ")
    lines.append("  con veredicto `ACCEPTED` sobre el total de validaciones ejecutadas.")
    lines.append("- **Tiempo promedio por UC**: Calculado desde el primer checkpoint hasta el último ")
    lines.append("  checkpoint de cada UC. Se excluyen duraciones superiores a 30 días (outliers).")
    lines.append("- **Delta count promedio**: Media de archivos modificados por sesión de desarrollo, ")
    lines.append("  tomados del campo `delta_count` o `files_modified` de cada sesión reportada.")
    lines.append("")
    lines.append("**Período**: Todos los datos históricos disponibles en el estado del Engine.")
    lines.append("")
    lines.append("**Anonimización**: Los nombres de proyecto se reemplazan por identificadores ")
    lines.append("genéricos (Proyecto A, B, C...). Solo se muestra la categoría genérica del stack.")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generado automáticamente por SpecBox Engine v{version}*")
    lines.append("")

    return "\n".join(lines)
