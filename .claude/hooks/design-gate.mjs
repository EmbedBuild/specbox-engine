#!/usr/bin/env node
/**
 * design-gate.mjs — PostToolUse hook for Write/Edit on UI page files
 * BLOCKING: Prevents creating/modifying UI pages without Stitch designs.
 *
 * v5.10.0 — Design Discipline Enforcement
 */

import { readStdin, fileExists, findFiles } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { readFileSync } from 'fs';
import { join } from 'path';

const input = readStdin();

// Extract the file path from the tool input
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// Check if the file is a UI page file (Flutter, React, Next.js)
if (!/(presentation\/pages\/|src\/pages\/|app\/.*page\.(tsx|ts|jsx))/.test(filePath)) {
  process.exit(0);
}

// Extract feature name from the path
// Flutter: lib/presentation/features/{feature}/pages/
// React: src/pages/{feature}/ or app/{feature}/page.tsx
const featureMatch = filePath.match(/(features|pages)\/([^/]+)/);
const feature = featureMatch ? featureMatch[2] : '';

if (!feature) {
  process.exit(0);
}

// Check if Stitch designs exist for this feature
// Multi-repo: designs may live in the orchestrator repo
const { orchestratorRoot } = getProjectConfig();
const designDir = join(orchestratorRoot, 'doc', 'design', feature);
const htmlFiles = findFiles(designDir, /\.html$/);
const htmlCount = htmlFiles.length;

if (htmlCount === 0) {
  console.log('');
  console.log('============================================================');
  console.log('  DESIGN GATE: No Stitch design found — UI write blocked');
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log(`  Feature: ${feature}`);
  console.log(`  Expected: ${designDir}/*.html`);
  console.log('');
  console.log('  The SpecBox Engine contract requires ALL UI pages to be');
  console.log('  generated from Stitch designs (design-to-code pipeline).');
  console.log('');
  console.log('  To proceed:');
  console.log('    1. Run /plan to generate Stitch designs for this feature');
  console.log(`    2. Or manually create designs in ${designDir}/`);
  console.log('    3. Then implement the UI from the HTML designs');
  console.log('');
  console.log('  This is non-negotiable. UI without design = no visual');
  console.log('  consistency = no traceability = quality degradation.');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// Design exists — check for traceability comment (WARNING only, not blocking)
if (fileExists(filePath)) {
  try {
    const content = readFileSync(filePath, 'utf-8');
    const first10Lines = content.split('\n').slice(0, 10).join('\n');
    if (!first10Lines.includes('Generated from: doc/design/')) {
      console.log('');
      console.log(`WARNING: Missing design traceability comment in ${filePath}`);
      console.log(`  Expected (within first 10 lines): // Generated from: doc/design/${feature}/{screen}.html`);
      console.log('  This is required for AG-08 Check 6 compliance.');
      console.log('');
    }
  } catch { /* ignore read errors */ }
}

process.exit(0);
