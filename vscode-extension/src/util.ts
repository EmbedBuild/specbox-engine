import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const log = (...args: unknown[]) => console.log('[SpecBox]', ...args);

/** Run a shell command and return stdout, or null on failure. */
export function exec(cmd: string, cwd?: string): Promise<string | null> {
	return new Promise(resolve => {
		const shell = os.platform() === 'win32' ? 'cmd.exe' : '/bin/sh';
		const flag = os.platform() === 'win32' ? '/c' : '-c';
		cp.execFile(shell, [flag, cmd], { cwd, timeout: 15_000 }, (err, stdout) => {
			if (err) {
				log(`Command failed: ${cmd}`, err.message);
			}
			resolve(err ? null : stdout.trim());
		});
	});
}

/** Check if a command exists on PATH. */
export async function commandExists(cmd: string): Promise<boolean> {
	const check = os.platform() === 'win32' ? `where ${cmd}` : `which ${cmd}`;
	return (await exec(check)) !== null;
}

/** Ensure a directory exists (recursive). */
export function ensureDir(dir: string): void {
	if (!fs.existsSync(dir)) {
		fs.mkdirSync(dir, { recursive: true });
	}
}

/** Copy a file, creating parent dirs as needed. */
export function copyFile(src: string, dest: string): void {
	ensureDir(path.dirname(dest));
	fs.copyFileSync(src, dest);
}

/** Create a symlink (file or dir). Falls back to copy on Windows if symlink fails. */
export function symlinkOrCopy(src: string, dest: string, type: 'file' | 'dir' = 'dir'): void {
	ensureDir(path.dirname(dest));
	// Remove existing
	if (fs.existsSync(dest) || isSymlink(dest)) {
		fs.rmSync(dest, { recursive: true, force: true });
	}
	try {
		fs.symlinkSync(src, dest, type === 'dir' ? 'junction' : 'file');
	} catch {
		// Fallback: copy (Windows without dev mode / elevated)
		log(`Symlink failed for ${src}, falling back to copy`);
		if (type === 'dir') {
			fs.cpSync(src, dest, { recursive: true });
		} else {
			fs.copyFileSync(src, dest);
		}
	}
}

function isSymlink(p: string): boolean {
	try {
		return fs.lstatSync(p).isSymbolicLink();
	} catch {
		return false;
	}
}

/** Read a JSON file, return null on failure. */
export function readJson<T = unknown>(filePath: string): T | null {
	try {
		return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
	} catch {
		return null;
	}
}

/** Write JSON to file with pretty-print. */
export function writeJson(filePath: string, data: unknown): void {
	ensureDir(path.dirname(filePath));
	fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
}

/**
 * Parse YAML top-level scalars (no lib dependency).
 * Handles: unquoted, single-quoted, double-quoted values, and inline comments.
 * Does NOT handle nested structures, multiline, or anchors.
 */
export function parseSimpleYaml(content: string): Record<string, string> {
	const result: Record<string, string> = {};
	for (const line of content.split('\n')) {
		// Skip comments, blank lines, and indented lines (nested)
		if (/^\s*#/.test(line) || /^\s*$/.test(line) || /^\s{2,}/.test(line)) {
			continue;
		}
		// Match: key: "value" or key: 'value' or key: value  # optional comment
		const m = line.match(/^([\w][\w-]*)\s*:\s*(?:"([^"]*)"|'([^']*)'|([^#\n]*))/);
		if (m) {
			const value = (m[2] ?? m[3] ?? m[4] ?? '').trim();
			result[m[1]] = value;
		}
	}
	return result;
}
