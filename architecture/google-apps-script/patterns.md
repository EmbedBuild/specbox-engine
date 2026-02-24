# Google Apps Script - Patrones

## 1. CRUD con Sheets como Backend

```javascript
const SHEET_ID = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
const SHEET_NAME = 'Data';

// READ: Obtener todos los registros como array de objetos
function getAllRecords_() {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  const headers = data.shift();

  return data.map((row, index) => {
    const obj = { _row: index + 2 };
    headers.forEach((header, i) => {
      obj[header] = row[i];
    });
    return obj;
  });
}

// CREATE: Agregar registro
function createRecord_(record) {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];

  record.id = Utilities.getUuid();
  record.createdAt = new Date();
  record.updatedAt = new Date();

  const row = headers.map(header => record[header] || '');
  sheet.appendRow(row);
  return record;
}

// UPDATE: Actualizar registro por ID (batch)
function updateRecord_(id, updates) {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const idCol = headers.indexOf('id');

  for (let i = 1; i < data.length; i++) {
    if (data[i][idCol] === id) {
      updates.updatedAt = new Date();
      const rowData = [...data[i]];
      Object.keys(updates).forEach(key => {
        const colIndex = headers.indexOf(key);
        if (colIndex !== -1) rowData[colIndex] = updates[key];
      });
      sheet.getRange(i + 1, 1, 1, rowData.length).setValues([rowData]);
      return rowData;
    }
  }
  throw new Error(`Registro con id ${id} no encontrado`);
}

// DELETE: Eliminar registro
function deleteRecord_(id) {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  const idCol = data[0].indexOf('id');

  for (let i = 1; i < data.length; i++) {
    if (data[i][idCol] === id) {
      sheet.deleteRow(i + 1);
      return true;
    }
  }
  return false;
}
```

## 2. Web App (doGet / doPost)

### Servir HTML

```javascript
function doGet(e) {
  const page = e.parameter.page || 'Index';
  return HtmlService.createTemplateFromFile(page)
    .evaluate()
    .setTitle('Mi Aplicacion')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

// Incluir parciales CSS/JS
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
```

### API REST con ContentService

```javascript
function doGet(e) {
  try {
    const action = e.parameter.action;
    let result;

    switch (action) {
      case 'list': result = getAllRecords_(); break;
      case 'get': result = getRecordById_(e.parameter.id); break;
      default: result = { error: 'Accion no reconocida' };
    }

    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const action = e.parameter.action;
    let result;

    switch (action) {
      case 'create': result = createRecord_(data); break;
      case 'update': result = updateRecord_(data.id, data); break;
      case 'delete': result = deleteRecord_(data.id); break;
      default: result = { error: 'Accion no reconocida' };
    }

    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

## 3. Triggers

### Simple Triggers (sin autorizacion)

```javascript
function onOpen(e) {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('Mi Menu')
    .addItem('Ejecutar proceso', 'runProcess')
    .addSeparator()
    .addSubMenu(ui.createMenu('Sub-menu')
      .addItem('Opcion A', 'optionA'))
    .addToUi();
}

function onEdit(e) {
  const range = e.range;
  const sheet = range.getSheet();
  // Ejemplo: timestamp automatico al editar columna B
  if (sheet.getName() === 'Data' && range.getColumn() === 2) {
    range.offset(0, 5).setValue(new Date());
  }
}
```

### Installable Triggers (con autorizacion)

```javascript
function createTimeTrigger() {
  ScriptApp.newTrigger('processData')
    .timeBased()
    .everyHours(1)
    .create();
}

function createDailyTrigger() {
  ScriptApp.newTrigger('dailyReport')
    .timeBased()
    .atHour(9)
    .everyDays(1)
    .create();
}

function createSpreadsheetTrigger() {
  const ss = SpreadsheetApp.getActive();
  ScriptApp.newTrigger('onEditInstallable')
    .forSpreadsheet(ss)
    .onEdit()
    .create();
}

function createFormSubmitTrigger() {
  const form = FormApp.getActiveForm();
  ScriptApp.newTrigger('onFormSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();
}

// Listar/eliminar triggers
function deleteAllTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
}
```

## 4. Sidebars y Dialogs

```javascript
function showSidebar() {
  const html = HtmlService.createTemplateFromFile('Sidebar')
    .evaluate()
    .setTitle('Panel de Control');
  SpreadsheetApp.getUi().showSidebar(html);
}

