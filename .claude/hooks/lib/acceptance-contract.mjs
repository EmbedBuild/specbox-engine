/**
 * El contrato de cada criterio antes de las pruebas de aceptación (US-128 · UC-12801).
 *
 * Espejo de `server/acceptance_contract.py`: las mismas reglas y los mismos mensajes, con una prueba
 * de paridad en `tests/test_acceptance_contract.py`. Lo usan `validate-results-json.js
 * --check-contract`, el hook `contract-first-guard` y `e2e-gate`.
 *
 * contract.json (uno por UC, en .quality/evidence/<feature>/acceptance/):
 *   {"schema": 1, "uc_id": "UC-12801", "criteria": {"AC-01": {
 *     "pre": [{"id": "AC-01.pre1", "text": "…"}], "post": [{"id": "AC-01.post1", "text": "…"}],
 *     "undefined": ["…"]}}}
 * Cada prueba cita lo que comprueba en results[].contract = {"pre": [...], "post": [...]}.
 */

export const SCHEMA = 1;
export const MAX_CONTRACT_BYTES = 512_000;
export const MAX_RESULTS_BYTES = 5_000_000;
export const MAX_CRITERIA = 200;
export const MAX_CONDITIONS = 50;
export const MAX_TEXT = 2000;
const KINDS = ['pre', 'post'];

const AC_RE = /^[ \t\r\n]*AC-(\d{1,4})[ \t\r\n]*$/i;
const CONDITION_RE = /^[ \t\r\n]*AC-(\d{1,4})\.(pre|post)(\d{1,4})[ \t\r\n]*$/i;

export class ContractError extends Error {}
export class ResultsError extends Error {}

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const pad = (n) => String(Number.parseInt(n, 10)).padStart(2, '0');
/** Corta por caracteres, no por unidades UTF-16 (como Python). */
const cut = (s, n) => Array.from(s).slice(0, n).join('');
const chars = (s) => Array.from(s).length;
/** Solo los espacios ASCII cuentan como espacio, igual que en el servidor. */
const strip = (s) => String(s).replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '');

function acId(raw) {
  const m = typeof raw === 'string' ? AC_RE.exec(raw) : null;
  return m ? `AC-${pad(m[1])}` : null;
}

/** `ac-1.PRE01` es `AC-01.pre1`: [id, criterio, clase] o null. */
export function normalizeCondition(raw) {
  const m = typeof raw === 'string' ? CONDITION_RE.exec(raw) : null;
  if (!m) return null;
  const ac = `AC-${pad(m[1])}`;
  const kind = m[2].toLowerCase();
  return [`${ac}.${kind}${Number.parseInt(m[3], 10)}`, ac, kind];
}

/** Un valor del cliente para un mensaje: el texto tal cual y lo demás en JSON (como Python). */
function show(raw) {
  if (typeof raw === 'string') return raw;
  try {
    const out = JSON.stringify(raw === undefined ? null : raw);
    return out === undefined ? '?' : out;
  } catch {
    return '?';
  }
}

