#!/usr/bin/env node
/**
 * agent-identity.mjs — PreToolUse de start_uc y record_review_verdict: quién llama (UC-12402).
 *
 * Pone en la llamada el contexto de Claude Code (`client_session_id`, `client_agent_id`,
 * `client_agent_type`) que recibe el hook, para que el tablero sepa quién implementó la UC y rechace un
 * veredicto de revisión del mismo contexto. Lo que mande el modelo en esos campos se sustituye.
 *
 * En FreeForm con el MCP remoto no hace nada: freeform-fragment ya cambia esas llamadas y pone la
 * identidad él mismo (dos hooks no cambian la misma llamada). Nunca bloquea.
 */

import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { IDENTITY_TOOLS, withIdentity } from './lib/agent-identity.mjs';
import { isRemoteMcp } from './lib/freeform-path.mjs';
import { parseToolName } from './lib/freeform-fragment.mjs';
import { readHookInput, readJsonFile } from './lib/utils.mjs';

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (event !== 'PreToolUse' || !parsed || !IDENTITY_TOOLS.has(parsed.tool)) process.exit(0);

let root = cwd;
try {
  root = execFileSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], {
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'ignore'],
    timeout: 5000,
  }).trim() || cwd;
} catch {
  // fuera de un repositorio: se usa la carpeta actual
}
const settings = readJsonFile(join(root, '.claude', 'settings.local.json'))?.specbox ?? {};
if (settings.backend_type === 'freeform' && isRemoteMcp({ cwd: root })) process.exit(0); // freeform-fragment

const updatedInput = withIdentity(toolInput, payload);
if (!updatedInput.client_session_id) process.exit(0); // sin contexto que poner: la llamada va como está
process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput } }));
