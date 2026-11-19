/**
 * lib/behavior-doc.mjs — el documento de comportamiento y el PRD superado (US-126 · UC-12605).
 *
 * Copia de `server/behavior_doc.py` para el hook app-docs-fragment (una prueba compara las dos):
 * - con FreeForm el hook calcula las secciones con su items.json (`sectionForStory`,
 *   `sectionFromItems`) y las historias sin nada pendiente (`completeStoriesFromItems`);
 * - con cualquier tablero, escribe las secciones en `doc/spec/<funcionalidad>.md`
 *   (`replaceStorySection`) y pone o quita la marca de superado del PRD (`markSuperseded`,
 *   `unmarkSuperseded`), que solo cuenta como línea propia de su cabecera (`isSuperseded`).
 */

const UC_NUM = /UC-(\d+)/;
const AC_ID = /\bAC-(\d+)\b/i;
const UC_PREFIX = /^\[?UC-\d+[a-z]?\]?\s*[:—–-]?\s*/;
const US_PREFIX = /^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*/;
const AC_PREFIX = /^\[?AC-\d+\]?\s*[:—–-]?\s*/i;
const US_ID_RE = /\bUS-\d+[a-z]?\b/g;
const US_ONLY = /^US-\d+[A-Z]?$/;
const SUPERSEDED_RE = /^\s*<!--\s*@specbox:prd\s+status="superseded"(?:\s+date="([^"]*)")?(?:\s+by="([^"]*)")?\s*-->\s*$/;
const FORMAT_MARK_RE = /^\s*<!--\s*@specbox:prd\s+format="\d+"\s*-->\s*$/;
const FENCE_RE = /^ {0,3}(`{3,}|~{3,})/;
const SUBHEADING_RE = /^#{2,6}(\s|$)/;
const DEFINING_RE = /^\s*[#>]/;

export const SPEC_DIR = 'doc/spec';
export const MAX_STORIES = 20;

const clean = (text) => String(text ?? '').split(/\s+/).filter(Boolean).join(' ');
/** Texto del tablero sin `<!--` ni `-->`: un criterio no puede abrir ni cerrar una marca. */
const safe = (text) => String(text).replaceAll('<!--', '&lt;!--').replaceAll('-->', '--&gt;');
/** Un valor que va dentro de una marca, sin comillas ni ángulos. */
const attr = (value) => String(value ?? '').replace(/["<>]/g, '');
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
  const title = safe(clean(story.title));
  const out = [start, `## ${story.us_id}${title ? ` — ${title}` : ''}`, ''];
  for (const uc of [...ucs].sort(ucOrder)) {
    const ucTitle = safe(clean(uc.title));
    out.push(`### ${uc.uc_id}${ucTitle ? `: ${ucTitle}` : ''}`, '');
    const criteria = [...(uc.criteria || [])].sort((a, b) => (a.ac_id < b.ac_id ? -1 : a.ac_id > b.ac_id ? 1 : 0));
    for (const ac of criteria) out.push(`- [${ac.done ? 'x' : ' '}] **${safe(ac.ac_id)}**: ${safe(ac.text)}`);
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

function storyOf(list, { ucId, usId }) {
  if (usId) return list.find((i) => has(i, 'US') && idOf(i, 'US') === String(usId).toUpperCase()) || null;
  const uc = list.find((i) => has(i, 'UC') && idOf(i, 'UC') === String(ucId || '').toUpperCase());
  return (uc && list.find((i) => has(i, 'US') && i.id === uc.parent_id)) || null;
}

/** La sección de una historia con el items.json de FreeForm, o null si no está. */
export function sectionForStory(items, usId) {
  const list = Array.isArray(items) ? items : [];
  const story = storyOf(list, { usId });
  const id = story ? idOf(story, 'US') : '';
  if (!US_ONLY.test(id)) return null;
  const ucs = list
    .filter((i) => has(i, 'UC') && i.parent_id === story.id && i.state === 'done')
    .map((item) => ({
      uc_id: idOf(item, 'UC'),
      title: clean(item.name).replace(UC_PREFIX, ''),
      criteria: list
        .filter((ac) => has(ac, 'AC') && ac.parent_id === item.id && ac.state !== 'archived')
        .map((ac) => criterion(ac.meta?.ac_id || '', ac.name, ac.state === 'done')),
    }));
  return { us_id: id, section: renderSection({ us_id: id, title: clean(story.name).replace(US_PREFIX, '') }, ucs) };
}

/** La historia de una UC (por `ucId`) o la dada (`usId`), en mayúsculas, o '' si no está. */
export function storyIdFromItems(items, { ucId, usId } = {}) {
  const story = storyOf(Array.isArray(items) ? items : [], { ucId, usId });
  const id = story ? idOf(story, 'US') : '';
  return US_ONLY.test(id) ? id : '';
}

/** La sección de la historia de `ucId` con el items.json de FreeForm, o null si no la encuentra. */
export function sectionFromItems(items, ucId) {
  const usId = storyIdFromItems(items, { ucId });
  return usId ? sectionForStory(items, usId) : null;
}

/**
 * Las historias sin nada pendiente, como `complete_stories` del servidor: archivadas, o con UC y
 * todas las no archivadas cerradas (una sin UC no está completa; una con todas archivadas, sí).
 */
export function completeStoriesFromItems(items) {
  const list = Array.isArray(items) ? items : [];
  const rows = new Map();
  for (const item of list) {
    if (!has(item, 'US')) continue;
    const usId = idOf(item, 'US');
    if (US_ONLY.test(usId)) rows.set(item.id, { us_id: usId, archived: item.state === 'archived', ucs: 0, open: 0 });
  }
  for (const item of list) {
    const row = has(item, 'UC') ? rows.get(item.parent_id) : undefined;
    if (!row) continue;
    row.ucs += 1;
    if (item.state !== 'done' && item.state !== 'archived') row.open += 1;
  }
  const out = [];
  for (const row of rows.values()) {
    if ((row.archived || (row.ucs && !row.open)) && !out.includes(row.us_id)) out.push(row.us_id);
  }
  return out;
}

export function docHeader(feature) {
  return (
    `# Comportamiento: ${feature}\n\n` +
    '> Lo que el sistema hace hoy: una sección por historia, con los criterios de sus UC cerradas.\n' +
    '> Lo escribe el engine al cerrar cada UC y se regenera desde el tablero: no lo\n' +
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

/** ¿Tiene el documento la sección entera de la historia? */
export function hasStorySection(doc, usId) {
  const [start, end] = sectionMarks(usId);
  const i = String(doc || '').indexOf(start);
  return i >= 0 && String(doc).indexOf(end, i) >= 0;
}

/** Sigue los bloques de código vallados línea a línea: `code(line)` dice si la línea es código. */
export function fences() {
  let open = null;
  return {
    code(line) {
      const m = FENCE_RE.exec(line);
      if (open) {
        const fence = m ? m[1] : '';
        if (fence && fence[0] === open[0] && fence.length >= open.length && !line.slice(m[0].length).trim()) open = null;
        return true;
      }
      if (m) {
        open = m[1];
        return true;
      }
      return false;
    },
  };
}

/** Los índices de la cabecera: las líneas antes del primer subtítulo (`## …`), fuera de código. */
function header(lines) {
  const f = fences();
  const out = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (f.code(lines[i])) continue;
    if (SUBHEADING_RE.test(lines[i])) break;
    out.push(i);
  }
  return out;
}

/** ¿Lleva el PRD la marca de superado como línea propia de su cabecera? */
export function isSuperseded(text) {
  const lines = String(text || '').split('\n');
  return header(lines).some((i) => SUPERSEDED_RE.test(lines[i]));
}

export function supersededMark(date, by) {
  return `<!-- @specbox:prd status="superseded" date="${attr(date)}" by="${attr(by)}" -->`;
}

/** El PRD con la marca de superado debajo de la de formato (o del título); igual si ya la tiene. */
export function markSuperseded(prd, date, by) {
  if (isSuperseded(prd)) return prd;
  const mark = supersededMark(date, by);
  const lines = String(prd).split('\n');
  const head = header(lines);
  let at = head.find((i) => FORMAT_MARK_RE.test(lines[i]));
  if (at === undefined) at = head.find((i) => lines[i].startsWith('# '));
  if (at === undefined) return `${mark}\n${prd}`;
  return [...lines.slice(0, at + 1), mark, ...lines.slice(at + 1)].join('\n');
}

/** El PRD sin la marca que puso el engine con ese documento (`by`); una marca con otro `by` se queda. */
export function unmarkSuperseded(prd, by) {
  const lines = String(prd).split('\n');
  const drop = new Set(header(lines).filter((i) => SUPERSEDED_RE.exec(lines[i])?.[2] === by));
  if (!drop.size) return prd;
  return lines.filter((_, i) => !drop.has(i)).join('\n');
}

/**
 * Las historias que define un PRD: las que nombran sus encabezados o las líneas «>» de su cabecera,
 * fuera de código. Una «>» del cuerpo es una cita, no una historia que el PRD defina.
 */
export function prdStories(prd) {
  const lines = String(prd || '').split('\n');
  const head = new Set(header(lines));
  const found = [];
  const f = fences();
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (f.code(line) || !DEFINING_RE.test(line)) continue;
    if (line.trimStart().startsWith('>') && !head.has(i)) continue;
    for (const m of line.matchAll(US_ID_RE)) {
      const us = m[0].toUpperCase();
      if (!found.includes(us)) found.push(us);
    }
  }
  return found;
}

/** La funcionalidad de un PRD por su ruta: su carpeta (doc/prd/<f>/prd.md) o su nombre sin «_prd». */
export function featureOf(prdRel) {
  const parts = String(prdRel).split('/');
  if (parts.length >= 4 && parts[0] === 'doc' && parts[1] === 'prd') return parts[2];
  return parts.at(-1).replace(/\.md$/i, '').replace(/_prd$/i, '');
}
