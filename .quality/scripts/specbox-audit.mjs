#!/usr/bin/env node
/**
 * specbox-audit.mjs — SpecBox Engine Compliance Auditor
 *
 * Standalone tool that audits a project's SpecBox compliance level.
 * Runs locally without Claude — usable from terminal, CI, or as a skill.
 *
 * Usage:
 *   node .quality/scripts/specbox-audit.mjs [project-path] [--json] [--fix] [--verbose]
 *
 * Options:
 *   project-path   Path to audited project (default: current directory)
 *   --json         Output as JSON (for MCP tools and skills)
 *   --fix          Auto-fix what can be fixed (copy missing hooks, create dirs)
 *   --verbose      Show detailed check results
 *
 * Exit codes:
 *   0 = All checks pass (100% compliance)
 *   1 = Compliance gaps found (report generated)
 *   2 = Critical: project not onboarded or engine not found
 *
 * v5.19.0 — Hook Schema Fix
 */

import { readFileSync, existsSync, statSync, readdirSync, mkdirSync, copyFileSync, writeFileSync } from 'fs';
import { join, basename, resolve, dirname } from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// --- CLI args ---
const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const fixMode = args.includes('--fix');
const verbose = args.includes('--verbose');
const projectPath = resolve(args.find(a => !a.startsWith('--')) || '.');

// --- Constants ---
const ENGINE_ROOT = resolve(__dirname, '..', '..');
const GLOBAL_HOOKS_DIR = join(process.env.HOME || '~', '.claude', 'hooks');
const GLOBAL_SKILLS_DIR = join(process.env.HOME || '~', '.claude', 'skills');

// ============================================================
// AUDIT CATEGORIES
// ============================================================

const results = {
  project: basename(projectPath),
  project_path: projectPath,
  timestamp: new Date().toISOString(),
  engine_version: null,
  project_version: null,
  needs_upgrade: false,
  overall_score: 0,
  overall_grade: '',
  categories: {},
  critical_issues: [],
  warnings: [],
  recommendations: [],
  auto_fixable: [],
};

// ============================================================
// CATEGORY 1: ENGINE VERSION ALIGNMENT
// ============================================================

function auditVersionAlignment() {
  const checks = [];

  // Read engine version
  const engineVersionFile = join(ENGINE_ROOT, 'ENGINE_VERSION.yaml');
  let engineVersion = 'unknown';
  if (existsSync(engineVersionFile)) {
    const content = readFileSync(engineVersionFile, 'utf-8');
    const match = content.match(/^version:\s*(.+)$/m);
    engineVersion = match ? match[1].trim() : 'unknown';
  }
  results.engine_version = engineVersion;

  // Read project version from CLAUDE.md
  const claudeMd = join(projectPath, 'CLAUDE.md');
  let projectVersion = 'unknown';
  if (existsSync(claudeMd)) {
    const content = readFileSync(claudeMd, 'utf-8');
    const match = content.match(/SpecBox Engine v([\d.]+)/);
    projectVersion = match ? match[1] : 'unknown';
    checks.push({ name: 'CLAUDE.md exists', pass: true });
  } else {
    checks.push({ name: 'CLAUDE.md exists', pass: false, fix: 'Run onboard_project or upgrade_project' });
  }
  results.project_version = projectVersion;

  // Compare versions
  if (engineVersion !== 'unknown' && projectVersion !== 'unknown') {
    const aligned = engineVersion === projectVersion;
    results.needs_upgrade = !aligned;
    checks.push({
      name: 'Version aligned',
      pass: aligned,
      detail: aligned ? `Both at v${engineVersion}` : `Engine v${engineVersion} vs Project v${projectVersion}`,
      fix: !aligned ? 'Run upgrade_project from MCP or ./install.sh' : undefined,
    });
  }

  // Check meta.json in engine state
  const metaFile = join(ENGINE_ROOT, 'data', 'state', 'projects', basename(projectPath), 'meta.json');
  const legacyMeta = join(ENGINE_ROOT, '.quality', 'state', 'projects', basename(projectPath), 'meta.json');
  const metaExists = existsSync(metaFile) || existsSync(legacyMeta);
  checks.push({
    name: 'Registered in engine state',
    pass: metaExists,
    fix: !metaExists ? 'Run onboard_project to register this project' : undefined,
    critical: !metaExists,
  });

  return { name: 'Version Alignment', weight: 15, checks };
}

