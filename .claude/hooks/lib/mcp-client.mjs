/**
 * lib/mcp-client.mjs — cliente MCP mínimo para los hooks (US-99 · UC-9901).
 *
 * Los hooks no tenían cómo hablar con el servidor MCP. Este cliente hace lo justo por HTTP
 * («Streamable HTTP»): `initialize`, `notifications/initialized` y un `tools/call`, con un tope de
 * tiempo para todo. Acepta respuestas JSON o en `text/event-stream`. Sin dependencias.
 */

const PROTOCOLO = '2025-06-18';

/** El mensaje JSON-RPC con ese `id` dentro de una respuesta JSON o SSE. */
export function mensajeDe(texto, tipo, id) {
  if ((tipo || '').includes('text/event-stream')) {
    for (const linea of String(texto).split('\n')) {
      if (!linea.startsWith('data:')) continue;
      try {
        const m = JSON.parse(linea.slice(5).trim());
        if (m && m.id === id) return m;
      } catch {
        // una línea que no es JSON: se ignora
      }
    }
    return null;
  }
  try {
    return JSON.parse(texto);
  } catch {
    return null;
  }
}

async function enviar(fetchImpl, url, cabeceras, cuerpo, sesion, signal) {
  const h = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', ...cabeceras };
  if (sesion) h['mcp-session-id'] = sesion;
  const res = await fetchImpl(url, { method: 'POST', headers: h, body: JSON.stringify(cuerpo), signal });
  const texto = res.status === 202 || res.status === 204 ? '' : await res.text();
  return {
    estado: res.status,
    sesion: res.headers.get('mcp-session-id') || sesion,
    mensaje: cuerpo.id === undefined ? null : mensajeDe(texto, res.headers.get('content-type'), cuerpo.id),
  };
}

/**
 * Llama a la tool `nombre` con `args` y devuelve su resultado (el JSON que devuelve la tool).
 * Lanza un Error corto (sin cabeceras ni token) si algo falla o pasa de `topeMs`.
 */
export async function llamarTool({ url, cabeceras = {}, nombre, args = {}, topeMs = 3000, fetchImpl = fetch }) {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), topeMs);
  try {
    const ini = await enviar(
      fetchImpl,
      url,
      cabeceras,
      {
        jsonrpc: '2.0',
        id: 1,
        method: 'initialize',
        params: { protocolVersion: PROTOCOLO, capabilities: {}, clientInfo: { name: 'specbox-heartbeat', version: '1' } },
      },
      null,
      control.signal,
    );
    if (ini.estado >= 400 || !ini.mensaje?.result) throw new Error(`initialize ${ini.estado}`);
    await enviar(fetchImpl, url, cabeceras, { jsonrpc: '2.0', method: 'notifications/initialized' }, ini.sesion, control.signal);
    const r = await enviar(
      fetchImpl,
      url,
      cabeceras,
      { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: nombre, arguments: args } },
      ini.sesion,
      control.signal,
    );
    if (r.estado >= 400 || !r.mensaje) throw new Error(`tools/call ${r.estado}`);
    if (r.mensaje.error) throw new Error(`tools/call ${r.mensaje.error.code ?? 'error'}`);
    const resultado = r.mensaje.result || {};
    if (resultado.structuredContent) return resultado.structuredContent;
    const texto = resultado.content?.find?.((c) => c.type === 'text')?.text;
    try {
      return texto ? JSON.parse(texto) : {};
    } catch {
      return { text: texto };
    }
  } catch (err) {
    if (err?.name === 'AbortError') throw new Error(`tope de ${topeMs} ms`);
    throw err instanceof Error ? new Error(err.message.slice(0, 120)) : new Error('fallo');
  } finally {
    clearTimeout(reloj);
  }
}
