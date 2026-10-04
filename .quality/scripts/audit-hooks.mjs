/**
 * audit-hooks.mjs — qué hooks exige /compliance (US-75 / UC-7501).
 *
 * La lista sale de templates/settings.json.template, lo que reciben los proyectos, más los
 * ayudantes que llama /implement; los módulos de lib/ son los que esos hooks importan. Antes era una
 * lista escrita a mano que exigía hooks retirados (mcp-report.mjs, lib/http.mjs) y no conocía los
 * nuevos.
 */

import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

/** Hooks cuyo fallo deja al proyecto sin un control que bloquea. */
const CRITICAL = new Set([
  'quality-first-guard',
  'read-tracker',
  'spec-guard',
  'commit-spec-guard',
  'pre-commit-lint',
  'no-bypass-guard',
  'healing-budget-guard',
  'pipeline-phase-guard',
]);

const DESCRIPTIONS = {
  'quality-first-guard': 'Read-before-write enforcement',
  'read-tracker': 'Tracks file reads for quality-first-guard',
  'spec-guard': 'No code without active UC, nor on main',
  'commit-spec-guard': 'No commits on main',
  'pre-commit-lint': 'Zero-tolerance lint on commit',
  'design-gate': 'No UI without its design',
  'design-system-gate': 'UI changes stay inside the design system',
  'e2e-gate': 'E2E evidence validation on commit',
  'no-bypass-guard': 'Blocks --no-verify, --force, --hard',
  'on-session-end': 'Session telemetry',
  'healing-budget-guard': 'Healing budget enforcement (max 8)',
  'pipeline-phase-guard': 'Pipeline phase ordering enforcement',
  'checkpoint-freshness-guard': 'Checkpoint staleness warning on commit',
  'uc-lifecycle-guard': 'UC lifecycle warning on push',
  'stripe-safety-guard': 'Stripe anti-patterns in billing code',
  'session-start': 'Injects the handoff when a session starts',
  'pre-read-budget-guard': 'Warns before reading huge files',
  'context-budget-guard': 'Subagent prompt budget',
  'file-ownership-guard': 'Subagents write only the files their role owns',
  'freeform-path-guard': 'Absolute FreeForm tracking paths',
  'pre-prd-discovery-check': 'Discovery gate before /prd',
  'app-docs-sync-guard': 'Canonical docs drift on commit',
};

/** Ayudantes que no se registran en settings.json: los llama /implement. */
const HELPERS = [
  { name: 'implement-checkpoint', desc: 'Phase checkpoint helper (/implement)' },
  { name: 'implement-healing', desc: 'Healing event logger (/implement)' },
];

/** Los hooks que exige /compliance: los de la plantilla y los ayudantes de /implement. */
export function requiredHooks(engineRoot) {
  const template = readFileSync(join(engineRoot, 'templates', 'settings.json.template'), 'utf8');
  const wired = [...new Set([...template.matchAll(/\.claude\/hooks\/([a-z0-9-]+)\.mjs/g)].map((m) => m[1]))];
  return [
    ...wired.map((name) => ({
      file: `${name}.mjs`,
      critical: CRITICAL.has(name),
      desc: DESCRIPTIONS[name] ?? 'Hook wired by the project template',
    })),
    ...HELPERS.filter((h) => !wired.includes(h.name)).map((h) => ({ file: `${h.name}.mjs`, critical: false, desc: h.desc })),
  ];
}

/** Los módulos de lib/ que importan esos hooks, también los que se importan entre sí. */
export function requiredLibFiles(engineRoot, hooks = requiredHooks(engineRoot)) {
  const hooksDir = join(engineRoot, '.claude', 'hooks');
  const libs = new Set();
  const pending = [];
  const imports = (path, pattern) => {
    if (!existsSync(path)) return [];
    return [...readFileSync(path, 'utf8').matchAll(pattern)].map((m) => m[1]);
  };
  for (const hook of hooks) {
    pending.push(...imports(join(hooksDir, hook.file), /from\s+['"]\.\/lib\/([a-z0-9-]+\.mjs)['"]/g));
  }
  while (pending.length) {
    const lib = pending.pop();
    if (libs.has(lib)) continue;
    libs.add(lib);
    pending.push(...imports(join(hooksDir, 'lib', lib), /from\s+['"]\.\/([a-z0-9-]+\.mjs)['"]/g));
  }
  return [...libs].sort();
}
