/**
 * security.mjs — SAST + dependency audit + secret scan + IaC.
 * Port of server/audit/analyzers/security.py (UC-663).
 *
 * External tools (all optional; missing → reported in toolsUsed, never abort):
 * semgrep (OWASP Top 10), gitleaks (secrets), pip-audit/npm audit (deps),
 * checkov (IaC, only if markers present).
 *
 * Returns { result, toolsUsed } — toolsUsed is collected by the orchestrator
 * into the report's top-level tools_used (mirrors BaseAnalyzer.record_tool).
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding, toolUsage,
} from '../lib/schema.mjs';
import { scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { runTool, detectVersion } from '../lib/tool-runner.mjs';
import { walkFiles, ext, exists } from '../lib/fs-scan.mjs';

export const characteristic = SquareCharacteristic.SECURITY;

const SEMGREP_SEVERITY_MAP = {
  ERROR: Severity.HIGH,
  WARNING: Severity.MEDIUM,
  INFO: Severity.LOW,
};

export function analyze(ctx) {
  const root = ctx.root;
  const findings = [];
  const raw = {};
  const toolsUsed = [];

  runSemgrep(root, findings, raw, toolsUsed);
  runGitleaks(root, findings, raw, toolsUsed);
  runDepAudit(ctx, findings, raw, toolsUsed);
  runCheckovIfIac(root, findings, raw, toolsUsed);

  const score = scoreFromFindings(findings, 100.0);

  const result = characteristicResult({
    characteristic, score, traffic_light: trafficLight(score),
    justification:
      `SAST + dependency + secret + IaC scan. ${findings.length} issue(s) `
      + `detected across the stack '${ctx.stack}'. Missing tools are reported `
      + 'in tools_used but do not fail the audit.',
    raw_metrics: raw, findings,
  });
  return { result, toolsUsed };
}

function runSemgrep(root, findings, raw, toolsUsed) {
  const res = runTool(
    ['semgrep', '--config', 'p/owasp-top-ten', '--json', '--quiet', '--error', root],
    { cwd: root, timeout: 240 },
  );
  if (!res.available) {
    toolsUsed.push(toolUsage({ name: 'semgrep', status: 'missing', message: 'install via `pip install semgrep`' }));
    raw.semgrep = 'missing';
    return;
  }
  toolsUsed.push(toolUsage({ name: 'semgrep', status: res.timedOut ? 'timeout' : 'ok', version: detectVersion('semgrep'), stack: 'multi' }));
  raw.semgrep = { returncode: res.returncode };
  if (res.timedOut) return;
  let data;
  try { data = JSON.parse(res.stdout || '{}'); } catch { return; }
  const results = data.results || [];
  raw.semgrep.findings = results.length;
  for (const r of results.slice(0, 50)) {
    const extra = r.extra || {};
    const sev = String(extra.severity || 'INFO').toUpperCase();
    const cweList = (extra.metadata && extra.metadata.cwe) || [];
    const cwe = Array.isArray(cweList) && cweList.length ? cweList[0] : null;
    findings.push(finding({
      severity: SEMGREP_SEVERITY_MAP[sev] || Severity.LOW,
      description: extra.message || r.check_id || 'semgrep finding',
      remediation: (extra.metadata && extra.metadata.fix) || 'Review and patch per OWASP guidance.',
      cwe: cwe ? String(cwe) : null,
      file: r.path,
      line: r.start && r.start.line,
      source_tool: 'semgrep',
    }));
  }
}

function runGitleaks(root, findings, raw, toolsUsed) {
  const res = runTool(
    ['gitleaks', 'detect', '--no-banner', '--report-format', 'json', '--report-path', '-', '--source', root],
    { cwd: root, timeout: 120 },
  );
  if (!res.available) {
    toolsUsed.push(toolUsage({ name: 'gitleaks', status: 'missing', message: 'install via https://github.com/gitleaks/gitleaks' }));
    raw.gitleaks = 'missing';
    return;
  }
  toolsUsed.push(toolUsage({ name: 'gitleaks', status: res.timedOut ? 'timeout' : 'ok', version: detectVersion('gitleaks', 'version'), stack: 'multi' }));
  raw.gitleaks = { returncode: res.returncode };
  if (res.timedOut || !res.stdout) return;
  let leaks;
  try { leaks = JSON.parse(res.stdout); } catch { return; }
  if (Array.isArray(leaks)) {
    raw.gitleaks.leaks = leaks.length;
    for (const leak of leaks.slice(0, 20)) {
      findings.push(finding({
        severity: Severity.CRITICAL,
        description: `Secret detected: ${leak.Description || 'unknown'}`,
        remediation: 'Rotate the secret immediately and purge from git history.',
        file: leak.File,
        line: leak.StartLine,
        source_tool: 'gitleaks',
      }));
    }
  }
}

function runDepAudit(ctx, findings, raw, toolsUsed) {
  const root = ctx.root;
  const isStack = (...n) => n.map((s) => s.toLowerCase()).includes((ctx.stack || '').toLowerCase());
  if (isStack('python') || exists(root, 'pyproject.toml') || exists(root, 'requirements.txt')) {
    runPipAudit(root, findings, raw, toolsUsed);
  }
  if (isStack('react', 'node', 'typescript') || exists(root, 'package.json')) {
    runNpmAudit(root, findings, raw, toolsUsed);
  }
}

function runPipAudit(root, findings, raw, toolsUsed) {
  const res = runTool(['pip-audit', '--format', 'json'], { cwd: root, timeout: 120 });
  if (!res.available) {
    toolsUsed.push(toolUsage({ name: 'pip-audit', status: 'missing', message: 'install via `pip install pip-audit`' }));
    raw.pip_audit = 'missing';
    return;
  }
  toolsUsed.push(toolUsage({ name: 'pip-audit', status: 'ok', version: detectVersion('pip-audit'), stack: 'python' }));
  raw.pip_audit = { returncode: res.returncode };
  let data;
  try { data = JSON.parse(res.stdout || '[]'); } catch { return; }
  const vulns = Array.isArray(data) ? data : (data.dependencies || []);
  let vulnCount = 0;
  for (const entry of vulns) {
    const vs = entry.vulns || entry.vulnerabilities || [];
    for (const v of vs) {
      vulnCount += 1;
      findings.push(finding({
        severity: Severity.HIGH,
        description: `Vulnerable dep ${entry.name}@${entry.version}: ${v.id || 'CVE'}`,
        remediation: `Upgrade to ${(v.fix_versions || []).join(', ') || 'patched version'}.`,
        cwe: v.id,
        source_tool: 'pip-audit',
      }));
    }
  }
  raw.pip_audit.vulns = vulnCount;
}

function runNpmAudit(root, findings, raw, toolsUsed) {
  const res = runTool(['npm', 'audit', '--json'], { cwd: root, timeout: 120 });
  if (!res.available) {
    toolsUsed.push(toolUsage({ name: 'npm', status: 'missing', message: 'install Node/npm' }));
    raw.npm_audit = 'missing';
    return;
  }
  toolsUsed.push(toolUsage({ name: 'npm-audit', status: 'ok', version: detectVersion('npm'), stack: 'node' }));
  let data;
  try { data = JSON.parse(res.stdout || '{}'); } catch { return; }
  const meta = (data.metadata && data.metadata.vulnerabilities) || {};
  raw.npm_audit = meta;
  for (const [level, severity] of [
    ['critical', Severity.CRITICAL], ['high', Severity.HIGH],
    ['moderate', Severity.MEDIUM], ['low', Severity.LOW],
  ]) {
    const count = Number(meta[level] || 0);
    if (count) {
      findings.push(finding({
        severity,
        description: `${count} ${level} vulnerability(ies) in npm dependencies.`,
        remediation: 'Run `npm audit fix`, then review remaining advisories manually.',
        source_tool: 'npm-audit',
      }));
    }
  }
}

function runCheckovIfIac(root, findings, raw, toolsUsed) {
  const iacMarkers = ['.tf', 'Dockerfile', 'docker-compose.yml', 'k8s', 'cloudformation'];
  let found = false;
  for (const abs of walkFiles(root)) {
    const base = abs.split('/').pop();
    if (iacMarkers.some((m) => abs.endsWith(m) || base.includes(m))) { found = true; break; }
  }
  if (!found) return;
  const res = runTool(['checkov', '-d', root, '-o', 'json', '--quiet'], { timeout: 180 });
  if (!res.available) {
    toolsUsed.push(toolUsage({ name: 'checkov', status: 'missing', message: 'install via `pip install checkov`' }));
    raw.checkov = 'missing';
    return;
  }
  toolsUsed.push(toolUsage({ name: 'checkov', status: res.timedOut ? 'timeout' : 'ok', version: detectVersion('checkov'), stack: 'iac' }));
  let data;
  try { data = JSON.parse(res.stdout || '{}'); } catch { return; }
  let failed = 0;
  if (data && typeof data === 'object') {
    const results = (data.results && data.results.failed_checks) || [];
    failed = results.length;
    for (const f of results.slice(0, 20)) {
      findings.push(finding({
        severity: Severity.MEDIUM,
        description: `IaC misconfig: ${f.check_name || f.check_id}`,
        remediation: f.guideline || 'Review IaC resource per CIS benchmark.',
        file: f.file_path,
        line: (f.file_line_range || [null])[0],
        source_tool: 'checkov',
      }));
    }
  }
  raw.checkov = { failed_checks: failed };
}