function showDialog() {
  const html = HtmlService.createTemplateFromFile('Dialog')
    .evaluate()
    .setWidth(400)
    .setHeight(300);
  SpreadsheetApp.getUi().showModalDialog(html, 'Titulo');
}
```

**Comunicacion bidireccional (HTML lado cliente):**
```html
<script>
  google.script.run
    .withSuccessHandler(onSuccess)
    .withFailureHandler(onError)
    .myServerFunction(param1, param2);

  function onSuccess(data) { /* ... */ }
  function onError(error) { alert(error.message); }

  // Cerrar sidebar/dialog
  google.script.host.close();
</script>
```

## 5. Almacenamiento

### PropertiesService (persistente)

```javascript
// Script Properties: compartidas entre usuarios
const props = PropertiesService.getScriptProperties();
props.setProperty('API_KEY', 'abc123');
const apiKey = props.getProperty('API_KEY');

// User Properties: privadas por usuario
const userProps = PropertiesService.getUserProperties();
userProps.setProperty('theme', 'light');

// Document Properties: vinculadas al documento (solo bound scripts)
const docProps = PropertiesService.getDocumentProperties();
```

**Limites:** 9 KB por valor, 500 KB total por store.

### CacheService (temporal)

```javascript
function getCachedData_(key) {
  const cache = CacheService.getScriptCache();
  let data = cache.get(key);

  if (data) return JSON.parse(data);

  // Cache miss
  data = fetchExpensiveData_();
  cache.put(key, JSON.stringify(data), 600); // 10 min
  return data;
}
```

**Limites:** 100 KB por valor, max 6 hrs de vida. No garantiza integridad.

### LockService (concurrencia)

```javascript
function updateSharedCounter() {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000); // Espera max 10 seg

    const props = PropertiesService.getScriptProperties();
    let counter = parseInt(props.getProperty('counter') || '0');
    counter++;
    props.setProperty('counter', counter.toString());

    lock.releaseLock();
    return counter;
  } catch (e) {
    console.error('No se pudo obtener el lock:', e.message);
    throw e;
  }
}
```

## 6. APIs Externas (UrlFetchApp)

```javascript
// GET simple
function fetchData_(url) {
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (response.getResponseCode() !== 200) {
    throw new Error(`HTTP ${response.getResponseCode()}`);
  }
  return JSON.parse(response.getContentText());
}

// POST con auth
function postData_(url, payload) {
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'Bearer ' + PropertiesService.getScriptProperties().getProperty('API_TOKEN')
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  return JSON.parse(response.getContentText());
}

// Batch (paralelo) — MUCHO mas rapido
function fetchMultiple_(urls) {
  const requests = urls.map(url => ({ url, method: 'get', muteHttpExceptions: true }));
  return UrlFetchApp.fetchAll(requests).map(r => JSON.parse(r.getContentText()));
}

// Exponential backoff para rate limiting
function fetchWithRetry_(url, options, maxRetries = 5) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const response = UrlFetchApp.fetch(url, { ...options, muteHttpExceptions: true });
    if (response.getResponseCode() !== 429) return response;
    Utilities.sleep(Math.pow(2, attempt) * 1000 + Math.random() * 1000);
  }
  throw new Error('Max retries exceeded');
}
```

## 7. Batch Processing (superar limite de 6 min)

```javascript
function processBatch() {
  const props = PropertiesService.getScriptProperties();
  const startIndex = parseInt(props.getProperty('lastIndex') || '0');
  const startTime = new Date().getTime();
  const MAX_RUNTIME = 5 * 60 * 1000; // 5 min (margen de 1 min)

  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName('Data');
  const data = sheet.getDataRange().getValues();

  for (let i = startIndex; i < data.length; i++) {
    if (new Date().getTime() - startTime > MAX_RUNTIME) {
      props.setProperty('lastIndex', i.toString());
      ScriptApp.newTrigger('processBatch')
        .timeBased()
        .after(1 * 60 * 1000)
        .create();
      console.log(`Pausado en indice ${i}. Continuara en 1 minuto.`);
      return;
    }
    processRow_(data[i]);
  }

  // Completado: limpiar
  props.deleteProperty('lastIndex');
  console.log('Proceso completado.');
}
```

## 8. Error Handling Centralizado

```javascript
function withErrorHandling_(fn, context = '') {
  try {
    return fn();
  } catch (error) {
    console.error(`[${context}] Error: ${error.message}`);
    console.error(`Stack: ${error.stack}`);

    // Notificar por email si es critico
    if (error.message.includes('quota') || error.message.includes('timeout')) {
      MailApp.sendEmail({
        to: PropertiesService.getScriptProperties().getProperty('ADMIN_EMAIL'),
        subject: `[Apps Script Error] ${context}`,
        body: `Error: ${error.message}\nStack: ${error.stack}\nTimestamp: ${new Date()}`
      });
    }

    throw error;
  }
}

