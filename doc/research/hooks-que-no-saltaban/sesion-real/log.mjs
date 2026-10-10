import { appendFileSync, readFileSync } from 'node:fs';
let p = {};
try { p = JSON.parse(readFileSync(0, 'utf8') || '{}'); } catch {}
const ti = p.tool_input || {};
appendFileSync(process.env.HITS_LOG, `${process.argv[2]}\t${p.hook_event_name}\t${p.tool_name}\t${ti.command || ti.file_path || ''}\n`);
process.exit(0);
