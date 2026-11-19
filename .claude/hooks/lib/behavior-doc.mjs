/**
 * lib/behavior-doc.mjs — el documento de comportamiento y el PRD superado (US-126 · UC-12605).
 *
 * Copia de `server/behavior_doc.py` para el hook app-docs-fragment:
 * - con FreeForm por fragmentos el servidor no ve el tablero entero y el hook calcula la sección de
 *   la historia con su items.json (`sectionFromItems`, `completeStoriesFromItems`); una prueba
 *   compara la salida con la del servidor;
 * - con cualquier tablero, el hook escribe la sección en `doc/spec/<funcionalidad>.md`
 *   (`replaceStorySection`) y marca el PRD cuyas historias están todas cerradas (`markSuperseded`).
 */

const UC_NUM = /UC-(\d+)/;
const AC_ID = /\bAC-(\d+)\b/i;
const UC_PREFIX = /^\[?UC-\d+[a-z]?\]?\s*[:—–-]?\s*/;
const US_PREFIX = /^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*/;
const AC_PREFIX = /^\[?AC-\d+\]?\s*[:—–-]?\s*/i;
const US_ID_RE = /\bUS-\d+[a-z]?\b/g;
const SUPERSEDED_RE = /<!--\s*@specbox:prd\s+status="superseded"(?:\s+date="([^"]*)")?(?:\s+by="([^"]*)")?\s*-->/;
const FORMAT_MARK_RE = /^\s*<!--\s*@specbox:prd\s+format="\d+"\s*-->\s*$/;

export const SPEC_DIR = 'doc/spec';

const clean = (text) => String(text ?? '').split(/\s+/).filter(Boolean).join(' ');
const has = (item, label) => Array.isArray(item?.labels) && item.labels.includes(label);

function ucOrder(a, b) {
  const na = UC_NUM.exec(a.uc_id);
  const nb = UC_NUM.exec(b.uc_id);
  const ka = na ? Number(na[1]) : 1e9;
  const kb = nb ? Number(nb[1]) : 1e9;
  if (ka !== kb) return ka - kb;
  return a.uc_id < b.uc_id ? -1 : a.uc_id > b.uc_id ? 1 : 0;
}

function acId(rawId, text) {
  const m = AC_ID.exec(rawId || '') || new RegExp(`^${AC_ID.source}`, 'i').exec(clean(text));
  return m ? `AC-${String(Number(m[1])).padStart(2, '0')}` : clean(rawId);
}

/** Un criterio normalizado, como `criterion` del servidor. */
export function criterion(rawId, text, done) {
  return { ac_id: acId(rawId, text), text: clean(clean(text).replace(AC_PREFIX, '')), done: !!done };
}

export function sectionMarks(usId) {
  return [`<!-- @specbox:spec us="${usId}" start -->`, `<!-- @specbox:spec us="${usId}" end -->`];
}

/** La sección de una historia; mismo texto que `render_section` del servidor. */
export function renderSection(story, ucs) {
  const [start, end] = sectionMarks(story.us_id);
  const title = clean(story.title);
  const out = [start, `## ${story.us_id}${title ? ` — ${title}` : ''}`, ''];
  for (const uc of [...ucs].sort(ucOrder)) {
    const ucTitle = clean(uc.title);
    out.push(`### ${uc.uc_id}${ucTitle ? `: ${ucTitle}` : ''}`, '');
    const criteria = [...(uc.criteria || [])].sort((a, b) => (a.ac_id < b.ac_id ? -1 : a.ac_id > b.ac_id ? 1 : 0));
    for (const ac of criteria) out.push(`- [${ac.done ? 'x' : ' '}] **${ac.ac_id}**: ${ac.text}`);
    out.push('');
  }
  if (!ucs.length) out.push('_(ninguna UC cerrada todavía)_', '');
  out.push(end);
  return out.join('\n');
}

const idOf = (item, prefix) => {
  const meta = item?.meta || {};
  const fromMeta = meta[`${prefix.toLowerCase()}_id`];
  if (fromMeta) return String(fromMeta).toUpperCase();
  const m = new RegExp(`^\\[?(${prefix}-\\d+[a-z]?)\\]?`, 'i').exec(String(item?.name || '').trim());
  return m ? m[1].toUpperCase() : '';
};

/** La sección de la historia de `ucId` con el items.json de FreeForm, o null si no la encuentra. */
export function sectionFromItems(items, ucId) {
  const list = Array.isArray(items) ? items : [];
  const uc = list.find((i) => has(i, 'UC') && idOf(i, 'UC') === String(ucId).toUpperCase());
  const story = uc && list.find((i) => has(i, 'US') && i.id === uc.parent_id);
  if (!story) return null;
  const ucs = list
    .filter((i) => has(i, 'UC') && i.parent_id === story.id && i.state === 'done')
    .map((item) => ({
      uc_id: idOf(item, 'UC'),
      title: clean(item.name).replace(UC_PREFIX, ''),
      criteria: list
        .filter((ac) => has(ac, 'AC') && ac.parent_id === item.id && ac.state !== 'archived')
        .map((ac) => criterion(ac.meta?.ac_id || '', ac.name, ac.state === 'done')),
    }));
  const usId = idOf(story, 'US');
  return { us_id: usId, section: renderSection({ us_id: usId, title: clean(story.name).replace(US_PREFIX, '') }, ucs) };
}

/** Las historias con todas sus UC cerradas (sin contar las archivadas), como el servidor. */
export function completeStoriesFromItems(items) {
  const list = Array.isArray(items) ? items : [];
  const stories = new Map();
  for (const item of list) {
    if (has(item, 'US') && item.state !== 'archived') {
      const usId = idOf(item, 'US');
      if (usId) stories.set(item.id, { us_id: usId, done: 0, total: 0 });
    }
  }
  for (const item of list) {
    if (!has(item, 'UC') || item.state === 'archived' || !stories.has(item.parent_id)) continue;
    const row = stories.get(item.parent_id);
    row.total += 1;
    if (item.state === 'done') row.done += 1;
  }
  return [...stories.values()].filter((r) => r.total && r.done === r.total).map((r) => r.us_id);
}

export function docHeader(feature) {
  return (
    `# Comportamiento: ${feature}\n\n` +
    '> Lo que el sistema hace hoy: una sección por historia, con los criterios de sus UC cerradas.\n' +
    '> Lo escribe el engine al cerrar cada UC (UC-12605) y se regenera desde el tablero: no lo\n' +
    '> edites a mano. Los PRD siguen siendo el historial de cada cambio.\n'
  );
}

/** El documento con la sección de la historia puesta; mismo resultado que el servidor. */
export function replaceStorySection(doc, usId, section, feature) {
  const text = String(doc || '').trim() ? String(doc) : docHeader(feature);
  const [start, end] = sectionMarks(usId);
  const i = text.indexOf(start);
  const j = i >= 0 ? text.indexOf(end, i) : -1;
  if (i >= 0 && j >= 0) return text.slice(0, i) + section + text.slice(j + end.length);
  return `${text.replace(/\n+$/, '')}\n\n${section}\n`;
}

export const isSuperseded = (text) => SUPERSEDED_RE.test(String(text || ''));

export function supersededMark(date, by) {
  return `<!-- @specbox:prd status="superseded" date="${date}" by="${by}" -->`;
}

/** El PRD con la marca de superado debajo de la de formato (o del título); igual si ya la tiene. */
export function markSuperseded(prd, date, by) {
  if (isSuperseded(prd)) return prd;
  const mark = supersededMark(date, by);
  const lines = String(prd).split('\n');
  let at = lines.findIndex((line) => FORMAT_MARK_RE.test(line));
  if (at < 0) at = lines.findIndex((line) => line.startsWith('# '));
  if (at < 0) return `${mark}\n${prd}`;
  return [...lines.slice(0, at + 1), mark, ...lines.slice(at + 1)].join('\n');
}

/** Las historias que define un PRD: las que nombran sus encabezados. */
export function prdStories(prd) {
  const found = [];
  for (const line of String(prd || '').split('\n')) {
    if (!line.trimStart().startsWith('#')) continue;
    for (const m of line.matchAll(US_ID_RE)) if (!found.includes(m[0])) found.push(m[0]);
  }
  return found;
}

/** La funcionalidad de un PRD por su ruta: su carpeta (doc/prd/<f>/prd.md) o su nombre sin «_prd». */
export function featureOf(prdRel) {
  const parts = String(prdRel).split('/');
  if (parts.length >= 4 && parts[0] === 'doc' && parts[1] === 'prd') return parts[2];
  return parts.at(-1).replace(/\.md$/i, '').replace(/_prd$/i, '');
}
