/**
 * app-spec-zones.mjs — lee las zonas automáticas de `doc/app/app_spec.md` (UC-12205).
 *
 * Un marcador de apertura lleva sus atributos en cualquier orden y puede traer otros
 * además de `kind` e `id` (la plantilla añade `auto_sync_on`, las zonas híbridas `merge`):
 *
 *   <!-- @specbox:zone start kind="auto" id="stack" auto_sync_on="lockfile_change" -->
 *   …
 *   <!-- @specbox:zone end -->
 *
 * Antes la expresión exigía el cierre `-->` justo después del id y no casaba con ninguna
 * zona de la plantilla, así que el arranque de sesión nunca las inyectaba.
 */

const ZONE_RE = /<!--\s*@specbox:zone start\b([\s\S]*?)-->([\s\S]*?)<!--\s*@specbox:zone end\s*-->/g;
const ATTR_RE = /([A-Za-z_][\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;

/** Zonas automáticas que el arranque de sesión inyecta, en este orden. */
export const SESSION_ZONES = ['stack', 'tracking_backend', 'autopilot'];

/** Atributos del marcador de apertura (`kind`, `id`, `auto_sync_on`…), en cualquier orden. */
export function zoneAttributes(raw) {
  const attrs = {};
  for (const m of String(raw ?? '').matchAll(ATTR_RE)) {
    attrs[m[1]] = m[2] ?? m[3] ?? '';
  }
  return attrs;
}

/**
 * Devuelve `{id: contenido}` de las zonas `kind="auto"` cuyo id está en `wanted`.
 * Ignora las zonas manuales e híbridas y las que no se piden.
 */
export function parseAutoZones(content, wanted = SESSION_ZONES) {
  const zones = {};
  if (typeof content !== 'string') return zones;
  for (const m of content.matchAll(ZONE_RE)) {
    const attrs = zoneAttributes(m[1]);
    if (attrs.kind !== 'auto' || !wanted.includes(attrs.id)) continue;
    zones[attrs.id] = m[2].trim();
  }
  return zones;
}
