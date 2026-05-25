#!/usr/bin/env node
/**
 * implement-checkpoint.mjs — Hook helper: saves checkpoint after each /implement phase
 * Usage: node implement-checkpoint.mjs <feature> <phase_number> <phase_name>
 * Called from within the /implement Skill, not as an automatic hook.
 */

import { git, mkdir, now } from './lib/utils.mjs';
import { writeFileSync } from 'fs';

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

// v6.1.0 Cloud Cutover: remote heartbeat + mcp-report dispatch removed.
// Local checkpoint state still persisted to .quality/checkpoints/ above.
