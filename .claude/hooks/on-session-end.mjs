#!/usr/bin/env node
/**
 * on-session-end.mjs — Stop hook: logs session telemetry
 * NON-BLOCKING: Records session metrics and reports to MCP + Engram.
 */

import { git, mkdir, now, getProjectName, findFiles, commandExists, getHooksDir } from './lib/utils.mjs';
import { appendLine, fileExists } from './lib/utils.mjs';
import { spawn } from 'child_process';
import { readFileSync, statSync } from 'fs';
import { join, basename, dirname } from 'path';

const LOGS_DIR = '.quality/logs';
mkdir(LOGS_DIR);

const timestamp = now();
const date = timestamp.slice(0, 10); // YYYY-MM-DD
const LOG_FILE = join(LOGS_DIR, `sessions_${date}.jsonl`);

// Count files modified in this session (git-tracked changes)
const diffOutput = git('diff --name-only HEAD');
const filesModified = diffOutput ? diffOutput.split('\n').filter(Boolean).length : 0;

// Estimate context loaded (sum of modified + staged files in chars)
let contextChars = 0;
const allChangedFiles = new Set();
if (diffOutput) diffOutput.split('\n').filter(Boolean).forEach(f => allChangedFiles.add(f));
const cachedOutput = git('diff --cached --name-only');
if (cachedOutput) cachedOutput.split('\n').filter(Boolean).forEach(f => allChangedFiles.add(f));

for (const f of allChangedFiles) {
  if (fileExists(f)) {
    try {
      const chars = readFileSync(f, 'utf-8').length;
      contextChars += chars;
    } catch { /* ignore */ }
  }
}
const contextTokens = Math.floor(contextChars / 4);

// Count healing events if evidence exists
let healingEvents = 0;
const healingFiles = findFiles('.quality/evidence', /^healing\.jsonl$/);
if (healingFiles.length > 0) {
  try {
    const content = readFileSync(healingFiles[0], 'utf-8');
    healingEvents = content.split('\n').filter(Boolean).length;
  } catch { /* ignore */ }
}

// Check for checkpoint (active implementation)
let activeFeature = '';
const checkpointFiles = findFiles('.quality/evidence', /^checkpoint\.json$/);
if (checkpointFiles.length > 0) {
  // Find checkpoints newer than the log file
  const logMtime = fileExists(LOG_FILE) ? statSync(LOG_FILE).mtimeMs : 0;
  for (const cp of checkpointFiles) {
    try {
      if (statSync(cp).mtimeMs > logMtime) {
        activeFeature = basename(dirname(cp));
        break;
      }
    } catch { /* ignore */ }
  }
}

// Write session log
const logEntry = JSON.stringify({
  event: 'session_end',
  timestamp,
  pwd: process.cwd(),
  files_modified: filesModified,
  context_tokens_est: contextTokens,
  healing_events: healingEvents,
  active_feature: activeFeature,
});
appendLine(LOG_FILE, logEntry);

console.log(`[TELEMETRY] Session logged to ${LOG_FILE} (est. ${contextTokens} tokens, ${filesModified} files)`);

// Persist session summary to Engram (REQUERIDO)
if (commandExists('engram')) {
  const engramSummary = `Session ended at ${timestamp} | Project: ${basename(process.cwd())} | Files modified: ${filesModified} | Context tokens: ${contextTokens} | Healing events: ${healingEvents} | Active feature: ${activeFeature}`;
  const engramChild = spawn('engram', ['save', 'session-summary', engramSummary], {
    detached: true,
    stdio: 'ignore',
  });
  engramChild.unref();
  console.log('[ENGRAM] Session summary persisted to Engram memory');
} else {
  // Detect OS and suggest appropriate install method
  console.log('');
  console.log('============================================================');
  console.log('  ERROR: ENGRAM NO INSTALADO');
  console.log('============================================================');
  console.log('  Engram es requerido para la memoria persistente del engine.');
  console.log('  Sin el, las compactaciones de contexto causan perdida de estado.');
  console.log('');

  switch (process.platform) {
    case 'darwin':
      console.log('  SO detectado: macOS');
      console.log('');
      console.log('  Instalar:');
      console.log('    # Apple Silicon (M1/M2/M3/M4):');
      console.log('    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_arm64.tar.gz | tar xz');
      console.log('    # Intel:');
      console.log('    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_amd64.tar.gz | tar xz');
      console.log('    mv engram ~/.local/bin/');
      break;
    case 'linux':
      console.log('  SO detectado: Linux');
      console.log('');
      console.log('  Instalar:');
      console.log('    # x86_64:');
      console.log('    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_amd64.tar.gz | tar xz');
      console.log('    # arm64:');
      console.log('    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_arm64.tar.gz | tar xz');
      console.log('    mv engram ~/.local/bin/');
      break;
    case 'win32':
      console.log('  SO detectado: Windows');
      console.log('');
      console.log('  Instalar:');
      console.log('    Descargar desde: https://github.com/Gentleman-Programming/engram/releases/latest');
      console.log('    Archivo: engram_1.7.1_windows_amd64.zip o engram_1.7.1_windows_arm64.zip');
      console.log('    Descomprimir y mover engram.exe a una carpeta en el PATH');
      break;
    default:
      console.log(`  SO detectado: ${process.platform}`);
      console.log('');
      console.log('  Descargar desde: https://github.com/Gentleman-Programming/engram/releases/latest');
      break;
  }

  console.log('');
  console.log('  Verificar: engram save "test" "hello engram"');
  console.log('  MCP config: .vscode/mcp.json');
  console.log('============================================================');
  console.log('');
}

// Report to MCP (fire-and-forget)
const projectName = getProjectName();
const hooksDir = getHooksDir();

const mcpArgs = JSON.stringify({
  project: projectName,
  timestamp,
  files_modified: filesModified,
  context_tokens_est: contextTokens,
  healing_events: healingEvents,
  active_feature: activeFeature,
});

const mcpChild = spawn('node', [join(hooksDir, 'mcp-report.mjs'), 'report_session', mcpArgs], {
  detached: true,
  stdio: 'ignore',
});
mcpChild.unref();

// Send heartbeat (fire-and-forget, background)
const hbChild = spawn('node', [join(hooksDir, 'heartbeat-sender.mjs'), projectName, 'idle'], {
  detached: true,
  stdio: 'ignore',
});
hbChild.unref();
