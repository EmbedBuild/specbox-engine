// UC-650 — mock cloud server.
//
// Simulates the cloud's /vscode/issue-token endpoint defined in UC-645 AC-02.
// On a GET to /vscode/issue-token?return_to=<loopback>&state=<csrf>, it
// redirects (302) to <return_to>?mcp_token=<fake>&state=<csrf>. Optional
// modes via query params:
//   ?mode=error        → redirect with ?error=access_denied&error_description=...
//   ?mode=bad_state    → redirect with a different state
//   ?mode=never        → never redirect (used to verify the 5min timeout)
//
// Used by tests/oauth-integration.test.mjs.

import http from 'node:http';
import crypto from 'node:crypto';

export async function startMockCloudServer({ port = 0 } = {}) {
	const server = http.createServer((req, res) => {
		const url = new URL(req.url ?? '/', 'http://127.0.0.1');
		if (url.pathname !== '/vscode/issue-token') {
			res.statusCode = 404;
			res.end('not found');
			return;
		}
		const returnTo = url.searchParams.get('return_to');
		const state = url.searchParams.get('state');
		const mode = url.searchParams.get('mode') ?? 'success';
		if (!returnTo || !state) {
			res.statusCode = 400;
			res.end('missing return_to or state');
			return;
		}
		if (mode === 'never') {
			// hold the connection open
			return;
		}
		const target = new URL(returnTo);
		if (mode === 'error') {
			target.searchParams.set('error', 'access_denied');
			target.searchParams.set('error_description', 'user_rejected');
			target.searchParams.set('state', state);
		} else if (mode === 'bad_state') {
			target.searchParams.set('mcp_token', crypto.randomBytes(32).toString('hex'));
			target.searchParams.set('state', 'wrong-state');
		} else {
			target.searchParams.set('mcp_token', crypto.randomBytes(32).toString('hex'));
			target.searchParams.set('state', state);
		}
		res.statusCode = 302;
		res.setHeader('Location', target.toString());
		res.end();
	});
	await new Promise((res, rej) => {
		server.once('error', rej);
		server.listen(port, '127.0.0.1', () => res());
	});
	const addr = server.address();
	return {
		port: addr.port,
		url: `http://127.0.0.1:${addr.port}/vscode/issue-token`,
		close: () => new Promise((res) => server.close(() => res())),
	};
}
