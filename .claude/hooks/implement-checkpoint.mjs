#!/usr/bin/env node
/**
 * implement-checkpoint.mjs — Hook helper: saves checkpoint after each /implement phase
 * Usage: node implement-checkpoint.mjs <feature> <phase_number> <phase_name>
 * Called from within the /implement Skill, not as an automatic hook.
 */

import { git, getProjectName, mkdir, now, getHooksDir } from './lib/utils.mjs';
import { writeFileSync } from 'fs';
import { spawn } from 'child_process';
import { join } from 'path';

const feature = process.argv[2] || '';
const phase = process.argv[3] || '';
const phaseName = process.argv[4] || '';
const branch = git('branch --show-current') || 'unknown';

if (!feature || !phase) {
  console.log('Usage: implement-checkpoint.mjs <feature> <phase> <phase_name>');
  process.exit(1);
}

const evidenceDir = `.quality/evidence/${feature}`;
mkdir(evidenceDir);

const timestamp = now();

const checkpoint = {
  feature,
  phase: Number(phase),
  phase_name: phaseName,
  branch,
  timestamp,
  status: 'complete',
};

writeFileSync(
  join(evidenceDir, 'checkpoint.json'),
  JSON.stringify(checkpoint, null, 2) + '\n',
  'utf-8'
);

console.log(`[CHECKPOINT] Phase ${phase} (${phaseName}) saved for ${feature}`);

// Report to MCP (fire-and-forget)
const projectName = getProjectName();
const hooksDir = getHooksDir();

const mcpArgs = JSON.stringify({
  project: projectName,
  feature,
  phase: Number(phase),
  phase_name: phaseName,
  branch,
  timestamp,
});

const child1 = spawn('node', [join(hooksDir, 'mcp-report.mjs'), 'report_checkpoint', mcpArgs], {
  detached: true,
  stdio: 'ignore',
});
child1.unref();

// Send heartbeat with current phase info (fire-and-forget, background)
const child2 = spawn('node', [join(hooksDir, 'heartbeat-sender.mjs'), projectName, 'implement'], {
  detached: true,
  stdio: 'ignore',
});
child2.unref();
