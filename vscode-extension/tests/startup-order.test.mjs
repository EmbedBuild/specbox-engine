// US-118 (UC-11801 AC-06) — the usage events start before anything in the
// startup chain that can wait for the person.
//
// In 6.33.0 `maybeEmitActivation` ran at the end of runStartupTasks, behind
// notifications that are awaited until someone clicks (the «not installed — run
// the setup wizard?» one appears on every clean install). A clean install from
// the Marketplace was therefore never counted. extension.ts needs half the VS
// Code API to load, so this test reads its source: inside runStartupTasks the
// usage events are fired, not awaited, before the first `await`.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.resolve(__dirname, '..', 'src', 'extension.ts'), 'utf8');

function functionBody(src, signature) {
	const start = src.indexOf(signature);
	assert.ok(start >= 0, `no encuentro «${signature}» en extension.ts`);
	const open = src.indexOf('{', src.indexOf(')', start));
	let depth = 0;
	for (let i = open; i < src.length; i++) {
		if (src[i] === '{') { depth++; }
		if (src[i] === '}' && --depth === 0) { return src.slice(open + 1, i); }
	}
	throw new Error(`«${signature}» no se cierra`);
}

// Only code, without comments, so a comment that mentions `await` does not count.
const code = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

test('UC-11801 AC-06: activation and heartbeat start before the first await of the startup chain', () => {
	const body = code(functionBody(source, 'async function runStartupTasks('));
	const usage = body.indexOf('maybeEmitActivation(');
	const firstAwait = body.search(/\bawait\b/);
	assert.ok(usage >= 0, 'runStartupTasks ya no lanza maybeEmitActivation');
	assert.ok(firstAwait >= 0, 'runStartupTasks no tiene ningún await (¿ha cambiado la estructura?)');
	assert.ok(usage < firstAwait, 'maybeEmitActivation tiene que ir antes del primer await de runStartupTasks');
});

test('UC-11801 AC-06: the usage events are fired without await and chain the heartbeat', () => {
	const body = code(functionBody(source, 'async function runStartupTasks('));
	assert.match(body, /void maybeEmitActivation\(context\)\.then\(\(\) => startHeartbeat\(context\)\)/);
	assert.doesNotMatch(body, /await\s+maybeEmitActivation/);
	// One single place starts them: twice would double the startup work.
	assert.equal(code(source).split('maybeEmitActivation(context)').length - 1, 1);
});
