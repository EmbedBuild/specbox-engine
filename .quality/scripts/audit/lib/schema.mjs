/**
 * lib/schema.mjs — Client-side mirror of server/audit/schema.py (UC-663).
 *
 * The 8 SQuaRE analyzers run on the client (Node, zero-Python) and each
 * produces a CharacteristicResult fragment. The orchestrator merges them
 * into a QualityReport dict that is submitted verbatim to the MCP via
 * `submit_quality_audit(project, report)` — the server validates it against
 * server/audit/schema.py (QualityReport.from_dict), so the shapes here MUST
 * stay byte-compatible with that contract.
 *
 * Only the enums + ordering + the dict shapes the server reads are mirrored.
 * The server owns scoring authority for the *global* score and PDF render;
 * the client computes per-characteristic scores so the report is complete
 * before submission (the server re-derives nothing it isn't given).
 */

export const AUDIT_SCHEMA_VERSION = '1.0';

/** @enum {string} — mirrors schema.py Severity */
export const Severity = Object.freeze({
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
  INFO: 'info',
});

/** @enum {string} — mirrors schema.py TrafficLight */
export const TrafficLight = Object.freeze({
  GREEN: 'green',
  AMBER: 'amber',
  RED: 'red',
});

/** @enum {string} — mirrors schema.py SquareCharacteristic (values are the JSON ids) */
export const SquareCharacteristic = Object.freeze({
  FUNCTIONAL_SUITABILITY: 'functional_suitability',
  PERFORMANCE_EFFICIENCY: 'performance_efficiency',
  COMPATIBILITY: 'compatibility',
  USABILITY: 'usability',
  RELIABILITY: 'reliability',
  SECURITY: 'security',
  MAINTAINABILITY: 'maintainability',
  PORTABILITY: 'portability',
});

/** Canonical SQuaRE order for the report (mirrors schema.py SQUARE_ORDER). */
export const SQUARE_ORDER = Object.freeze([
  SquareCharacteristic.FUNCTIONAL_SUITABILITY,
  SquareCharacteristic.PERFORMANCE_EFFICIENCY,
  SquareCharacteristic.COMPATIBILITY,
  SquareCharacteristic.USABILITY,
  SquareCharacteristic.RELIABILITY,
  SquareCharacteristic.SECURITY,
  SquareCharacteristic.MAINTAINABILITY,
  SquareCharacteristic.PORTABILITY,
]);

/**
 * Build a Finding dict (drops null/undefined keys, mirrors Finding.to_dict).
 * @param {{severity:string, description:string, remediation:string, cwe?:string|null, file?:string|null, line?:number|null, source_tool?:string|null}} f
 * @returns {object}
 */
export function finding(f) {
  const out = {
    severity: f.severity,
    description: f.description,
    remediation: f.remediation,
  };
  if (f.cwe !== null && f.cwe !== undefined) out.cwe = String(f.cwe);
  if (f.file !== null && f.file !== undefined) out.file = f.file;
  if (f.line !== null && f.line !== undefined) out.line = f.line;
  if (f.source_tool !== null && f.source_tool !== undefined) out.source_tool = f.source_tool;
  return out;
}

/**
 * Build a ToolUsage dict (drops null/undefined keys, mirrors ToolUsage.to_dict).
 * @param {{name:string, status:string, version?:string|null, stack?:string|null, message?:string|null}} t
 * @returns {object}
 */
export function toolUsage(t) {
  const out = { name: t.name, status: t.status };
  if (t.version !== null && t.version !== undefined) out.version = t.version;
  if (t.stack !== null && t.stack !== undefined) out.stack = t.stack;
  if (t.message !== null && t.message !== undefined) out.message = t.message;
  return out;
}

/**
 * Build a CharacteristicResult dict (mirrors CharacteristicResult.to_dict).
 * `id` is the SquareCharacteristic value; score is rounded to 2 decimals.
 *
 * @param {object} r
 * @param {string} r.characteristic - a SquareCharacteristic value
 * @param {number} r.score - 0..100
 * @param {string} r.traffic_light - a TrafficLight value
 * @param {string} [r.justification]
 * @param {object} [r.raw_metrics]
 * @param {object[]} [r.findings]
 * @param {object[]} [r.recommendations]
 * @param {object|null} [r.breakdown] - maintainability only
 * @param {boolean} [r.skipped]
 * @param {string|null} [r.skipped_reason]
 * @returns {object}
 */
export function characteristicResult(r) {
  const out = {
    id: r.characteristic,
    score: round2(r.score),
    traffic_light: r.traffic_light,
    justification: r.justification || '',
    raw_metrics: r.raw_metrics || {},
    findings: r.findings || [],
    recommendations: r.recommendations || [],
    skipped: r.skipped || false,
  };
  if (r.breakdown !== null && r.breakdown !== undefined) out.breakdown = r.breakdown;
  if (r.skipped_reason) out.skipped_reason = r.skipped_reason;
  return out;
}

/** Round to 2 decimals like Python's round(x, 2) used across to_dict. */
export function round2(x) {
  return Math.round((Number(x) + Number.EPSILON) * 100) / 100;
}

/** Round to 3 decimals — used by raw_metrics ratios (mirrors round(x, 3)). */
export function round3(x) {
  return Math.round((Number(x) + Number.EPSILON) * 1000) / 1000;
}

/** ISO 8601 UTC timestamp (mirrors schema.py now_iso). */
export function nowIso() {
  return new Date().toISOString();
}

/** audit_id format audit_YYYYMMDDTHHMMSSZ (mirrors schema.py new_audit_id). */
export function newAuditId() {
  const d = new Date();
  const p = (n, w = 2) => String(n).padStart(w, '0');
  const ts = `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}`
    + `T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`;
  return `audit_${ts}`;
}
