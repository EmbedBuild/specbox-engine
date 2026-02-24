# Arquitectura Google Apps Script - Overview

## Principios Fundamentales

### 1. V8 Runtime Obligatorio
- **SIEMPRE** usar V8 runtime (Rhino deprecado, muere Enero 2026)
- Configurar `"runtimeVersion": "V8"` en `appsscript.json`
- ES2022+: let/const, arrow functions, destructuring, template literals, clases
- **Limitaciones V8 en GAS**: No ES6 modules, no private class fields (`#field`), no static fields, scope global unico

### 2. Desarrollo Local con clasp + TypeScript
- **SIEMPRE** usar clasp CLI para desarrollo local en VSCode
- TypeScript con esbuild como bundler (clasp ya no transpila TS)
- Git para versionado, `.clasprc.json` en `.gitignore`
- `appsscript.json` y `.clasp.json` SI se versionan

### 3. Batch Operations First
- **NUNCA** leer/escribir celda por celda — usar `getValues()`/`setValues()` en batch
- Agrupar reads primero, luego writes — evitar interleaving
- `UrlFetchApp.fetchAll()` para multiples llamadas HTTP en paralelo
- `CacheService` para datos que se leen frecuentemente

### 4. Separacion de Concerns por Archivo
- Apps Script compila todo en un scope global unico (no hay modulos)
- La organizacion se logra por convencion de archivos
- Prefijos de modulo para evitar colisiones: `DATA_`, `UI_`, `API_`, `UTIL_`
- Funciones privadas terminan en `_` (no visibles como library)

## Tipos de Proyectos

| Tipo | Descripcion | Cuando usar |
|------|-------------|-------------|
| **Bound** | Vinculado a un documento (Sheet, Doc, Form) | Automatizaciones de un documento especifico |
| **Standalone** | Proyecto independiente | Web Apps, APIs, bibliotecas |
| **Library** | Standalone compartido entre proyectos | Codigo reutilizable entre equipo |
| **Add-on** | Publicado en Marketplace | Productos para terceros |

## Servicios Principales

### Built-in (no requieren activacion)

| Servicio | Objeto Global | Uso |
|----------|---------------|-----|
| Spreadsheet | `SpreadsheetApp` | CRUD en Sheets |
| Document | `DocumentApp` | Manipulacion de Docs |
| Slides | `SlidesApp` | Manipulacion de Slides |
| Forms | `FormApp` | Crear/editar Forms |
| Gmail | `GmailApp` / `MailApp` | Enviar/leer emails |
| Drive | `DriveApp` | Gestion de archivos |
| Calendar | `CalendarApp` | Calendarios/eventos |
| URL Fetch | `UrlFetchApp` | Llamadas HTTP externas |
| HTML Service | `HtmlService` | Interfaces web (sidebars, dialogs, Web Apps) |
| Content Service | `ContentService` | Servir JSON/XML (APIs REST) |
| Properties | `PropertiesService` | Almacenamiento key-value persistente |
| Cache | `CacheService` | Cache temporal (max 6 hrs) |
| Lock | `LockService` | Control de concurrencia |
| Card | `CardService` | UI para Workspace Add-ons |
| Utilities | `Utilities` | Encode/decode, formatDate, sleep, UUID |

### Advanced Services (requieren activacion)

| Servicio | API | Cuando usar |
|----------|-----|-------------|
| Sheets API v4 | Batch updates, charts avanzados | Cuando SpreadsheetApp no es suficiente |
| Drive API v3 | Propiedades custom, revisiones | Operaciones avanzadas de Drive |
| Admin SDK | Usuarios, grupos, OUs | Administracion de Workspace |
| BigQuery | BigQuery API | Analisis de datos masivos |
| People API | Contactos avanzados | Reemplazo de ContactsApp |

## Quotas Criticas

| Recurso | Gratuita | Workspace |
|---------|----------|-----------|
| Ejecucion por invocacion | 6 min | 6 min |
| Trigger total/dia | 90 min | 6 hrs |
| Custom function | 30 seg | 30 seg |
| Emails/dia (MailApp) | 100 | 1,500 |
| URL Fetch calls/dia | 20,000 | 100,000 |
| PropertiesService/valor | 9 KB | 9 KB |
| PropertiesService total | 500 KB | 500 KB |
| CacheService/valor | 100 KB | 100 KB |
| Workspace Add-on ejecucion | 30 seg | 30 seg |

## Documentos Relacionados

- [Estructura de Carpetas](folder-structure.md)
- [Patrones](patterns.md)
- [Estrategia de Testing](testing-strategy.md)