/** Lee el contrato y lo deja normalizado; lo que no vale va a `invalid`. */
export function parseContract(content) {
  if (content === null || content === undefined || !strip(content)) throw new ContractError('está vacío');
  if (Buffer.byteLength(content, 'utf8') > MAX_CONTRACT_BYTES) {
    throw new ContractError(`pasa de ${MAX_CONTRACT_BYTES} bytes`);
  }
  let data;
  try {
    data = JSON.parse(content);
  } catch (e) {
    throw new ContractError(`no es JSON (${e.message})`);
  }
  if (!isObj(data)) throw new ContractError('no es un objeto JSON');
  const schema = has(data, 'schema') ? data.schema : null;
  if (schema !== SCHEMA) throw new ContractError(`su «schema» es ${show(schema)}; este engine lee el ${SCHEMA}`);
  const rawCriteria = data.criteria;
  if (!isObj(rawCriteria)) throw new ContractError('no tiene «criteria» como objeto');
  if (Object.keys(rawCriteria).length > MAX_CRITERIA) throw new ContractError(`tiene más de ${MAX_CRITERIA} criterios`);

  const invalid = [];
  let ucId = data.uc_id;
  if (typeof ucId !== 'string' || !strip(ucId)) {
    invalid.push({ ac_id: '', problem: 'falta «uc_id»' });
    ucId = '';
  }
  const criteria = {};
  for (const [key, entry] of Object.entries(rawCriteria)) {
    const ac = acId(key);
    if (ac === null) {
      invalid.push({ ac_id: String(key), problem: 'no es el id de un criterio (AC-NN)' });
      continue;
    }
    if (has(criteria, ac)) {
      invalid.push({ ac_id: ac, problem: 'el criterio aparece dos veces' });
      continue;
    }
    if (!isObj(entry)) {
      invalid.push({ ac_id: ac, problem: 'no es un objeto con «pre», «post» y «undefined»' });
      continue;
    }
    const parsed = { pre: [], post: [], undefined: null };
    for (const kind of KINDS) {
      let items = has(entry, kind) ? entry[kind] : [];
      if (!Array.isArray(items)) {
        invalid.push({ ac_id: ac, problem: `«${kind}» no es una lista` });
        continue;
      }
      if (items.length > MAX_CONDITIONS) {
        invalid.push({ ac_id: ac, problem: `«${kind}» tiene más de ${MAX_CONDITIONS} condiciones` });
        items = items.slice(0, MAX_CONDITIONS);
      }
      const seen = new Set();
      for (const item of items) {
        const rawId = isObj(item) && has(item, 'id') ? item.id : null;
        const text = isObj(item) && has(item, 'text') ? item.text : null;
        const cond = normalizeCondition(rawId);
        if (cond === null) {
          invalid.push({
            ac_id: ac,
            problem: cut(`«${kind}» tiene una condición sin id válido (AC-NN.${kind}N): ${show(rawId)}`, 300),
          });
          continue;
        }
        const [condId, condAc, condKind] = cond;
        if (condAc !== ac || condKind !== kind) {
          invalid.push({ ac_id: ac, problem: `«${condId}» no es una ${kind} de ${ac}` });
          continue;
        }
        if (seen.has(condId)) {
          invalid.push({ ac_id: ac, problem: `«${condId}» aparece dos veces` });
          continue;
        }
        if (typeof text !== 'string' || !strip(text)) {
          invalid.push({ ac_id: ac, problem: `«${condId}» no tiene texto` });
          continue;
        }
        if (chars(text) > MAX_TEXT) {
          invalid.push({ ac_id: ac, problem: `«${condId}» pasa de ${MAX_TEXT} caracteres` });
          continue;
        }
        seen.add(condId);
        parsed[kind].push({ id: condId, text: strip(text) });
      }
    }
    const undef = has(entry, 'undefined') ? entry.undefined : null;
    if (undef !== null) {
      if (!Array.isArray(undef) || !undef.every((u) => typeof u === 'string' && strip(u))) {
        invalid.push({ ac_id: ac, problem: '«undefined» no es una lista de textos' });
      } else if (undef.length > MAX_CONDITIONS || undef.some((u) => chars(u) > MAX_TEXT)) {
        invalid.push({ ac_id: ac, problem: '«undefined» es demasiado largo' });
      } else {
        parsed.undefined = undef.map((u) => strip(u));
      }
    }
    criteria[ac] = parsed;
  }
  return { uc_id: strip(ucId).toUpperCase(), criteria, invalid };
}

