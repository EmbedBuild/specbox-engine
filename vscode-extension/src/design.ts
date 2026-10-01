import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

/**
 * UC-4903 — las páginas web de la extensión (retorno de la conexión OAuth y diagnóstico) hablan
 * el idioma visual del sistema único «Tinta» (D18): tokens de @specbox/tokens, IBM Plex, el
 * símbolo de la caja marcada e iconos Lucide con nombre accesible.
 *
 * Los tokens llegan VENDORIZADOS a media/tokens/ con `npm run sync -- specbox-engine` en
 * packages/tokens del orquestador (specbox-manager) y el símbolo a media/brand/: no se editan aquí.
 * Este módulo no escribe ningún color: solo usa variables del sistema.
 */

const MEDIA = path.join(__dirname, '..', 'media');

export type PageTheme = 'light' | 'dark';

/**
 * El tema de la página sigue al de VSCode; oscuro por defecto (contrato: la extensión arranca en
 * oscuro). ColorThemeKind: 1 Light, 2 Dark, 3 HighContrast, 4 HighContrastLight.
 */
export function pageTheme(kind?: number): PageTheme {
	const k = kind ?? vscode.window?.activeColorTheme?.kind;
	return k === 1 || k === 4 ? 'light' : 'dark';
}

function readMedia(...parts: string[]): string {
	try {
		return fs.readFileSync(path.join(MEDIA, ...parts), 'utf8');
	} catch {
		return '';
	}
}

/** Variables del sistema (escala, densidad y los dos temas) para incrustar en la página. */
export function tokensCss(): string {
	return ['foundation.css', 'semantic-light.css', 'semantic-dark.css']
		.map((f) => readMedia('tokens', f))
		.join('\n');
}

/** La caja marcada: tinta sobre papel claro, papel sobre oscuro. Decorativa (el nombre va al lado). */
export function brandMark(theme: PageTheme, size = 28): string {
	const svg = readMedia('brand', theme === 'dark' ? 'specbox-mark-paper.svg' : 'specbox-mark-ink.svg');
	if (!svg) { return ''; }
	return svg
		.replace(/<\?xml[^>]*>\s*/, '')
		.replace(/<svg\b/, `<svg aria-hidden="true" focusable="false" width="${size}" height="${size}" class="brand-mark"`);
}

/** Iconos de Lucide que usan las páginas (datos de lucide 0.469, licencia ISC). */
const LUCIDE: Record<string, string> = {
	'circle-check': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
	'circle-x': '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
	'circle-alert': '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
};

/**
 * Un icono de Lucide al grosor del sistema (--icon-stroke en píxeles de pantalla), 16 o 20 px.
 * Con `label` es una imagen con nombre; sin él, decorativo (aria-hidden) porque lleva texto al lado.
 */
export function lucideIcon(name: keyof typeof LUCIDE, opts: { label?: string; size?: 16 | 20 } = {}): string {
	const size = opts.size ?? 20;
	const a11y = opts.label ? `role="img" aria-label="${escapeHtml(opts.label)}"` : 'aria-hidden="true"';
	return `<svg xmlns="http://www.w3.org/2000/svg" class="lucide lucide-${name}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" focusable="false" ${a11y}>${LUCIDE[name]}</svg>`;
}

/**
 * Un aviso de acción terminada con la marca de terminal del sistema: `[x] texto` (UC-4903 AC-02).
 * La palabra la pone el propio texto («Conectado», «Clonado»…); la marca dice que está hecho.
 */
export function markDone(text: string): string {
	return `[x] ${text}`;
}

export function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) => ({
		'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
	}[c] as string));
}

/**
 * Estilos de la página: solo variables del sistema. Los tamaños y pesos los ponen las clases de
 * estilo de texto de foundation.css (display-lg, display-md, body-lg, label, caption, data-md…).
 */
const BASE_CSS = `
html { color-scheme: light; background: var(--paper-000); }
html[data-theme="dark"] { color-scheme: dark; }
body { margin: 0; font-family: var(--font-sans); font-size: var(--density-text); line-height: 1.5; color: var(--ink-900); background: var(--paper-000); -webkit-font-smoothing: antialiased; }
.lucide { flex: none; stroke-width: var(--icon-stroke); }
.lucide * { vector-effect: non-scaling-stroke; }
.brand { display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-8); color: var(--ink-900); }
h1, p { margin: 0; }
a { color: var(--link); text-decoration: underline; text-underline-offset: 2px; }
:where(a, button, [tabindex]):focus-visible { outline: var(--stroke-focus) solid var(--focus-ring); outline-offset: var(--focus-offset); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
`;

/** El símbolo y el nombre del producto en display-md, como en el resto del ecosistema. */
export function brandBlock(theme: PageTheme): string {
	return `<div class="brand">${brandMark(theme)}<span class="display-md">SpecBox</span></div>`;
}

/** Página completa con los tokens del sistema y el tema de VSCode. */
export function renderPage(opts: { lang?: string; title: string; theme?: PageTheme; css?: string; body: string; script?: string }): string {
	const theme = opts.theme ?? pageTheme();
	return `<!doctype html>
<html lang="${opts.lang ?? vscode.env?.language ?? 'en'}" data-theme="${theme}" data-density="comfortable">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="${theme}">
<title>${escapeHtml(opts.title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>${tokensCss()}
${BASE_CSS}
${opts.css ?? ''}</style>
</head>
<body>${opts.body}${opts.script ? `\n<script>${opts.script}</script>` : ''}</body>
</html>`;
}
