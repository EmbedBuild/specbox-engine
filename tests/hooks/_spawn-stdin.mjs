/**
 * spawnSync con la entrada estándar desde un fichero, para las pruebas que mandan a un hook un
 * encargo grande.
 *
 * Con `spawnSync(..., { input })` y una entrada de decenas de KB (los 80 000 caracteres de las pruebas
 * de context-budget), el hijo a veces no recibe el fin de la entrada y se queda leyendo para siempre
 * (visto con node 26 en macOS: el bloque `hooks` del CI local llegaba a su límite de una hora). Un
 * fichero como entrada siempre termina. El tope de 30 s es solo una red: estas pruebas tardan ~0,2 s.
 */

import { spawnSync } from 'node:child_process';
import { closeSync, mkdtempSync, openSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export function spawnWithStdin(command, args, input, options = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'hook-stdin-'));
  const file = join(dir, 'stdin.json');
  writeFileSync(file, input);
  const fd = openSync(file, 'r');
  try {
    return spawnSync(command, args, { timeout: 30000, ...options, stdio: [fd, 'pipe', 'pipe'] });
  } finally {
    closeSync(fd);
    rmSync(dir, { recursive: true, force: true });
  }
}
