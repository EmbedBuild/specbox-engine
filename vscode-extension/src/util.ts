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

/** The filesystem calls symlinkOrCopy makes; tests pass a simulated one (UC-9601 AC-04). */
export interface LinkFs {
	lstatSync(p: string): { isSymbolicLink(): boolean };
	readlinkSync(p: string): string;
	unlinkSync(p: string): void;
	rmdirSync(p: string): void;
	rmSync(p: string, opts: fs.RmOptions): void;
	mkdirSync(p: string, opts: fs.MakeDirectoryOptions): void;
	symlinkSync(target: string, p: string, type: 'junction' | 'file'): void;
	cpSync(src: string, dest: string, opts: fs.CopySyncOptions): void;
	copyFileSync(src: string, dest: string): void;
}

/**
 * Create a symlink (file or dir) — a junction for directories on Windows. Falls back to copy on
 * Windows if the link fails. Returns what it did: `kept` (the link already pointed at `src`),
 * `linked` or `copied`.
 *
 * UC-9601 — an existing link or junction is never deleted recursively: on Windows that goes
 * through the junction and empties the folder it points to (the managed engine clone lost all its
 * skills that way on the second install). A link pointing elsewhere is removed on its own; only a
 * real directory or file (an earlier copy) is deleted recursively.
 */
export function symlinkOrCopy(src: string, dest: string, type: 'file' | 'dir' = 'dir', lfs: LinkFs = fs): 'kept' | 'linked' | 'copied' {
	lfs.mkdirSync(path.dirname(dest), { recursive: true });
	const existing = lstatOrNull(lfs, dest);
	if (existing?.isSymbolicLink()) {
		if (linkPointsTo(lfs, dest, src)) { return 'kept'; }
		removeLinkOnly(lfs, dest);
	} else if (existing) {
		lfs.rmSync(dest, { recursive: true, force: true });
	}
	try {
		lfs.symlinkSync(src, dest, type === 'dir' ? 'junction' : 'file');
		return 'linked';
	} catch {
		// Fallback: copy (Windows without dev mode / elevated)
		log(`Symlink failed for ${src}, falling back to copy`);
		if (type === 'dir') {
			lfs.cpSync(src, dest, { recursive: true });
		} else {
			lfs.copyFileSync(src, dest);
		}
		return 'copied';
	}
}

function lstatOrNull(lfs: LinkFs, p: string): { isSymbolicLink(): boolean } | null {
	try {
		return lfs.lstatSync(p);
	} catch {
		return null;
	}
}

/** Does the link at `link` point at `target`? Relative targets resolve against the link's folder. */
function linkPointsTo(lfs: LinkFs, link: string, target: string): boolean {
	let raw: string;
	try {
		raw = lfs.readlinkSync(link);
	} catch {
		return false;
	}
	const resolved = path.resolve(path.dirname(link), raw.replace(/^\\\\\?\\/, ''));
	const wanted = path.resolve(target);
	return os.platform() === 'win32' ? resolved.toLowerCase() === wanted.toLowerCase() : resolved === wanted;
}

/**
 * Remove a link without following it. unlink removes a symlink and, on Windows, a junction too
 * (libuv removes directory reparse points with RemoveDirectory); rmdir is the non-recursive
 * fallback for a directory link. Neither ever deletes what the link points to.
 */
function removeLinkOnly(lfs: LinkFs, p: string): void {
	try {
		lfs.unlinkSync(p);
	} catch {
		lfs.rmdirSync(p);
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