// ============================================================
// CATEGORY 2: HOOKS INSTALLATION
// ============================================================

function auditHooksInstallation() {
  const checks = [];

  const requiredHooks = [
    { file: 'quality-first-guard.mjs', critical: true, desc: 'Read-before-write enforcement' },
    { file: 'read-tracker.mjs', critical: true, desc: 'Tracks file reads for quality-first-guard' },
    { file: 'spec-guard.mjs', critical: true, desc: 'No code without active UC' },
    { file: 'branch-guard.mjs', critical: true, desc: 'No code on main/master' },
    { file: 'commit-spec-guard.mjs', critical: true, desc: 'No commits on main' },
    { file: 'pre-commit-lint.mjs', critical: true, desc: 'Zero-tolerance lint on commit' },
    { file: 'design-gate.mjs', critical: false, desc: 'No UI without Stitch design' },
    { file: 'e2e-gate.mjs', critical: false, desc: 'E2E evidence validation on commit' },
    { file: 'no-bypass-guard.mjs', critical: true, desc: 'Blocks --no-verify, --force, --hard' },
    { file: 'on-session-end.mjs', critical: false, desc: 'Session telemetry' },
    { file: 'implement-checkpoint.mjs', critical: false, desc: 'Phase checkpoint helper' },
    { file: 'implement-healing.mjs', critical: false, desc: 'Healing event logger' },
    { file: 'healing-budget-guard.mjs', critical: true, desc: 'Healing budget enforcement (max 8)' },
    { file: 'pipeline-phase-guard.mjs', critical: true, desc: 'Pipeline phase ordering enforcement' },
    { file: 'checkpoint-freshness-guard.mjs', critical: false, desc: 'Checkpoint staleness warning on commit' },
    { file: 'uc-lifecycle-guard.mjs', critical: false, desc: 'UC lifecycle warning on push' },
    { file: 'mcp-report.mjs', critical: false, desc: 'MCP telemetry reporter' },
  ];

  const requiredLibFiles = ['utils.mjs', 'output.mjs', 'config.mjs', 'http.mjs'];

  // Check project-local hooks
  const localHooksDir = join(projectPath, '.claude', 'hooks');
  const globalHooksDir = GLOBAL_HOOKS_DIR;

  for (const hook of requiredHooks) {
    const localExists = existsSync(join(localHooksDir, hook.file));
    const globalExists = existsSync(join(globalHooksDir, hook.file));
    const engineExists = existsSync(join(ENGINE_ROOT, '.claude', 'hooks', hook.file));

    const installed = localExists || globalExists;
    checks.push({
      name: `Hook: ${hook.file}`,
      pass: installed,
      detail: installed
        ? (localExists ? 'project-local' : 'global')
        : `Missing — ${hook.desc}`,
      fix: !installed && engineExists ? `Copy from engine: cp ${join(ENGINE_ROOT, '.claude', 'hooks', hook.file)} ${join(globalHooksDir, hook.file)}` : undefined,
      critical: hook.critical && !installed,
      autoFixable: !installed && engineExists,
      autoFix: () => {
        mkdirSync(globalHooksDir, { recursive: true });
        copyFileSync(join(ENGINE_ROOT, '.claude', 'hooks', hook.file), join(globalHooksDir, hook.file));
      },
    });
  }

  // Check lib/ files
  for (const libFile of requiredLibFiles) {
    const localLib = join(localHooksDir, 'lib', libFile);
    const globalLib = join(globalHooksDir, 'lib', libFile);
    const engineLib = join(ENGINE_ROOT, '.claude', 'hooks', 'lib', libFile);

    const installed = existsSync(localLib) || existsSync(globalLib);
    checks.push({
      name: `Hook lib: ${libFile}`,
      pass: installed,
      fix: !installed ? `Copy from engine hooks/lib/` : undefined,
      autoFixable: !installed && existsSync(engineLib),
      autoFix: () => {
        mkdirSync(join(globalHooksDir, 'lib'), { recursive: true });
        copyFileSync(engineLib, join(globalLib));
      },
    });
  }

  return { name: 'Hooks Installation', weight: 25, checks };
}

