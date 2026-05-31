---
id: UC-663
ordinal: UC-103
title: Porting de los 8 SQuaRE analyzers a .quality/scripts/audit/ (Node local)
parent_us: US-CONN-AUDIT
status: draft
actor: Client
hours: 12
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-663 — Porting de los 8 SQuaRE analyzers a .quality/scripts/audit/ (Node local)

> **US padre:** [US-CONN-AUDIT](../us/US-19-audit-operativo-en-remoto-via-analyzers-locales.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Los 8 analyzers SQuaRE (functional, performance, compatibility, usability, reliability, security, maintainability, portability) se ejecutan client-side desde .quality/scripts/audit/ (Node) escaneando el codigo local, sin que el server toque el filesystem del cliente. Test: corre cada analyzer sobre un fixture y asserta que produce su bloque del QualityReport (score 0-100, traffic_light, findings, recommendations).

- **Estado:** ⬜ pendiente

### AC-02

submit_quality_audit(report) acepta el QualityReport construido client-side por content-passing, lo persiste bajo evidence/audits/ y autogenera audit_id si no se pasa. Test: envia un report serializado y asserta persistencia (JSON + PDF) + audit_id formato audit_YYYYMMDDTHHMMSSZ.

- **Estado:** ⬜ pendiente

### AC-03

La skill /audit orquesta el flujo nuevo (lazy-check de tools externas -> ejecutar analyzers locales -> submit_quality_audit) y funciona end-to-end con SPECBOX_ENGINE_MCP_URL set. Smoke test que ejecuta /audit en remoto sobre el propio repo y produce evidencia valida.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
