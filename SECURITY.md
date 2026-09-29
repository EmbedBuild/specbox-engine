# Security Policy

*Versión en español más abajo.*

## Reporting a vulnerability

Please report security issues privately. **Do not open a public issue, discussion or pull request.**

| Channel | When to use it |
|---------|----------------|
| **[Report a vulnerability](https://github.com/EmbedBuild/specbox-engine/security/advisories/new)** (GitHub private vulnerability reporting) | Preferred. Encrypted in transit, visible only to the maintainers, and it accepts attachments (logs, transcripts, proof-of-concept). |
| **security@specbox.build** | If you cannot use GitHub. Do not put secrets, tokens or personal data in the email: we will open a private advisory and invite you to it to exchange anything sensitive. |

Please include what you found, how to reproduce it, what it affects and, if you have one, a suggested fix.

## What to expect

| Step | Target |
|------|--------|
| Acknowledgement | within **48 hours** |
| Triage and severity assessment | within **5 business days** |
| Fix available — critical | **7 days** |
| Fix available — high | **30 days** |
| Fix available — medium | **90 days** |
| Fix available — low | next scheduled release |

Fixes ship in a versioned release. Each release notes what it now prevents in its **Security** section of the [CHANGELOG](CHANGELOG.md), without exploitable detail. We credit reporters who want to be credited.

## Scope

- SpecBox Engine: the MCP server, including the hosted instance at `mcp-specbox-engine.jpsdeveloper.com`
- The VS Code extension (`EmbedBuild.specbox-engine`) and the `specbox` CLI (npm)
- SpecBox Cloud (`cloud.specbox.build`, `api-cloud.specbox.build`) and the public site

Out of scope: denial of service or volumetric testing, social engineering, physical attacks, and vulnerabilities in third-party services we depend on (report those to their vendors).

## Safe harbour

We will not pursue legal action against good-faith research that follows this policy. Access only the minimum data needed to demonstrate an issue, never data from other users; do not degrade the service; and give us reasonable time to fix before any public disclosure.

## Supported versions

| Version | Supported |
|---------|-----------|
| 6.x (latest minor) | Yes |
| < 6.0 | No |

## Using SpecBox safely

- Connect with a **device token**: `npx specbox login` or *SpecBox: Sign in with GitHub* in VS Code. The token goes to your operating system's secure store and is never shown or pasted.
- Review and revoke your devices under **Connected devices** in the panel. Tokens expire and renew themselves.
- Never commit tokens or `.env` files; use `.env.example` as a template.
- Self-hosting the MCP server: keep `SPECBOX_NATIVE_DSN` only in the environment, require a token on every connection (`SPECBOX_TRANSPORT_AUTH=enforce`) and run the container as its non-root user.

---

# Política de seguridad

## Cómo reportar una vulnerabilidad

Repórtala en privado. **No abras un issue, una discusión ni una PR públicos.**

| Canal | Cuándo usarlo |
|-------|---------------|
| **[Reportar una vulnerabilidad](https://github.com/EmbedBuild/specbox-engine/security/advisories/new)** (reporte privado de GitHub) | Preferido. Cifrado en tránsito, solo lo ven los mantenedores y admite adjuntos (logs, transcripts, pruebas de concepto). |
| **security@specbox.build** | Si no puedes usar GitHub. No incluyas secretos, tokens ni datos personales en el correo: abriremos un aviso privado y te invitaremos a él para intercambiar lo sensible. |

Incluye qué encontraste, cómo reproducirlo, a qué afecta y, si la tienes, una propuesta de corrección.

## Qué esperar

| Paso | Plazo objetivo |
|------|----------------|
| Acuse de recibo | en **48 horas** |
| Análisis y severidad | en **5 días laborables** |
| Corrección disponible — crítica | **7 días** |
| Corrección disponible — alta | **30 días** |
| Corrección disponible — media | **90 días** |
| Corrección disponible — baja | siguiente versión planificada |

Las correcciones salen en una versión publicada. Cada versión cuenta en la sección **Security** del [CHANGELOG](CHANGELOG.md) qué evita a partir de ese momento, sin detalles explotables. Si quieres, te mencionamos.

## Alcance

- SpecBox Engine: el servidor MCP, incluida la instancia alojada en `mcp-specbox-engine.jpsdeveloper.com`
- La extensión de VS Code (`EmbedBuild.specbox-engine`) y la CLI `specbox` (npm)
- SpecBox Cloud (`cloud.specbox.build`, `api-cloud.specbox.build`) y el site público

Fuera de alcance: pruebas de denegación de servicio o de volumen, ingeniería social, ataques físicos y fallos de servicios de terceros de los que dependemos (repórtalos a su fabricante).

## Investigación de buena fe

No emprenderemos acciones legales contra investigación de buena fe que siga esta política. Accede solo a los datos mínimos para demostrar el problema y nunca a datos de otras personas; no degrades el servicio; y danos un plazo razonable para corregirlo antes de publicar nada.

## Usar SpecBox con seguridad

- Conéctate con un **token de dispositivo**: `npx specbox login` o *SpecBox: Iniciar sesión con GitHub* en VS Code. El token va al almacén seguro de tu sistema y nunca se muestra ni se pega.
- Revisa y revoca tus dispositivos en **Dispositivos conectados** del panel. Los tokens caducan y se renuevan solos.
- No subas tokens ni ficheros `.env` al repositorio; usa `.env.example` como plantilla.
- Si alojas tú el servidor MCP: `SPECBOX_NATIVE_DSN` solo en el entorno, token obligatorio en cada conexión (`SPECBOX_TRANSPORT_AUTH=enforce`) y el contenedor con su usuario sin privilegios.