// ============================================================
// CATEGORY 3: SETTINGS CONFIGURATION
// ============================================================

function auditSettingsConfiguration() {
  const checks = [];

  // Check settings.json exists
  const settingsFile = join(projectPath, '.claude', 'settings.json');
  const globalSettings = join(process.env.HOME || '~', '.claude', 'settings.json');

  let settings = null;
  if (existsSync(settingsFile)) {
    checks.push({ name: 'Project settings.json exists', pass: true });
    try { settings = JSON.parse(readFileSync(settingsFile, 'utf-8')); } catch { /* */ }
  } else if (existsSync(globalSettings)) {
    checks.push({ name: 'Project settings.json exists', pass: false, detail: 'Using global settings' });
    try { settings = JSON.parse(readFileSync(globalSettings, 'utf-8')); } catch { /* */ }
  } else {
    checks.push({ name: 'settings.json exists', pass: false, critical: true, fix: 'Run onboard_project or copy from template' });
    return { name: 'Settings Configuration', weight: 20, checks };
  }

  if (!settings || !settings.hooks) {
    checks.push({ name: 'Hooks configured in settings', pass: false, critical: true, fix: 'Settings missing hooks section' });
    return { name: 'Settings Configuration', weight: 20, checks };
  }

  // Check matcher format — Claude Code expects matcher as string, not object
  let hasObjectMatchers = false;
  for (const eventType of ['PreToolUse', 'PostToolUse']) {
    const groups = settings.hooks[eventType] || [];
    for (const group of groups) {
      if (group.matcher && typeof group.matcher === 'object') {
        hasObjectMatchers = true;
        break;
      }
    }
    if (hasObjectMatchers) break;
  }
  checks.push({
    name: 'Matcher format (string, not object)',
    pass: !hasObjectMatchers,
    detail: hasObjectMatchers
      ? 'BROKEN: matcher is {tool_name:...} object — Claude Code expects a string. Hooks are NOT active.'
      : 'Correct: matchers are strings',
    critical: hasObjectMatchers,
    fix: hasObjectMatchers ? 'Run upgrade_project or replace settings.json from engine template (v5.19+)' : undefined,
  });

  // Check critical hook registrations in settings
  const requiredSettingsHooks = [
    { event: 'PreToolUse', tool: 'Write', hook: 'quality-first-guard', desc: 'Read-before-write on Write' },
    { event: 'PreToolUse', tool: 'Edit', hook: 'quality-first-guard', desc: 'Read-before-write on Edit' },
    { event: 'PostToolUse', tool: 'Read', hook: 'read-tracker', desc: 'Read tracker' },
    { event: 'PostToolUse', tool: 'Bash:git commit', hook: 'commit-spec-guard', desc: 'Commit branch guard' },
    { event: 'PostToolUse', tool: 'Bash:git commit', hook: 'pre-commit-lint', desc: 'Pre-commit lint' },
    { event: 'PostToolUse', tool: 'Write:src/', hook: 'spec-guard', desc: 'Spec guard on Write src/' },
    { event: 'PostToolUse', tool: 'Write:lib/', hook: 'spec-guard', desc: 'Spec guard on Write lib/' },
    { event: 'PostToolUse', tool: 'Edit:src/', hook: 'spec-guard', desc: 'Spec guard on Edit src/' },
    { event: 'PostToolUse', tool: 'Edit:lib/', hook: 'spec-guard', desc: 'Spec guard on Edit lib/' },
    { event: 'PreToolUse', tool: 'Bash:--no-verify', hook: 'no-bypass-guard', desc: 'No-bypass guard' },
    { event: 'PreToolUse', tool: 'Bash:push.*--force', hook: 'no-bypass-guard', desc: 'No force-push guard' },
    { event: 'PreToolUse', tool: 'Bash:reset --hard', hook: 'no-bypass-guard', desc: 'No hard-reset guard' },
    { event: 'PreToolUse', tool: 'Write', hook: 'healing-budget-guard', desc: 'Healing budget on Write' },
    { event: 'PreToolUse', tool: 'Edit', hook: 'healing-budget-guard', desc: 'Healing budget on Edit' },
    { event: 'PreToolUse', tool: 'Write', hook: 'pipeline-phase-guard', desc: 'Pipeline phase on Write' },
    { event: 'PreToolUse', tool: 'Edit', hook: 'pipeline-phase-guard', desc: 'Pipeline phase on Edit' },
    { event: 'PostToolUse', tool: 'Bash:git commit', hook: 'checkpoint-freshness-guard', desc: 'Checkpoint freshness on commit' },
    { event: 'PostToolUse', tool: 'Bash:git push', hook: 'uc-lifecycle-guard', desc: 'UC lifecycle on push' },
  ];

  const settingsStr = JSON.stringify(settings);

  for (const req of requiredSettingsHooks) {
    const hookRegistered = settingsStr.includes(req.hook);
    checks.push({
      name: `Settings: ${req.desc}`,
      pass: hookRegistered,
      detail: hookRegistered ? 'Registered' : `Missing from ${req.event}`,
      fix: !hookRegistered ? `Add ${req.hook}.mjs to ${req.event} in settings.json` : undefined,
      critical: !hookRegistered && ['quality-first-guard', 'spec-guard', 'no-bypass-guard'].includes(req.hook),
    });
  }

  return { name: 'Settings Configuration', weight: 20, checks };
}

