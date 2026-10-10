// Construye un settings.json con las entradas condicionadas de un settings del engine, cada una con un registrador.
import { readFileSync, writeFileSync } from 'node:fs';
const [, , src, dst, log] = process.argv;
const s = JSON.parse(readFileSync(src, 'utf8'));
const out = { hooks: {} };
for (const [ev, groups] of Object.entries(s.hooks)) {
  for (const g of groups) {
    const hooks = g.hooks.filter((h) => h.if).map((h) => ({ type: 'command', if: h.if, command: `node ${log} "${h.command.match(/hooks\/([a-z0-9-]+)\.mjs/)[1]}"`, timeout: 10 }));
    if (hooks.length) (out.hooks[ev] ??= []).push({ matcher: g.matcher, hooks });
  }
}
writeFileSync(dst, JSON.stringify(out, null, 2));