// Uso
function myFunction() {
  return withErrorHandling_(() => {
    const data = SpreadsheetApp.getActiveSheet().getDataRange().getValues();
    return processData_(data);
  }, 'myFunction');
}
```

## 9. CardService (Workspace Add-ons)

```javascript
function buildHomePage(e) {
  const card = CardService.newCardBuilder();

  const header = CardService.newCardHeader()
    .setTitle('Mi Add-on')
    .setSubtitle('Panel principal');

  const section = CardService.newCardSection()
    .setHeader('Acciones')
    .addWidget(
      CardService.newTextInput()
        .setFieldName('query')
        .setTitle('Buscar')
    )
    .addWidget(
      CardService.newTextButton()
        .setText('Buscar')
        .setOnClickAction(
          CardService.newAction().setFunctionName('onSearch')
        )
    );

  card.setHeader(header).addSection(section);
  return card.build();
}
```

## 10. Custom Functions para Sheets

```javascript
/**
 * Busca el precio de un producto.
 *
 * @param {string} productId El ID del producto.
 * @return {number} El precio.
 * @customfunction
 */
function PRODUCT_PRICE(productId) {
  if (!productId) return '';
  const cache = CacheService.getScriptCache();
  const cached = cache.get('price_' + productId);
  if (cached) return parseFloat(cached);

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Products');
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === productId) {
      cache.put('price_' + productId, data[i][2].toString(), 300);
      return data[i][2];
    }
  }
  return 'No encontrado';
}
```

**Reglas de Custom Functions:**
- Timeout 30 segundos
- No acceden a servicios con autorizacion (no Gmail, no UrlFetchApp, no PropertiesService)
- Tag `@customfunction` en JSDoc para autocomplete en Sheets
- No terminar en `_` (serian privadas)
- Reciben rangos como arrays 2D

## 11. Mail Merge con Gmail + Sheets

```javascript
function sendMailMerge() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data.shift();
  const emailCol = headers.indexOf('email');
  const statusCol = headers.indexOf('status');

  const draft = GmailApp.getDrafts()[0];
  const template = draft.getMessage();
  const subject = template.getSubject();
  const body = template.getBody();

  data.forEach((row, index) => {
    if (row[statusCol] === 'sent') return;

    let personalizedBody = body;
    headers.forEach((header, i) => {
      personalizedBody = personalizedBody.replace(
        new RegExp(`{{${header}}}`, 'g'), row[i]
      );
    });

    GmailApp.sendEmail(row[emailCol], subject, '', {
      htmlBody: personalizedBody,
      name: 'Mi Empresa'
    });

    sheet.getRange(index + 2, statusCol + 1).setValue('sent');
  });

  SpreadsheetApp.flush();
}
```

## 12. OAuth para APIs Externas

Para servicios no-Google, usar la biblioteca [apps-script-oauth2](https://github.com/googleworkspace/apps-script-oauth2):

```javascript
// Para APIs de Google, usar el token nativo
function callGoogleApi_() {
  const token = ScriptApp.getOAuthToken();
  return UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files', {
    headers: { 'Authorization': 'Bearer ' + token }
  });
}
```

## Reglas de Performance Criticas

1. **Batch siempre**: `getValues()`/`setValues()` en vez de celda por celda
2. **No interleave**: Agrupar reads, luego writes
3. **`muteHttpExceptions: true`**: Siempre en `UrlFetchApp.fetch()`
4. **`fetchAll()`**: Para multiples URLs en paralelo
5. **Cache agresivo**: `CacheService` para datos frecuentes
6. **Lock para concurrencia**: `LockService` cuando multiples ejecuciones modifican el mismo recurso
7. **Minimizar `flush()`**: Solo cuando el usuario necesita ver cambios intermedios
8. **No abusar de libraries**: Impacto en performance — copiar codigo si la velocidad importa
