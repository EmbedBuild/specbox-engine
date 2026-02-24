# Google Apps Script - Estructura de Carpetas

## Proyecto con clasp + TypeScript (Recomendado)

```
mi-proyecto-gas/
├── .git/
├── .gitignore
├── .clasp.json                    # Config clasp (scriptId, rootDir) — SI versionar
├── appsscript.json                # Manifiesto GAS (scopes, runtime) — SI versionar
├── package.json                   # Dependencies (clasp, typescript, esbuild)
├── tsconfig.json                  # Config TypeScript
├── build.mjs                      # Script de build con esbuild
├── src/                           # Codigo fuente TypeScript
│   ├── index.ts                   # Entry point — exporta funciones globales
│   ├── Config.ts                  # Constantes, configuracion
│   ├── services/                  # Logica de negocio por servicio
│   │   ├── SheetsService.ts       # CRUD con Sheets
│   │   ├── GmailService.ts        # Operaciones de email
│   │   ├── DriveService.ts        # Operaciones de Drive
│   │   ├── CalendarService.ts     # Operaciones de Calendar
│   │   └── ApiService.ts          # Llamadas a APIs externas (UrlFetchApp)
│   ├── data/                      # Acceso a datos
│   │   ├── SheetDataAccess.ts     # CRUD generico contra Sheets
│   │   └── PropertiesManager.ts   # Wrapper de PropertiesService
│   ├── ui/                        # Interfaz de usuario
│   │   ├── Menu.ts                # Menus custom (onOpen)
│   │   ├── Sidebar.ts             # Logica de sidebars
│   │   └── Dialog.ts              # Logica de dialogs
│   ├── triggers/                  # Funciones de triggers
│   │   ├── OnOpen.ts              # Simple trigger onOpen
│   │   ├── OnEdit.ts              # Simple trigger onEdit
│   │   └── TimeBased.ts           # Installable triggers de tiempo
│   ├── webapp/                    # Web App (doGet/doPost)
│   │   ├── Router.ts              # Enrutador para doGet/doPost
│   │   └── Handlers.ts            # Handlers por action
│   ├── addons/                    # Add-ons (si aplica)
│   │   ├── Cards.ts               # CardService builders
│   │   └── Handlers.ts            # Action handlers
│   ├── utils/                     # Utilidades
│   │   ├── ErrorHandler.ts        # Manejo centralizado de errores
│   │   ├── Logger.ts              # Logging helpers
│   │   └── Helpers.ts             # Funciones de utilidad
│   └── html/                      # Templates HTML (HtmlService)
│       ├── Sidebar.html
│       ├── Dialog.html
│       ├── Styles.html            # CSS compartido
│       └── JavaScript.html        # JS compartido del cliente
├── tests/                         # Tests locales (Jest)
│   ├── services/
│   │   └── SheetsService.test.ts
│   └── utils/
│       └── Helpers.test.ts
├── dist/                          # Output de build — en .gitignore
│   ├── Code.js                    # Bundle generado por esbuild
│   └── appsscript.json            # Copiado automaticamente
└── node_modules/                  # — en .gitignore
```

## Proyecto Simple (.gs sin TypeScript)

Para proyectos pequenos o scripts rapidos:

```
mi-script/
├── .clasp.json
├── appsscript.json
├── Code.gs                        # Entry point / funciones principales
├── Config.gs                      # Constantes, configuracion
├── DataAccess.gs                  # CRUD contra Sheets/DB
├── ApiService.gs                  # Llamadas HTTP externas
├── EmailService.gs                # Gmail/MailApp
├── UI.gs                          # Menus, dialogos, sidebars
├── Triggers.gs                    # onOpen, onEdit, triggers programaticos
├── Utils.gs                       # Utilidades genericas
├── ErrorHandler.gs                # Manejo de errores
├── Templates/                     # HTML para HtmlService
│   ├── Sidebar.html
│   ├── Dialog.html
│   └── Styles.html
└── Tests.gs                       # Tests manuales
```

## Archivos de Configuracion

### .clasp.json

```json
{
  "scriptId": "1234567890abcdef",
  "rootDir": "./dist",
  "projectId": "mi-gcp-project",
  "fileExtension": "ts"
}
```

### appsscript.json

```json
{
  "timeZone": "Europe/Madrid",
  "runtimeVersion": "V8",
  "exceptionLogging": "STACKDRIVER",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/script.external_request"
  ],
  "dependencies": {
    "enabledAdvancedServices": []
  }
}
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "lib": ["ESNext"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": false,
    "noEmit": false
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

### build.mjs

```javascript
import { build } from 'esbuild';
import { copyFileSync } from 'fs';

await build({
  entryPoints: ['src/index.ts'],
  bundle: true,
  outfile: 'dist/Code.js',
  format: 'esm',
  target: 'es2020',
  banner: {
    js: '// Bundled with esbuild for Google Apps Script'
  },
  globalName: 'exports',
  footer: {
    js: `
      // Expose functions globally for Apps Script
      function doGet(e) { return exports.doGet(e); }
      function doPost(e) { return exports.doPost(e); }
      function onOpen(e) { return exports.onOpen(e); }
      function onEdit(e) { return exports.onEdit(e); }
    `
  }
});

// Copy manifest to dist
copyFileSync('appsscript.json', 'dist/appsscript.json');
```

### package.json scripts

```json
{
  "scripts": {
    "build": "node build.mjs",
    "push": "npm run build && clasp push",
    "watch": "nodemon --watch src -e ts,html --exec 'npm run push'",
    "pull": "clasp pull",
    "deploy": "npm run push && clasp deploy",
    "open": "clasp open",
    "logs": "clasp logs --watch",
    "test": "jest",
    "lint": "tsc --noEmit"
  }
}
```

### .gitignore

```
node_modules/
dist/
.clasprc.json
*.log
.DS_Store
```

## Naming Conventions

```javascript
// Funciones publicas: camelCase
function processInvoices() { }

// Funciones privadas (no visibles en library): terminan en _
function helperFunction_() { }

// Constantes: UPPER_SNAKE_CASE
const MAX_ROWS = 1000;
const SHEET_NAME = 'Data';

// Prefijos por modulo (evita colisiones en scope global)
function DATA_getRecords() { }
function UI_showSidebar() { }
function API_fetchCustomers() { }
function UTIL_formatDate() { }

// Custom functions para Sheets: UPPER_CASE con @customfunction JSDoc
/**
 * @customfunction
 */
function CELSIUS_TO_FAHRENHEIT(celsius) {
  return celsius * 9 / 5 + 32;
}

// Archivos: PascalCase.ts o PascalCase.gs
// Clases: PascalCase
// Variables: camelCase
// Interfaces (TS): PascalCase con prefijo I opcional
```

## Scopes (Principio de Minimo Privilegio)

Declarar explicitamente en `appsscript.json`. Usar el scope mas restrictivo posible:

| Necesidad | Scope restrictivo | NO usar |
|-----------|-------------------|---------|
| Leer Sheets | `spreadsheets.readonly` | `spreadsheets` |
| Leer Drive | `drive.readonly` | `drive` |
| Solo archivos del script | `drive.file` | `drive` |
| Enviar email | `gmail.send` | `gmail.modify` |
| Leer calendario | `calendar.readonly` | `calendar` |