/** Qué falta en el contrato para los criterios vigentes de la UC (AC-01). */
export function checkContract(contract, criteriaIds, ucId = null) {
  const wanted = [];
  for (const raw of criteriaIds || []) {
    const ac = acId(raw);
    if (ac && !wanted.includes(ac)) wanted.push(ac);
  }
  const entries = contract.criteria;
  const missing = wanted.filter((ac) => !has(entries, ac));
  const incomplete = [];
  for (const ac of wanted) {
    const entry = entries[ac];
    if (!entry || !has(entries, ac)) continue;
    const lacks = KINDS.filter((kind) => entry[kind].length === 0);
    if (entry.undefined === null) lacks.push('undefined');
    if (lacks.length) incomplete.push({ ac_id: ac, missing: lacks });
  }
  const extra = wanted.length ? Object.keys(entries).filter((ac) => !wanted.includes(ac)) : [];
  const out = { missing, incomplete, extra };
  const expected = strip(ucId || '').toUpperCase();
  if (expected && contract.uc_id && contract.uc_id !== expected) {
    out.uc_mismatch = { expected, found: contract.uc_id };
  }
  return out;
}

/** Las ejecuciones de results.json (una o una lista), en orden: la más reciente, la última. */
export function parseResults(content) {
  if (content === null || content === undefined || !strip(content)) throw new ResultsError('está vacío');
  if (Buffer.byteLength(content, 'utf8') > MAX_RESULTS_BYTES) {
    throw new ResultsError(`pasa de ${MAX_RESULTS_BYTES} bytes`);
  }
  let data;
  try {
    data = JSON.parse(content);
  } catch (e) {
    throw new ResultsError(`no es JSON (${e.message})`);
  }
  let runs = Array.isArray(data) ? data : [data];
  if (!runs.length) throw new ResultsError('no trae ninguna ejecución');
  runs.forEach((run, i) => {
    if (!isObj(run) || !Array.isArray(run.results)) {
      throw new ResultsError(`la ejecución ${i + 1} no tiene una lista «results»`);
    }
  });
  if (runs.every((r) => typeof r.timestamp === 'string' && r.timestamp)) {
    runs = [...runs].sort((a, b) => (a.timestamp < b.timestamp ? -1 : a.timestamp > b.timestamp ? 1 : 0));
  }
  return runs;
}

function latestTests(runs, ucId) {
  const out = new Map();
  for (const run of runs) {
    const runUc = strip(run.uc_id || '').toUpperCase();
    if (ucId && runUc && runUc !== ucId) continue;
    const thisRun = new Map();
    for (const result of run.results) {
      const ac = isObj(result) ? acId(result.id) : null;
      if (!ac) continue;
      if (!thisRun.has(ac)) thisRun.set(ac, []);
      thisRun.get(ac).push(result);
    }
    for (const [ac, list] of thisRun) out.set(ac, list);
  }
  return out;
}

/** Qué pruebas no citan su pre y su post, o citan una condición que no es de su criterio (AC-02). */
export function checkCitations(contract, runs) {
  const conditions = new Map();
  for (const [ac, entry] of Object.entries(contract.criteria)) {
    for (const kind of KINDS) for (const cond of entry[kind]) conditions.set(cond.id, [ac, kind]);
  }
  const tests = latestTests(runs, contract.uc_id);
  const uncited = [];
  const unknown = [];
  const cited = new Set();
  let checked = 0;
  for (const [ac, results] of tests) {
    results.forEach((result, i) => {
      checked += 1;
      const scenario = result.scenario;
      const label = cut(typeof scenario === 'string' && scenario ? scenario : `${ac} #${i + 1}`, 200);
      const citation = isObj(result.contract) ? result.contract : {};
      const lacks = [];
      for (const kind of KINDS) {
        const values = Array.isArray(citation[kind]) ? citation[kind] : [];
        let found = false;
        for (const raw of values) {
          const cond = normalizeCondition(raw);
          if (cond === null || !conditions.has(cond[0])) {
            unknown.push({ ac_id: ac, test: label, condition: cut(show(raw), 100), problem: 'no existe en el contrato' });
            continue;
          }
          const [condAc, condKind] = conditions.get(cond[0]);
          if (condAc !== ac) {
            unknown.push({ ac_id: ac, test: label, condition: cond[0], problem: `es de otro criterio (${condAc})` });
            continue;
          }
          if (condKind !== kind) {
            unknown.push({ ac_id: ac, test: label, condition: cond[0], problem: `es una ${condKind}, no una ${kind}` });
            continue;
          }
          found = true;
          cited.add(cond[0]);
        }
        if (!found) lacks.push(kind);
      }
      if (lacks.length) uncited.push({ ac_id: ac, test: label, missing: lacks });
    });
  }
  const notCited = [...conditions].filter(([id, [ac]]) => tests.has(ac) && !cited.has(id)).map(([id]) => id);
  return { tests_checked: checked, uncited, unknown, not_cited: notCited };
}

