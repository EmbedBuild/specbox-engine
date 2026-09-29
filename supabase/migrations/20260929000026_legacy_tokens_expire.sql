-- 0026_legacy_tokens_expire.sql
-- UC-3902 AC-01 (US-39) — los tokens anteriores a la caducidad también caducan.
--
-- Desde la migración 0025 todo token nuevo nace con fecha de caducidad (90 días),
-- pero los emitidos antes no tienen ninguna y valen para siempre. Decisión del
-- operador (2026-09-29): caducan a los 90 días del despliegue de esta regla, el
-- 2026-12-28. Quien use la extensión 6.14.0 o `specbox login` ya tiene un token
-- de dispositivo que se renueva solo, así que no lo nota; quien siga con un token
-- antiguo recibirá, al caducar, el mensaje de cómo reconectar.
--
-- Solo toca tokens activos sin fecha: los revocados y los que ya caducan quedan
-- igual. Fecha fija (no now()) para que reaplicar la migración dé siempre el mismo
-- resultado. Reversible: UPDATE ... SET expires_at = NULL WHERE expires_at =
-- '2026-12-28 00:00:00+00' AND device_id IS NULL.

UPDATE public.mcp_tokens
   SET expires_at = timestamptz '2026-12-28 00:00:00+00'
 WHERE revoked_at IS NULL
   AND expires_at IS NULL;
