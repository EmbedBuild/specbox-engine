import * as fs from 'fs';
import * as path from 'path';

export interface SkillInfo {
	name: string;
	description: string;
	source: 'local' | 'global';
	skillMdPath: string;
	hasFrontmatter: boolean;
}

export interface FrontmatterFields {
	name?: string;
	description?: string;
}

const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)/;

export function parseSkillFrontmatter(content: string): FrontmatterFields {
	const match = content.match(FRONTMATTER_RE);
	if (!match) { return {}; }

	const result: FrontmatterFields = {};
	const lines = match[1].split('\n');
	for (const line of lines) {
		const colonIdx = line.indexOf(':');
		if (colonIdx === -1) { continue; }
		const key = line.slice(0, colonIdx).trim();
		let value = line.slice(colonIdx + 1).trim();
		if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
			value = value.slice(1, -1);
		}
		if (key === 'name') { result.name = value; }
		else if (key === 'description') { result.description = value; }
	}
	return result;
}

function readSkillDir(dir: string, source: 'local' | 'global', onError: (e: unknown, path: string) => void): SkillInfo[] {
	const out: SkillInfo[] = [];
	let entries: fs.Dirent[];
	try {
		entries = fs.readdirSync(dir, { withFileTypes: true });
	} catch (err) {
		onError(err, dir);
		return out;
	}

	for (const entry of entries) {
		if (!entry.isDirectory()) { continue; }
		const skillMdPath = path.join(dir, entry.name, 'SKILL.md');
		if (!fs.existsSync(skillMdPath)) { continue; }

		let content: string;
		try {
			content = fs.readFileSync(skillMdPath, 'utf8');
		} catch (err) {
			onError(err, skillMdPath);
			continue;
		}

		const fm = parseSkillFrontmatter(content);
		out.push({
			name: entry.name,
			description: fm.description ?? '',
			source,
			skillMdPath,
			hasFrontmatter: fm.description !== undefined || fm.name !== undefined,
		});
	}
	return out;
}

export interface SkillLoaderInput {
	localPaths: string[];
	globalPaths: string[];
	onError?: (e: unknown, path: string) => void;
}

export function loadSkillsFromFilesystem(input: SkillLoaderInput): SkillInfo[] {
	const onError = input.onError ?? (() => { /* silent */ });
	const dedup = new Map<string, SkillInfo>();

	for (const dir of input.localPaths) {
		for (const skill of readSkillDir(dir, 'local', onError)) {
			if (!dedup.has(skill.name)) { dedup.set(skill.name, skill); }
		}
	}
	for (const dir of input.globalPaths) {
		for (const skill of readSkillDir(dir, 'global', onError)) {
			if (!dedup.has(skill.name)) { dedup.set(skill.name, skill); }
		}
	}

	return [...dedup.values()].sort((a, b) => a.name.localeCompare(b.name));
}