/** El informe completo de check_acceptance_contract, igual que el del servidor. */
export function contractReport({ contractContent, criteriaIds = null, ucId = null, resultsContent = null } = {}) {
  let contract;
  try {
    contract = parseContract(contractContent);
  } catch (e) {
    if (!(e instanceof ContractError)) throw e;
    return {
      success: false,
      code: 'INVALID_CONTRACT',
      error: `contract_content no es un contrato válido: ${e.message}. Escríbelo como dice `
        + 'doc/specs/results-json-spec.md («Contrato de cada criterio»).',
    };
  }
  const out = { success: true, uc_id: contract.uc_id, invalid: contract.invalid };
  Object.assign(out, checkContract(contract, criteriaIds || [], ucId));
  if (!criteriaIds || !criteriaIds.length) {
    out.notice = 'Sin uc_criteria solo se comprueba la forma del contrato: pasa los criterios vigentes '
      + 'de la UC para saber si falta alguno.';
  }
  let ok = !(out.missing.length || out.incomplete.length || out.invalid.length || out.uc_mismatch);
  const warnings = [];
  if (out.missing.length) {
    warnings.push(`Criterios sin contrato: ${out.missing.join(', ')}. Escribe su pre, su post y su `
      + 'undefined antes de generar sus pruebas.');
  }
  if (out.incomplete.length) {
    const listed = out.incomplete.map((i) => `${i.ac_id} (sin ${i.missing.join(' ni ')})`).join('; ');
    warnings.push(`Criterios con el contrato incompleto: ${listed}.`);
  }
  if (out.invalid.length) warnings.push(`El contrato tiene ${out.invalid.length} entradas que no valen: corrígelas.`);
  if (out.uc_mismatch) warnings.push(`El contrato es de ${out.uc_mismatch.found}, no de ${out.uc_mismatch.expected}.`);
  if (out.extra.length) warnings.push(`El contrato trae criterios que la UC no tiene: ${out.extra.join(', ')}.`);
  if (resultsContent !== null && resultsContent !== undefined) {
    let runs;
    try {
      runs = parseResults(resultsContent);
    } catch (e) {
      if (!(e instanceof ResultsError)) throw e;
      return { success: false, code: 'INVALID_RESULTS', error: `results_content no es un results.json válido: ${e.message}` };
    }
    const citations = checkCitations(contract, runs);
    out.citations = citations;
    ok = ok && !(citations.uncited.length || citations.unknown.length);
    if (citations.uncited.length) {
      warnings.push(`${citations.uncited.length} pruebas no citan su precondición y su postcondición: `
        + 'etiquétalas con @pre:AC-NN.preN y @post:AC-NN.postN.');
    }
    if (citations.unknown.length) {
      warnings.push(`${citations.unknown.length} citas no corresponden a una condición de su criterio.`);
    }
    if (citations.not_cited.length) {
      warnings.push(`Condiciones que ninguna prueba comprueba: ${citations.not_cited.slice(0, 20).join(', ')}.`);
    }
  }
  out.ok = ok;
  if (warnings.length) out.warnings = warnings;
  return out;
}