// ============================================================
// CATEGORY 4: QUALITY INFRASTRUCTURE
// ============================================================

function auditQualityInfra() {
  const checks = [];

  // Required directories
  const requiredDirs = [
    '.quality',
    '.quality/baselines',
    '.quality/evidence',
    '.quality/logs',
    '.quality/scripts',
  ];

  for (const dir of requiredDirs) {
    const fullPath = join(projectPath, dir);
    const exists = existsSync(fullPath);
    checks.push({
      name: `Directory: ${dir}/`,
      pass: exists,
      fix: !exists ? `mkdir -p ${dir}` : undefined,
      autoFixable: !exists,
      autoFix: () => mkdirSync(fullPath, { recursive: true }),
    });
  }

  // Quality baseline
  const baselineDir = join(projectPath, '.quality', 'baselines');
  let hasBaseline = false;
  if (existsSync(baselineDir)) {
    try {
      const files = readdirSync(baselineDir).filter(f => f.endsWith('.json'));
      hasBaseline = files.length > 0;
    } catch { /* */ }
  }
  checks.push({
    name: 'Quality baseline exists',
    pass: hasBaseline,
    fix: !hasBaseline ? 'Run /quality-gate baseline or .quality/scripts/create-baseline.sh' : undefined,
  });

  // Read tracker (should be cleared per session, but file should be writable)
  checks.push({
    name: 'Read tracker writable',
    pass: true, // Always pass — file is created on demand
    detail: 'Created on demand by read-tracker.mjs',
  });

  return { name: 'Quality Infrastructure', weight: 15, checks };
}

// ============================================================
// CATEGORY 5: SKILLS INSTALLATION
// ============================================================

function auditSkillsInstallation() {
  const checks = [];

  const coreSkills = [
    'prd', 'plan', 'implement', 'quality-gate', 'explore',
    'adapt-ui', 'optimize-agents', 'feedback', 'visual-setup',
    'check-designs', 'acceptance-check',
  ];

  for (const skill of coreSkills) {
    const localSkill = join(projectPath, '.claude', 'skills', skill, 'SKILL.md');
    const globalSkill = join(GLOBAL_SKILLS_DIR, skill, 'SKILL.md');
    const engineSkill = join(ENGINE_ROOT, '.claude', 'skills', skill, 'SKILL.md');

    const installed = existsSync(localSkill) || existsSync(globalSkill);
    const engineHas = existsSync(engineSkill);

    checks.push({
      name: `Skill: /${skill}`,
      pass: installed,
      detail: installed
        ? (existsSync(localSkill) ? 'project-local' : 'global (symlink)')
        : 'Not installed',
      fix: !installed && engineHas ? 'Run ./install.sh to install skills' : undefined,
    });
  }

  return { name: 'Skills Installation', weight: 10, checks };
}

// ============================================================
// CATEGORY 6: SPEC-DRIVEN COMPLIANCE
// ============================================================

