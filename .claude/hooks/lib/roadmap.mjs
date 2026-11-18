/**
 * lib/roadmap.mjs — la zona «roadmap» de app_prd.md con lo que dice el tablero (UC-12203).
 *
 * Copia de `server/app_docs/roadmap.py` para FreeForm por fragmentos: el servidor no ve el tablero
 * entero y el hook calcula el mismo cuerpo con su items.json. tests/test_app_docs_roadmap.py compara
 * las dos salidas. `replaceZone` reemplaza el cuerpo como `replace_zone_body` (por líneas, sin tocar
 * los marcadores ni lo de fuera).
 */

const US_PREFIX = /^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*/;
const US_ID = /^\[?(US-\d+[a-z]?)/;
const US_NUMBER = /^US-(\d+)/;

function title(name, usId) {
  const text = usId ? String(name || '').trim().replace(US_PREFIX, '') : String(name || '').trim();
  return text.split(/\s+/).filter(Boolean).join(' ').replace(/\|/g, '\\|');
}

function order(a, b) {
  const na = US_NUMBER.exec(a.us_id);
  const nb = US_NUMBER.exec(b.us_id);
  const ka = na ? Number(na[1]) : 1e9;
  const kb = nb ? Number(nb[1]) : 1e9;
  if (ka !== kb) return ka - kb;
  return a.us_id < b.us_id ? -1 : a.us_id > b.us_id ? 1 : 0;
}

const has = (item, label) => Array.isArray(item?.labels) && item.labels.includes(label);

/** Una fila por historia no archivada: id, título, estado y UC hechas/total (sin archivadas). */
export function rowsFromItems(items) {
  const stories = new Map();
  for (const item of items || []) {
    if (!has(item, 'US') || item.state === 'archived') continue;
    const usId = item.meta?.us_id || US_ID.exec(item.name || '')?.[1] || '';
    if (usId) stories.set(item.id, { us_id: usId, title: title(item.name, usId), state: item.state || '', done: 0, total: 0 });
  }
  for (const item of items || []) {
    if (!has(item, 'UC') || item.state === 'archived' || !stories.has(item.parent_id)) continue;
    const row = stories.get(item.parent_id);
    row.total += 1;
    if (item.state === 'done') row.done += 1;
  }
  return [...stories.values()].sort(order);
}

/** El cuerpo de la zona; mismo texto que `render` del servidor. */
export function render(rows) {
  const out = [
    '## 5. Roadmap de US',
    '',
    '> Esta zona la mantiene el engine con lo que dice el tablero: se regenera tras complete_uc, ' +
      'move_uc, add_uc, delete_uc y mark_ac_batch. No la edites a mano.',
    '',
    '| US | Título | Estado | UCs |',
    '|----|--------|--------|-----|',
  ];
  if (!rows.length) out.push('| (sin historias) | | | |');
  for (const r of rows) out.push(`| ${r.us_id} | ${r.title} | ${r.state} | ${r.done}/${r.total} |`);
  return out.join('\n');
}

const START = (id) => new RegExp(`<!--\\s*@specbox:zone start\\b[^>]*\\bid=["']${id}["'][^>]*-->`);
const END = /<!--\s*@specbox:zone end\s*-->/;

/** `content` con el cuerpo de la zona `zoneId` cambiado por `body`, o null si no tiene esa zona. */
export function replaceZone(content, zoneId, body) {
  const lines = String(content).split('\n');
  const trailing = String(content).endsWith('\n');
  if (trailing) lines.pop();
  const start = lines.findIndex((l) => START(zoneId).test(l));
  if (start < 0) return null;
  const end = lines.findIndex((l, i) => i > start && END.test(l));
  if (end < 0) return null;
  const rebuilt = [...lines.slice(0, start + 1), ...(body ? body.split('\n') : []), ...lines.slice(end)];
  return rebuilt.join('\n') + (trailing ? '\n' : '');
}
