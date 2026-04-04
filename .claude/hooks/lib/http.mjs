/**
 * lib/http.mjs — HTTP client and MCP protocol for SpecBox Engine hooks
 * Zero external dependencies. Uses Node.js 18+ global fetch.
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

/**
 * Get the MCP URL from environment variables.
 * Supports SPECBOX_ENGINE_MCP_URL with DEV_ENGINE_MCP_URL as legacy fallback.
 */
export function getMcpUrl() {
  return process.env.SPECBOX_ENGINE_MCP_URL || process.env.DEV_ENGINE_MCP_URL || '';
}

/**
 * Get the API base URL (MCP URL without /mcp suffix).
 */
export function getApiBase() {
  const url = getMcpUrl();
  return url.replace(/\/mcp$/, '');
}

/**
 * HTTP POST with timeout.
 * @param {string} url
 * @param {object} body
 * @param {object} [opts]
 * @param {number} [opts.timeoutMs=5000]
 * @param {object} [opts.headers]
 * @returns {Promise<{status: number, ok: boolean, body?: any}>}
 */
export async function httpPost(url, body, opts = {}) {
  const { timeoutMs = 5000, headers = {} } = opts;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headers },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    let resBody;
    try { resBody = await res.json(); } catch { resBody = null; }
    return { status: res.status, ok: res.ok, body: resBody, headers: res.headers };
  } catch {
    return { status: 0, ok: false, body: null, headers: null };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Read ENGINE_VERSION from ENGINE_VERSION.yaml
 */
function getEngineVersion() {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  const engineRoot = resolve(__dirname, '..', '..', '..');
  const versionFile = resolve(engineRoot, 'ENGINE_VERSION.yaml');
  if (!existsSync(versionFile)) return 'unknown';
  try {
    const content = readFileSync(versionFile, 'utf-8');
    const match = content.match(/^version:\s*(.+)$/m);
    return match ? match[1].trim() : 'unknown';
  } catch {
    return 'unknown';
  }
}

/**
 * Perform a full MCP tool call (3-step protocol):
 *   1. initialize → get session ID
 *   2. notifications/initialized
 *   3. tools/call with tool name and arguments
 *
 * Fire-and-forget: errors are silently ignored.
 *
 * @param {string} toolName - MCP tool name to call
 * @param {object} args - Tool arguments
 */
export async function mcpCall(toolName, args) {
  const mcpUrl = getMcpUrl();
  if (!mcpUrl) return;

  const engineVersion = getEngineVersion();

  try {
    // Step 1: Initialize
    const initRes = await httpPost(mcpUrl, {
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2025-03-26',
        capabilities: {},
        clientInfo: { name: 'specbox-engine-hook', version: engineVersion },
      },
    }, { timeoutMs: 5000 });

    const sessionId = initRes.headers?.get('mcp-session-id');
    if (!sessionId) return;

    const sessionHeaders = {
      'Mcp-Session-Id': sessionId,
    };

    // Step 2: Send initialized notification
    await httpPost(mcpUrl, {
      jsonrpc: '2.0',
      method: 'notifications/initialized',
    }, { timeoutMs: 5000, headers: sessionHeaders });

    // Step 3: Call the tool
    await httpPost(mcpUrl, {
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/call',
      params: { name: toolName, arguments: args },
    }, { timeoutMs: 5000, headers: sessionHeaders });
  } catch {
    // Fire-and-forget: silently ignore all errors
  }
}

/**
 * Send a heartbeat to the VPS REST API.
 * @param {object} payload - Heartbeat payload
 */
export async function heartbeat(payload) {
  const apiBase = getApiBase();
  if (!apiBase) return { ok: false };

  const syncToken = process.env.SPECBOX_SYNC_TOKEN || '';
  const headers = {};
  if (syncToken) {
    headers['Authorization'] = `Bearer ${syncToken}`;
  }

  return httpPost(`${apiBase}/api/heartbeat`, payload, { timeoutMs: 5000, headers });
}
