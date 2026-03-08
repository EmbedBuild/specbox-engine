# Google Apps Script - Estrategia de Testing

## Limitaciones de Testing en Apps Script

Google Apps Script NO tiene un framework de testing nativo. La estrategia se divide en dos niveles:

| Nivel | Que testear | Herramienta | Donde |
|-------|-------------|-------------|-------|
| **Local** | Logica pura (sin servicios Google) | Jest + TypeScript | Maquina local |
| **Remoto** | Funciones que usan servicios Google | Tests manuales estructurados | Entorno Apps Script |

**Regla critica**: Solo puedes testear localmente funciones que NO llamen a `SpreadsheetApp`, `GmailApp`, `DriveApp`, etc. Las funciones con servicios Google deben testearse en el entorno de Apps Script.

---

## 1. Testing Local con Jest (logica pura)

### Setup

```bash
npm install -D jest @types/jest ts-jest
```

**jest.config.js:**
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: ['**/*.test.ts'],
};
```

### Ejemplo

```typescript
// src/utils/Helpers.ts
export function formatCurrency(amount: number, currency = 'EUR'): string {
  return `${amount.toFixed(2)} ${currency}`;
}

export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function parseSheetRow(
  headers: string[],
  row: any[]
): Record<string, any> {
  const obj: Record<string, any> = {};
  headers.forEach((h, i) => { obj[h] = row[i]; });
  return obj;
}
```

```typescript
// tests/utils/Helpers.test.ts
import { formatCurrency, validateEmail, parseSheetRow } from '../../src/utils/Helpers';

describe('formatCurrency', () => {
  it('formatea con moneda por defecto', () => {
    expect(formatCurrency(1500)).toBe('1500.00 EUR');
  });

  it('formatea con moneda custom', () => {
    expect(formatCurrency(99.9, 'USD')).toBe('99.90 USD');
  });

  it('maneja decimales', () => {
    expect(formatCurrency(0.1 + 0.2)).toBe('0.30 EUR');
  });
});

describe('validateEmail', () => {
  it('acepta email valido', () => {
    expect(validateEmail('user@example.com')).toBe(true);
  });

  it('rechaza email invalido', () => {
    expect(validateEmail('invalid-email')).toBe(false);
    expect(validateEmail('')).toBe(false);
    expect(validateEmail('user@')).toBe(false);
  });
});

describe('parseSheetRow', () => {
  it('mapea headers a valores', () => {
    const headers = ['id', 'name', 'email'];
    const row = ['1', 'Jesus', 'jesus@example.com'];
    expect(parseSheetRow(headers, row)).toEqual({
      id: '1',
      name: 'Jesus',
      email: 'jesus@example.com'
    });
  });
});
```

---

## 2. Testing Remoto en Apps Script

Para funciones que usan servicios Google, crear un archivo de tests manuales estructurados:

```javascript
// Tests.gs (o src/tests/RunTests.ts)

function runAllTests() {
  const results = [];

  results.push(testGetAllRecords());
  results.push(testCreateRecord());
  results.push(testUpdateRecord());
  results.push(testDeleteRecord());
  results.push(testCacheService());
  results.push(testUrlFetch());

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;

  console.log(`\n========== TEST RESULTS ==========`);
  console.log(`Passed: ${passed} | Failed: ${failed} | Total: ${results.length}`);
  results.filter(r => !r.passed).forEach(r => {
    console.error(`FAIL: ${r.name} — ${r.error}`);
  });
  console.log(`==================================\n`);

  return { passed, failed, total: results.length, details: results };
}

// Helper de assertion
function assert_(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

function assertEqual_(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(
      `${message || 'assertEqual'}: expected "${expected}" but got "${actual}"`
    );
  }
}

// Test individual
function testGetAllRecords() {
  try {
    const records = getAllRecords_();
    assert_(Array.isArray(records), 'Debe devolver un array');
    assert_(records.length >= 0, 'Debe tener 0+ registros');
    if (records.length > 0) {
      assert_(records[0].id !== undefined, 'Cada registro debe tener id');
    }
    return { name: 'testGetAllRecords', passed: true };
  } catch (e) {
    return { name: 'testGetAllRecords', passed: false, error: e.message };
  }
}

function testCreateRecord() {
  try {
    const record = createRecord_({ name: 'Test', email: 'test@test.com' });
    assert_(record.id, 'Debe generar un UUID');
    assert_(record.createdAt, 'Debe tener timestamp');

    // Cleanup
    deleteRecord_(record.id);
    return { name: 'testCreateRecord', passed: true };
  } catch (e) {
    return { name: 'testCreateRecord', passed: false, error: e.message };
  }
}
```

---

## 3. Estrategia por Tipo de Proyecto

### Bound Script (Sheet/Doc/Form)

| Que testear | Como |
|-------------|------|
| Logica de procesamiento de datos | Jest local |
| CRUD contra Sheet | Tests remotos + Sheet de prueba |
| Triggers (onEdit, onOpen) | Manual + logging |
| Menus/Sidebars | Manual |

### Standalone / Web App

| Que testear | Como |
|-------------|------|
| Logica de negocio | Jest local |
| doGet/doPost handlers | Tests remotos con parametros mock |
| HTML rendering | Manual en navegador |
| APIs externas | Jest local con mocks de UrlFetchApp |

### Add-on

| Que testear | Como |
|-------------|------|
| CardService builders | Tests remotos |
| Action handlers | Tests remotos |
| OAuth flow | Manual |
| Scopes | Revision manual de appsscript.json |

---

## 4. Hooks de Testing

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:remote": "clasp run runAllTests"
  }
}
```