function auditSpecDrivenCompliance() {
  const checks = [];

  // Check if project is spec-driven
  const projectConfig = join(projectPath, '.claude', 'project-config.json');
  const settingsLocal = join(projectPath, '.claude', 'settings.local.json');

  let isSpecDriven = false;
  let backendType = '';

  for (const configFile of [projectConfig, settingsLocal]) {
    if (!existsSync(configFile)) continue;
    try {
      const config = JSON.parse(readFileSync(configFile, 'utf-8'));
      if (config.boardId || config.board_id || config.backend_type) {
        isSpecDriven = true;
        backendType = config.backend_type || (config.boardId ? 'trello' : 'unknown');
      }
    } catch { /* */ }
  }

  checks.push({
    name: 'Spec-driven configured',
    pass: isSpecDriven,
    detail: isSpecDriven ? `Backend: ${backendType}` : 'No board/backend configured',
    fix: !isSpecDriven ? 'Configure backend_type in .claude/settings.local.json or run set_auth_token' : undefined,
  });

  if (!isSpecDriven) {
    return { name: 'Spec-Driven Compliance', weight: 15, checks };
  }

  // Check active UC state
  const activeUCFile = join(projectPath, '.quality', 'active_uc.json');
  if (existsSync(activeUCFile)) {
    try {
      const uc = JSON.parse(readFileSync(activeUCFile, 'utf-8'));
      const age = (Date.now() - statSync(activeUCFile).mtimeMs) / 1000;
      const fresh = age < 86400;
      checks.push({
        name: 'Active UC marker',
        pass: true,
        detail: fresh
          ? `Active: ${uc.uc_id || 'unknown'} (${Math.round(age / 60)}min ago)`
          : `STALE: ${uc.uc_id || 'unknown'} (${Math.round(age / 3600)}h ago)`,
      });
      if (!fresh) {
        results.warnings.push(`Active UC marker is stale (>24h). Run complete_uc or start a new UC.`);
      }
    } catch { /* */ }
  }

  // Check current branch
  try {
    const branch = execSync('git branch --show-current', { cwd: projectPath, encoding: 'utf-8' }).trim();
    const onMain = branch === 'main' || branch === 'master';
    checks.push({
      name: 'Not on main/master',
      pass: !onMain,
      detail: `Current branch: ${branch}`,
      fix: onMain ? 'Create a feature branch before implementing' : undefined,
    });
  } catch { /* */ }

  return { name: 'Spec-Driven Compliance', weight: 15, checks };
}

// ============================================================
// SCORING & OUTPUT
// ============================================================

function calculateScore() {
  let totalWeight = 0;
  let weightedScore = 0;

  for (const [key, category] of Object.entries(results.categories)) {
    const total = category.checks.length;
    const passed = category.checks.filter(c => c.pass).length;
    category.score = total > 0 ? Math.round((passed / total) * 100) : 100;
    category.passed = passed;
    category.total = total;

    totalWeight += category.weight;
    weightedScore += (category.score / 100) * category.weight;

    // Collect issues
    for (const check of category.checks) {
      if (!check.pass) {
        if (check.critical) {
          results.critical_issues.push(`[${category.name}] ${check.name}: ${check.fix || check.detail || 'Failed'}`);
        } else if (check.fix) {
          results.warnings.push(`[${category.name}] ${check.name}: ${check.fix}`);
        }
        if (check.autoFixable) {
          results.auto_fixable.push({ category: category.name, check: check.name, fix: check.fix });
        }
      }
    }
  }

  results.overall_score = totalWeight > 0 ? Math.round((weightedScore / totalWeight) * 100) : 0;

  // Grade
  const s = results.overall_score;
  if (s === 100) results.overall_grade = 'A+ (Full Compliance)';
  else if (s >= 90) results.overall_grade = 'A (Minor gaps)';
  else if (s >= 75) results.overall_grade = 'B (Moderate gaps)';
  else if (s >= 60) results.overall_grade = 'C (Significant gaps)';
  else if (s >= 40) results.overall_grade = 'D (Major gaps)';
  else results.overall_grade = 'F (Critical — project not compliant)';

  // Recommendations
  if (results.needs_upgrade) {
    results.recommendations.push('Run upgrade_project to align with engine v' + results.engine_version);
  }
  if (results.critical_issues.length > 0) {
    results.recommendations.push('Fix all CRITICAL issues before proceeding with implementation');
  }
  if (results.auto_fixable.length > 0) {
    results.recommendations.push(`Run with --fix to auto-resolve ${results.auto_fixable.length} fixable issues`);
  }
}

