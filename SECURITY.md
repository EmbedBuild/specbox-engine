# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in SDD-JPS Engine, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **security@jpsdeveloper.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and provide a timeline for resolution.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 4.x     | Yes       |
| < 4.0   | No        |

## Security Best Practices for Users

- **Always set `DASHBOARD_TOKEN`** in production deployments
- **Never commit `.env` files** — use `.env.example` as a template
- Trello credentials are per-session and not persisted to disk
- Remote MCP telemetry (`DEV_ENGINE_MCP_URL`) is opt-in and fire-and-forget
