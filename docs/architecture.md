# Architecture Guide

> JPS Dev Engine v3.5.0 — Guia de arquitectura multi-stack

## Stacks soportados

El engine soporta 4 stacks de aplicacion y 5 servicios de infraestructura. La deteccion del stack es automatica basada en archivos del proyecto.

| Stack | Version | Deteccion |
|-------|---------|-----------|
| Flutter | 3.38+ | `pubspec.yaml` |
| React | 19.x (Next.js 15.x) | `package.json` con react |
| Python | 3.12+ (FastAPI) | `requirements.txt` o `pyproject.toml` |
| Google Apps Script | V8 | `.clasp.json` |

## Flutter

Arquitectura Clean Architecture con 3 capas (Presentation, Domain, Data), BLoC como unico patron de estado y responsive obligatorio con 3 layouts por feature (mobile, tablet, desktop).

Documentacion disponible en `architecture/flutter/`:

| Documento | Contenido |
|-----------|-----------|
| `overview.md` | Principios, capas, patron SaaS-ready con multi-tenancy |
| `folder-structure.md` | Estructura feature-first del proyecto |
| `bloc-patterns.md` | Convenciones BLoC: eventos, estados, naming |
| `testing-strategy.md` | Estrategia de testing por capa |
| `responsive-system.md` | Breakpoints, AppLayoutBuilder, layouts obligatorios |

## React

Stack basado en Next.js 15 con App Router, Server Components por defecto, TypeScript, TanStack Query para server state, Zustand para client state y Tailwind CSS.

Documentacion disponible en `architecture/react/`:

| Documento | Contenido |
|-----------|-----------|
| `overview.md` | Stack, principios, Server Components, App Router, patrones |

## Python

Stack basado en FastAPI con async por defecto, Pydantic para validacion, SQLAlchemy 2.x async, Alembic para migraciones, Ruff para linting y mypy para type checking.

Documentacion disponible en `architecture/python/`:

| Documento | Contenido |
|-----------|-----------|
| `overview.md` | Stack, principios, async-first, dependency injection |

## Google Apps Script

Desarrollo con V8 runtime obligatorio, clasp CLI para desarrollo local con TypeScript, batch operations first y separacion de concerns por archivo con prefijos de modulo.

Documentacion disponible en `architecture/google-apps-script/`:

| Documento | Contenido |
|-----------|-----------|
| `overview.md` | Principios V8, clasp + TypeScript, tipos de proyectos |
| `folder-structure.md` | Organizacion por convencion de archivos |
| `patterns.md` | Patrones: batch operations, cache, error handling |
| `testing-strategy.md` | Testing en GAS con clasp y mocks |

## Patrones comunes

Todos los stacks comparten principios fundamentales:

- **Feature-first**: organizacion por feature, no por tipo de archivo
- **Clean Architecture por capas**: separacion data / domain / presentation
- **Separacion de concerns**: cada capa tiene responsabilidades claras
- **Testing por capa**: unit tests en domain, integration en data, widget/component en presentation

## Infraestructura

Los patrones de integracion con servicios externos se documentan en `infra/{servicio}/patterns.md`:

| Servicio | Documento | Uso principal |
|----------|-----------|---------------|
| Supabase | `infra/supabase/patterns.md` | Auth, Postgres, Edge Functions, Storage |
| Neon | `infra/neon/patterns.md` | Postgres serverless, branching |
| Stripe | `infra/stripe/patterns.md` | Pagos, suscripciones, webhooks |
| Firebase | `infra/firebase/patterns.md` | Auth, Firestore, Cloud Functions |
| n8n | `infra/n8n/patterns.md` | Automatizaciones, workflows, webhooks |

## Diseyo UI

La integracion con Google Stitch MCP permite generar diseños UI como HTML desde prompts de texto. Los diseños se guardan en `doc/design/{feature}/` y se convierten a codigo durante `/implement`.

Documentacion en `design/stitch/`:

- `README.md` — configuracion y flujo de uso
- `prompt-template.md` — template para prompts de generacion

## Como usa el engine la arquitectura

Los Skills leen automaticamente `architecture/{stack}/` al detectar el stack del proyecto:

- `/plan` consulta el overview y folder-structure para generar planes alineados con la arquitectura
- `/implement` usa los patrones (BLoC, Server Components, async-first) para generar codigo idiomatico
- `/quality-gate` valida contra las convenciones definidas en cada stack
- `/adapt-ui` detecta el inventario de componentes segun la estructura del stack

No es necesario indicar el stack manualmente: el engine lo detecta por los archivos del proyecto y carga los documentos relevantes.

## Referencia completa

- Patrones de aplicacion: [architecture/](../architecture/)
- Patrones de infraestructura: [infra/](../infra/)
- Diseyo UI: [design/stitch/](../design/stitch/)