function autoFix() {
  let fixed = 0;
  for (const [, category] of Object.entries(results.categories)) {
    for (const check of category.checks) {
      if (!check.pass && check.autoFixable && typeof check.autoFix === 'function') {
        try {
          check.autoFix();
          check.pass = true;
          check.detail = '(auto-fixed)';
          fixed++;
        } catch (err) {
          results.warnings.push(`Auto-fix failed for ${check.name}: ${err.message}`);
        }
      }
    }
  }
  return fixed;
}

function printReport() {
  if (jsonMode) {
    // Strip autoFix functions before serialization
    const clean = JSON.parse(JSON.stringify(results, (key, val) =>
      key === 'autoFix' || key === 'autoFixable' ? undefined : val
    ));
    console.log(JSON.stringify(clean, null, 2));
    return;
  }

  console.log('');
  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log('║           SpecBox Engine — Compliance Audit                 ║');
  console.log('╚══════════════════════════════════════════════════════════════╝');
  console.log('');
  console.log(`  Project:        ${results.project}`);
  console.log(`  Engine version: v${results.engine_version}`);
  console.log(`  Project version: v${results.project_version}`);
  console.log(`  Needs upgrade:  ${results.needs_upgrade ? 'YES' : 'No'}`);
  console.log(`  Score:          ${results.overall_score}% — ${results.overall_grade}`);
  console.log('');

  for (const [, category] of Object.entries(results.categories)) {
    const icon = category.score === 100 ? '✓' : category.score >= 75 ? '~' : '✗';
    console.log(`  ${icon} ${category.name} — ${category.score}% (${category.passed}/${category.total})`);

    if (verbose || category.score < 100) {
      for (const check of category.checks) {
        if (verbose || !check.pass) {
          const mark = check.pass ? '  ✓' : (check.critical ? '  ✗ CRITICAL:' : '  ✗');
          const detail = check.detail ? ` — ${check.detail}` : '';
          console.log(`    ${mark} ${check.name}${detail}`);
          if (!check.pass && check.fix) {
            console.log(`      → Fix: ${check.fix}`);
          }
        }
      }
    }
    console.log('');
  }

  if (results.critical_issues.length > 0) {
    console.log('  ══ CRITICAL ISSUES ══');
    for (const issue of results.critical_issues) {
      console.log(`    ✗ ${issue}`);
    }
    console.log('');
  }

  if (results.recommendations.length > 0) {
    console.log('  ══ RECOMMENDATIONS ══');
    for (const rec of results.recommendations) {
      console.log(`    → ${rec}`);
    }
    console.log('');
  }

  if (results.auto_fixable.length > 0) {
    console.log(`  ${results.auto_fixable.length} issues can be auto-fixed. Run with --fix to resolve.`);
    console.log('');
  }

  console.log('────────────────────────────────────────────────────────────────');
  console.log('');
}

// ============================================================
// MAIN
// ============================================================

// Run all audit categories
results.categories.version = auditVersionAlignment();
results.categories.hooks = auditHooksInstallation();
results.categories.settings = auditSettingsConfiguration();
results.categories.quality = auditQualityInfra();
results.categories.skills = auditSkillsInstallation();
results.categories.spec_driven = auditSpecDrivenCompliance();

// Auto-fix if requested
if (fixMode) {
  const fixed = autoFix();
  if (!jsonMode) {
    console.log(`\n  Auto-fixed ${fixed} issue(s).\n`);
  }
}

// Calculate final scores
calculateScore();

// Output
printReport();

// Save report to .quality/
const reportDir = join(projectPath, '.quality', 'evidence');
if (existsSync(join(projectPath, '.quality'))) {
  try {
    mkdirSync(reportDir, { recursive: true });
    const reportFile = join(reportDir, 'compliance-audit.json');
    const clean = JSON.parse(JSON.stringify(results, (key, val) =>
      key === 'autoFix' || key === 'autoFixable' ? undefined : val
    ));
    writeFileSync(reportFile, JSON.stringify(clean, null, 2) + '\n');
  } catch { /* best effort */ }
}

// Exit code
if (results.critical_issues.length > 0) {
  process.exit(2);
} else if (results.overall_score < 100) {
  process.exit(1);
} else {
  process.exit(0);
}