### Pre-push

```bash
npm run test && npm run lint && npm run push
```

---

## 5. Cobertura

- **Logica pura (local)**: Apuntar a 85%+ con Jest
- **Funciones con servicios Google (remoto)**: Testear todos los happy paths + errores principales
- **Custom functions**: Testear con datos variados en un Sheet de prueba
- **Triggers**: Verificar manualmente que se ejecutan correctamente
- **Web Apps**: Testear con curl/Postman los endpoints doGet/doPost

---

## 6. Acceptance Testing (BDD)

> Tests de aceptación basados en Gherkin que validan AC-XX directamente desde archivos `.feature`.
> Cada UC genera un `.feature`, cada AC genera un Escenario.
> Solo aplica a la lógica pura testeable localmente (no a servicios Google).

### Setup

```bash
npm install -D jest-cucumber
```

### Ejemplo .feature

```gherkin
# language: es
# tests/acceptance/features/UC-001_procesar_factura.feature

@US-01 @UC-001
Característica: Procesar factura
  Como administrador
  Quiero procesar facturas desde un Google Sheet
  Para automatizar la contabilidad

  Antecedentes:
    Dado que tengo un array de headers ["id", "cliente", "monto", "estado"]
    Y tengo datos de factura válidos

  @AC-01
  Escenario: Procesar factura con datos válidos
    Cuando proceso la factura con cliente "Empresa ABC" y monto 1500.00
    Entonces el resultado tiene estado "procesada"
    Y el monto formateado es "1500.00 EUR"
    Y capturo evidencia del resultado

  @AC-02
  Escenario: Rechazar factura con monto negativo
    Cuando proceso la factura con cliente "Empresa ABC" y monto -100
    Entonces el resultado tiene estado "rechazada"
    Y el error contiene "monto inválido"
    Y capturo evidencia del resultado
```

### Step Definition (TypeScript)

```typescript
// tests/acceptance/steps/UC-001_steps.ts
import { defineFeature, loadFeature } from 'jest-cucumber';
import { formatCurrency } from '../../src/utils/Helpers';
import { processInvoice } from '../../src/services/InvoiceProcessor';
import * as fs from 'fs';

const feature = loadFeature(
  'tests/acceptance/features/UC-001_procesar_factura.feature',
);

defineFeature(feature, (test) => {
  let headers: string[];
  let result: any;

  test('Procesar factura con datos válidos', ({ given, when, then, and }) => {
    given(/^que tengo un array de headers (.*)$/, (h: string) => {
      headers = JSON.parse(h);
    });

    given('tengo datos de factura válidos', () => {
      // Setup preconditions
    });

    when(
      /^proceso la factura con cliente "(.*)" y monto (.*)$/,
      (cliente: string, monto: string) => {
        result = processInvoice({
          cliente,
          monto: parseFloat(monto),
        });
      },
    );

    then(/^el resultado tiene estado "(.*)"$/, (estado: string) => {
      expect(result.estado).toBe(estado);
    });

    and(/^el monto formateado es "(.*)"$/, (expected: string) => {
      expect(formatCurrency(result.monto)).toBe(expected);
    });

    and('capturo evidencia del resultado', () => {
      const evidence = JSON.stringify(result, null, 2);
      fs.mkdirSync('tests/acceptance/reports', { recursive: true });
      fs.appendFileSync(
        'tests/acceptance/reports/evidence.json',
        evidence + '\n',
      );
    });
  });
});
```

### Ejecución

```bash
# Ejecutar acceptance tests BDD
npx jest tests/acceptance/

# Con verbose
npx jest tests/acceptance/ --verbose

# Con coverage
npx jest tests/acceptance/ --coverage
```

### Report

- Formato: JSON Cucumber estándar
- Ubicación: `tests/acceptance/reports/cucumber-report.json`
- PDF de evidencia generado y adjuntado a card UC en Trello (si spec-driven)

### Estructura

```
tests/acceptance/
├── features/
│   ├── UC-001_procesar_factura.feature
│   └── UC-002_generar_reporte.feature
├── steps/
│   ├── common_steps.ts         # Helpers comunes de assertion
│   └── UC-001_steps.ts         # Steps específicos del UC
└── reports/
    ├── cucumber-report.json
    └── acceptance-report.pdf
```

---

## Anti-patrones de Testing

| No hacer | Si hacer |
|----------|----------|
| Testear servicios Google con Jest | Separar logica pura de servicios Google |
| Ignorar tests porque "es solo Apps Script" | Tests locales para logica, remotos para servicios |
| Hardcodear IDs de Sheets en tests | Usar PropertiesService o Sheet de test dedicada |
| Testear en el Sheet de produccion | Crear copia de test o Sheet dedicada |
| Depender solo de console.log | Estructurar tests con assert y resultados |
