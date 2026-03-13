"""Tools for standalone acceptance checking — BDD exportable module (US-04).

Provides two MCP tools:
  - run_acceptance_check: Run acceptance validation for a UC/US against a project
  - get_acceptance_report: Retrieve the last acceptance report for a UC
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP


def register_acceptance_tools(mcp: FastMCP, engine_path: Path, state_path: Path):

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _find_prd_files(project_path: Path) -> list[Path]:
        """Search for PRD markdown files in common locations."""
        candidates: list[Path] = []
        for subdir in ("doc/prd", "doc/prds"):
            d = project_path / subdir
            if d.is_dir():
                candidates.extend(d.glob("*.md"))
        # Also check root-level PRD files
        candidates.extend(project_path.glob("*.prd.md"))
        candidates.extend(project_path.glob("PRD*.md"))
        return sorted(candidates)

    def _extract_ac_from_prd(prd_text: str, item_id: str) -> list[dict]:
        """Extract acceptance criteria lines for a UC or US from PRD text.

        Returns list of {"ac_id": "AC-XX", "description": "..."}.
        """
        criteria: list[dict] = []
        # Match lines like "- AC-01: description" or "- AC-01 description"
        ac_pattern = re.compile(r"-\s*(AC-\d+)[:\s]+(.+)", re.IGNORECASE)

        # Determine the section to search in
        item_upper = item_id.upper()
        in_section = False
        section_depth = 0

        for line in prd_text.splitlines():
            stripped = line.strip()

            # Detect heading level
            heading_match = re.match(r"^(#{1,6})\s+", line)
            if heading_match:
                level = len(heading_match.group(1))
                # Check if this heading contains our item_id
                if item_upper in stripped.upper():
                    in_section = True
                    section_depth = level
                    continue
                # If we hit a heading at same or higher level, leave section
                if in_section and level <= section_depth:
                    in_section = False
                    continue

            if in_section:
                m = ac_pattern.match(stripped)
                if m:
                    criteria.append({
                        "ac_id": m.group(1).upper(),
                        "description": m.group(2).strip(),
                    })

        return criteria

    def _find_ucs_for_us(prd_text: str, us_id: str) -> list[str]:
        """Find all UC-XXX identifiers under a US-XX section."""
        uc_pattern = re.compile(r"(UC-\d+)", re.IGNORECASE)
        us_upper = us_id.upper()
        in_section = False
        section_depth = 0
        ucs: list[str] = []

        for line in prd_text.splitlines():
            heading_match = re.match(r"^(#{1,6})\s+", line)
            if heading_match:
                level = len(heading_match.group(1))
                if us_upper in line.upper():
                    in_section = True
                    section_depth = level
                    continue
                if in_section and level <= section_depth:
                    in_section = False
                    continue

            if in_section:
                for m in uc_pattern.finditer(line):
                    uc_id = m.group(1).upper()
                    if uc_id not in ucs:
                        ucs.append(uc_id)

        return ucs

    def _search_evidence(project_path: Path, ac_id: str, description: str) -> list[str]:
        """Search the project codebase for evidence of AC implementation.

        Returns list of evidence strings like 'file.py:42'.
        """
        evidence: list[str] = []
        # Source extensions to search
        extensions = ("*.py", "*.dart", "*.ts", "*.tsx", "*.jsx", "*.js")

        # 1. Direct AC-XX reference in code/tests
        for ext in extensions:
            for f in project_path.rglob(ext):
                # Skip hidden dirs, node_modules, .venv, etc.
                parts = f.parts
                if any(p.startswith(".") or p in ("node_modules", "__pycache__", ".venv", "venv")
                       for p in parts):
                    continue
                try:
                    content = f.read_text(errors="ignore")
                    for i, line in enumerate(content.splitlines(), 1):
                        if ac_id.upper() in line.upper():
                            rel = f.relative_to(project_path)
                            evidence.append(f"{rel}:{i}")
                except (OSError, UnicodeDecodeError):
                    continue

        # 2. Search for keywords from description in test files
        keywords = _extract_keywords(description)
        if keywords:
            test_dirs = [
                project_path / "tests",
                project_path / "test",
                project_path / "tests/acceptance",
                project_path / "test/acceptance",
            ]
            for test_dir in test_dirs:
                if not test_dir.is_dir():
                    continue
                for ext in extensions:
                    for f in test_dir.rglob(ext):
                        try:
                            content = f.read_text(errors="ignore").lower()
                            if any(kw in content for kw in keywords):
                                rel = f.relative_to(project_path)
                                ev = f"{rel} (keyword match)"
                                if ev not in evidence:
                                    evidence.append(ev)
                        except (OSError, UnicodeDecodeError):
                            continue

        # 3. Check existing acceptance evidence
        evidence_dir = project_path / ".quality" / "evidence"
        if evidence_dir.is_dir():
            for f in evidence_dir.rglob("acceptance-*.json"):
                try:
                    data = json.loads(f.read_text())
                    if isinstance(data, dict):
                        criteria = data.get("criteria", [])
                        for c in criteria:
                            if c.get("ac_id", "").upper() == ac_id.upper():
                                rel = f.relative_to(project_path)
                                evidence.append(f"{rel} (prior acceptance)")
                except (json.JSONDecodeError, OSError):
                    continue

        return evidence

    def _extract_keywords(description: str) -> list[str]:
        """Extract meaningful keywords from an AC description for search."""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "with", "for", "from", "that", "this", "these", "those",
            "and", "but", "or", "not", "no", "if", "when", "where",
            "how", "what", "which", "who", "whom", "whose", "why",
            "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "than", "too", "very", "just",
            "el", "la", "los", "las", "un", "una", "de", "del", "en",
            "con", "por", "para", "que", "como", "se", "su", "al",
            "es", "son", "y", "o", "no", "si", "puede", "debe",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", description.lower())
        return [w for w in words if w not in stop_words][:5]

    def _determine_verdict(evidence: list[str]) -> tuple[str, str]:
        """Determine verdict for a single AC based on evidence found.

        Returns (verdict, reason).
        """
        if not evidence:
            return "REJECTED", "No implementation evidence found"

        has_test = any("test" in e.lower() or "acceptance" in e.lower() for e in evidence)
        has_code = any("test" not in e.lower() for e in evidence)

        if has_code and has_test:
            return "ACCEPTED", "Implementation and test evidence found"
        if has_code:
            return "CONDITIONAL", "Implementation found but missing test coverage"
        if has_test:
            return "CONDITIONAL", "Test references found but implementation unclear"
        return "CONDITIONAL", "Evidence found but manual verification recommended"

    def _generate_gherkin(ac: dict, uc_id: str) -> str:
        """Generate a Gherkin .feature file content for an AC."""
        ac_id = ac["ac_id"]
        desc = ac["description"]
        return (
            f"# language: es\n"
            f"@acceptance @{uc_id} @{ac_id}\n"
            f"Caracteristica: {desc}\n"
            f"\n"
            f"  Como validacion automatica del criterio {ac_id}\n"
            f"  Necesito verificar que el codigo cumple: {desc}\n"
            f"\n"
            f"  Escenario: {desc}\n"
            f"    Dado que el sistema esta en estado inicial\n"
            f"    Cuando se ejecuta la funcionalidad descrita en {ac_id}\n"
            f"    Entonces se cumple que {desc}\n"
        )

    def _get_git_info(project_path: Path) -> dict:
        """Get current branch and commit from git."""
        info = {"branch": "unknown", "commit": "unknown"}
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(project_path), capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                info["branch"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(project_path), capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                info["commit"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return info

    def _get_pr_changed_files(project_path: Path, branch: str) -> list[str]:
        """Get files changed in the current branch vs main."""
        base = "main"
        try:
            result = subprocess.run(
                ["git", "diff", f"{base}...{branch}", "--name-only"],
                cwd=str(project_path), capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return [f for f in result.stdout.strip().splitlines() if f]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return []

    def _log_execution(project_path: Path, uc_id: str, verdict: str, git_info: dict):
        """Append execution log entry to .quality/logs/acceptance-check.jsonl."""
        logs_dir = project_path / ".quality" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "acceptance-check.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uc_id": uc_id,
            "verdict": verdict,
            "branch": git_info.get("branch", "unknown"),
            "commit": git_info.get("commit", "unknown"),
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------
    # MCP Tools
    # -------------------------------------------------------------------

    @mcp.tool
    def run_acceptance_check(
        project_path: str,
        item_id: str = "",
        branch: str = "",
    ) -> dict:
        """Run standalone acceptance check for a UC or US against a project.

        Locates the PRD, extracts acceptance criteria, generates Gherkin .feature
        files, validates each AC against the codebase, and produces a verdict.

        Args:
            project_path: Absolute path to the project root.
            item_id: UC-XXX, US-XX, or empty. If empty, checks all UCs found in PRDs.
            branch: Git branch to check (used for PR-focused diff). Empty = current branch.

        Returns:
            JSON with verdict (ACCEPTED/CONDITIONAL/REJECTED), per-AC results,
            generated .feature file paths, and a PR-comment-ready Markdown report.
        """
        pp = Path(project_path).resolve()
        if not pp.is_dir():
            return {"error": f"Project path does not exist: {project_path}"}

        # Git info
        git_info = _get_git_info(pp)
        if branch:
            git_info["branch"] = branch

        timestamp = datetime.now(timezone.utc).isoformat()

        # Find PRD files
        prd_files = _find_prd_files(pp)
        if not prd_files:
            return {
                "error": "No PRD files found",
                "searched": ["doc/prd/", "doc/prds/", "*.prd.md", "PRD*.md"],
                "hint": "Create a PRD with AC-XX definitions in doc/prd/",
            }

        # Read all PRD content
        prd_text = ""
        for prd_file in prd_files:
            try:
                prd_text += "\n" + prd_file.read_text(encoding="utf-8")
            except OSError:
                continue

        if not prd_text.strip():
            return {"error": "PRD files found but could not be read"}

        # Determine which UCs to check
        uc_ids_to_check: list[str] = []
        item_id_upper = item_id.upper().strip() if item_id else ""

        if item_id_upper.startswith("US-"):
            # Find all UCs under this US
            ucs = _find_ucs_for_us(prd_text, item_id_upper)
            if not ucs:
                return {
                    "error": f"No UCs found for {item_id_upper} in PRD",
                    "hint": "Ensure the PRD has UC-XXX references under the US section",
                }
            uc_ids_to_check = ucs
        elif item_id_upper.startswith("UC-"):
            uc_ids_to_check = [item_id_upper]
        elif item_id_upper == "" or item_id_upper.startswith("PR-") or item_id_upper.startswith("--PR"):
            # Try to find all UCs in the PRD
            all_ucs = re.findall(r"(UC-\d+)", prd_text, re.IGNORECASE)
            uc_ids_to_check = list(dict.fromkeys(uc.upper() for uc in all_ucs))
            if not uc_ids_to_check:
                return {
                    "error": "No UC identifiers found in PRD files",
                    "hint": "PRD should contain UC-XXX sections with AC-XX criteria",
                }
        else:
            # Try both UC and US interpretation
            if re.match(r"\d+$", item_id_upper):
                return {
                    "error": f"Ambiguous item_id '{item_id}'. Use UC-{item_id} or US-{item_id}",
                }
            uc_ids_to_check = [item_id_upper]

        # Get changed files for PR-focused mode (AC-49)
        if branch:
            _get_pr_changed_files(pp, branch)  # validates branch exists

        # Process each UC
        all_results: list[dict] = []
        all_features: list[str] = []

        for uc_id in uc_ids_to_check:
            criteria = _extract_ac_from_prd(prd_text, uc_id)
            if not criteria:
                all_results.append({
                    "uc_id": uc_id,
                    "error": f"No acceptance criteria found for {uc_id}",
                    "verdict": "REJECTED",
                    "criteria": [],
                })
                continue

            # Create output directory
            out_dir = pp / ".quality" / "acceptance-check" / uc_id
            out_dir.mkdir(parents=True, exist_ok=True)

            uc_criteria_results: list[dict] = []
            uc_features: list[str] = []

            for ac in criteria:
                ac_id = ac["ac_id"]
                desc = ac["description"]

                # Generate Gherkin feature
                feature_content = _generate_gherkin(ac, uc_id)
                feature_path = out_dir / f"{ac_id}.feature"
                feature_path.write_text(feature_content, encoding="utf-8")
                uc_features.append(str(feature_path.relative_to(pp)))

                # Search for evidence
                evidence = _search_evidence(pp, ac_id, desc)
                verdict, reason = _determine_verdict(evidence)

                uc_criteria_results.append({
                    "ac_id": ac_id,
                    "description": desc,
                    "verdict": verdict,
                    "reason": reason,
                    "evidence": evidence[:10],  # Limit evidence entries
                })

            # Determine UC-level verdict
            verdicts = [c["verdict"] for c in uc_criteria_results]
            if all(v == "ACCEPTED" for v in verdicts):
                uc_verdict = "ACCEPTED"
            elif any(v == "REJECTED" for v in verdicts):
                uc_verdict = "REJECTED"
            else:
                uc_verdict = "CONDITIONAL"

            # Save JSON report
            report = {
                "uc_id": uc_id,
                "timestamp": timestamp,
                "branch": git_info["branch"],
                "commit": git_info["commit"],
                "verdict": uc_verdict,
                "criteria": uc_criteria_results,
                "features_generated": uc_features,
            }
            report_json_path = out_dir / "report.json"
            report_json_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Save Markdown report (PR-comment-ready)
            md_lines = [
                f"## Acceptance Check: {uc_id}\n",
                f"**Branch**: {git_info['branch']}",
                f"**Commit**: {git_info['commit']}",
                f"**Date**: {timestamp}",
                f"**Verdict**: **{uc_verdict}**\n",
                "### Criteria Results\n",
                "| AC | Description | Verdict | Evidence |",
                "|----|-------------|---------|----------|",
            ]
            for c in uc_criteria_results:
                ev_str = ", ".join(f"`{e}`" for e in c["evidence"][:3]) if c["evidence"] else "No evidence"
                md_lines.append(
                    f"| {c['ac_id']} | {c['description'][:60]} | {c['verdict']} | {ev_str} |"
                )

            md_lines.append("\n### Details\n")
            for c in uc_criteria_results:
                md_lines.append(f"#### {c['ac_id']}: {c['description']}")
                md_lines.append(f"**Verdict**: {c['verdict']}")
                md_lines.append(f"**Reason**: {c['reason']}")
                if c["evidence"]:
                    md_lines.append("**Evidence**:")
                    for e in c["evidence"][:5]:
                        md_lines.append(f"- `{e}`")
                md_lines.append("")

            md_lines.append("---")
            md_lines.append("*Generated by SDD-JPS Engine `/acceptance-check`*")

            report_md_path = out_dir / "report.md"
            report_md_path.write_text("\n".join(md_lines), encoding="utf-8")

            # Log execution
            _log_execution(pp, uc_id, uc_verdict, git_info)

            all_results.append(report)
            all_features.extend(uc_features)

        # Overall verdict across all UCs
        all_verdicts = [r.get("verdict", "REJECTED") for r in all_results]
        if all(v == "ACCEPTED" for v in all_verdicts):
            overall_verdict = "ACCEPTED"
        elif any(v == "REJECTED" for v in all_verdicts):
            overall_verdict = "REJECTED"
        else:
            overall_verdict = "CONDITIONAL"

        return {
            "verdict": overall_verdict,
            "timestamp": timestamp,
            "branch": git_info["branch"],
            "commit": git_info["commit"],
            "uc_results": all_results,
            "features_generated": all_features,
            "total_criteria": sum(len(r.get("criteria", [])) for r in all_results),
            "reports": [
                str((pp / ".quality" / "acceptance-check" / uc / "report.md").relative_to(pp))
                for uc in uc_ids_to_check
                if (pp / ".quality" / "acceptance-check" / uc / "report.md").exists()
            ],
        }

    @mcp.tool
    def get_acceptance_report(
        project_path: str,
        uc_id: str,
    ) -> dict:
        """Get the last acceptance check report for a UC.

        Args:
            project_path: Absolute path to the project root.
            uc_id: Use case identifier (e.g., UC-001).

        Returns:
            The last report JSON, or error if no report exists.
            Includes verdict, per-AC results, evidence, and generated .feature paths.
        """
        pp = Path(project_path).resolve()
        uc_upper = uc_id.upper().strip()

        if not pp.is_dir():
            return {"error": f"Project path does not exist: {project_path}"}

        # Check .quality/acceptance-check/{uc_id}/report.json
        report_file = pp / ".quality" / "acceptance-check" / uc_upper / "report.json"
        if report_file.exists():
            try:
                report = json.loads(report_file.read_text(encoding="utf-8"))
                # Also include the markdown report path
                md_path = report_file.parent / "report.md"
                if md_path.exists():
                    report["markdown_report"] = str(md_path.relative_to(pp))
                    report["markdown_content"] = md_path.read_text(encoding="utf-8")
                return report
            except (json.JSONDecodeError, OSError) as exc:
                return {"error": f"Failed to read report: {exc}"}

        # Check .quality/evidence/*/acceptance-report.json as fallback
        evidence_dir = pp / ".quality" / "evidence"
        if evidence_dir.is_dir():
            for feature_dir in evidence_dir.iterdir():
                if not feature_dir.is_dir():
                    continue
                ar = feature_dir / "acceptance-report.json"
                if ar.exists():
                    try:
                        data = json.loads(ar.read_text(encoding="utf-8"))
                        if isinstance(data, dict) and uc_upper in json.dumps(data).upper():
                            data["_source"] = str(ar.relative_to(pp))
                            return data
                    except (json.JSONDecodeError, OSError):
                        continue

        # List available reports
        check_dir = pp / ".quality" / "acceptance-check"
        available: list[str] = []
        if check_dir.is_dir():
            available = [
                d.name for d in check_dir.iterdir()
                if d.is_dir() and (d / "report.json").exists()
            ]

        return {
            "error": f"No acceptance report found for {uc_upper}",
            "available_reports": available,
            "hint": "Run `run_acceptance_check` first to generate a report",
        }
