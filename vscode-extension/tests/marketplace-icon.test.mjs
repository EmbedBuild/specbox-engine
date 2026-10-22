// UC-9606 (US-96) — la extensión se publica en el Marketplace con un icono que acepta.
//
// AC-02 · Esta prueba falla si el icono que declara package.json pasa de 1024×1024 píxeles.
//
// La publicación de la v6.26.0 falló con «The provided icon image exceeds the maximum allowed dimensions
// of 1024 by 1024 pixels»: el icono medía 1200×1200 desde la v5.21.0 y el Marketplace empezó a exigirlo.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MAX = 1024;

/** Ancho y alto de un PNG, leídos de su cabecera IHDR. */
function pngSize(file) {
	const buf = fs.readFileSync(file);
	assert.equal(buf.toString('latin1', 1, 4), 'PNG', `${file} no es un PNG`);
	return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

test('AC-02 · el icono de la extensión cabe en el límite del Marketplace (1024×1024)', () => {
	const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'));
	assert.ok(pkg.icon, 'package.json declara un icono');
	const { width, height } = pngSize(path.join(root, pkg.icon));
	assert.ok(width <= MAX && height <= MAX, `${pkg.icon} mide ${width}×${height}; el Marketplace admite hasta ${MAX}×${MAX}`);
	assert.equal(width, height, 'cuadrado');
});
