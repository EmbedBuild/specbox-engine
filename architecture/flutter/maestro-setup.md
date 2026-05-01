# Maestro — Flutter Mobile E2E Testing (recomendado)

> Guía para E2E testing con Maestro (mobile-dev-inc) en Flutter Mobile (Android + iOS).
> **Recomendado por defecto** para nuevos proyectos Flutter mobile en SpecBox v5.28+.
> Patrol v4 sigue soportado como ruta legacy — ver `patrol-setup.md`.

---

## Por qué Maestro (vs Patrol)

| Necesitas... | Recomendado |
|---|---|
| Tests cross-platform iOS + Android con un único script | **Maestro** |
| Tolerancia automática a flake (auto-retry, wait-for-stability) | **Maestro** |
| Tests escritos por QA o PM (no solo devs) | **Maestro** (YAML) |
| Production builds testables | **Maestro** (black-box) |
| Acceso a estado interno Dart (Provider, BLoC) durante el test | Patrol |
| Aserciones complejas con lógica condicional | Patrol (Dart > YAML) |
| Tests en Flutter Web | **Playwright** (no Maestro — ver Limitaciones) |
| Flutter Desktop (macOS/Windows/Linux) | Ninguno cubierto hoy |

**Regla por defecto**: empieza con Maestro. Solo migra/mantén Patrol si necesitas acceso a estado Dart-side o aserciones que YAML no expresa bien.

---

## Setup

### 1. Instalación CLI

```bash
# macOS / Linux
curl -Ls "https://get.maestro.mobile.dev" | bash

# Verificar
maestro --version
```

No requiere dependencias en `pubspec.yaml`. Maestro opera sobre el binario compilado (APK/IPA), **no inyecta código en la app**.

### 2. Hacer los widgets addressables

Maestro usa la **Semantics Tree** de Flutter, no las `Key`. Las `Key` no se exponen al accessibility layer.

#### Texto visible (implícito)
```dart
Text('Guardar')              // → tapOn: "Guardar"
TextField(hintText: 'Email') // → tapOn: "Email"
```

#### `semanticLabel` (para iconos / botones sin texto)
```dart
IconButton(
  icon: Icon(Icons.add, semanticLabel: 'fabAddIcon'),
  onPressed: () {},
)
// → tapOn: "fabAddIcon"
```

#### `Semantics` widget (para áreas / contenedores)
```dart
Semantics(
  label: 'property_card',
  child: Container(...),
)
// → tapOn: "property_card"
```

#### `Semantics.identifier` (recomendado, Flutter 3.19+)

Identificador estable e inmutable, no dependiente de traducción. **Esta es la mejor práctica para tests**.

```dart
Semantics(
  identifier: 'btn_save_property',
  child: ElevatedButton(
    onPressed: _save,
    child: Text('Guardar'),  // texto puede cambiar por traducción
  ),
)
// → tapOn:
//     id: "btn_save_property"
```

---

## Escribir un flow

### Estructura del proyecto

```
.maestro/
  flows/
    UC-001_crear_propiedad/
      AC-01_crear_con_datos_validos.yaml
      AC-02_validacion_inline.yaml
      AC-03_aceptar_permisos_camara.yaml
    config.yaml          # opcional — variables compartidas
```

### Ejemplo: AC-01 con screenshots

```yaml
# .maestro/flows/UC-001_crear_propiedad/AC-01_crear_con_datos_validos.yaml
appId: com.embedbuild.myapp
name: "AC-01: Usuario crea propiedad con datos válidos"
---
- launchApp:
    clearState: true
- assertVisible: "Iniciar sesión"
- tapOn:
    id: "btn_login"
- inputText: "test@embed.build"
- tapOn:
    id: "input_password"
- inputText: "TestPassword123"
- tapOn:
    id: "btn_submit"
- assertVisible: "Mis propiedades"
- takeScreenshot: AC-01_step_1_logged_in

- tapOn:
    id: "fab_add_property"
- assertVisible: "Nueva propiedad"
- takeScreenshot: AC-01_step_2_form_open

- tapOn:
    id: "input_name"
- inputText: "Depto Centro"
- tapOn:
    id: "btn_save"
- assertVisible: "Depto Centro"
- takeScreenshot: AC-01_step_3_save_success
```

### Naming convention para screenshots

**Obligatorio**: `AC-XX_step_N_descripcion`. El generator usa este patrón para correlacionar screenshots con AC-XX.

### Interacciones nativas

Maestro maneja los diálogos del SO automáticamente:

```yaml
# Permisos de cámara (Android e iOS)
- tapOn:
    id: "btn_open_camera"
- tapOn: "Allow|Permitir|While using the app"   # cubre múltiples idiomas

# Notificaciones push (Android 13+)
- tapOn: "Allow"
```

### Aserciones soportadas

```yaml
- assertVisible: "texto"
- assertVisible:
    id: "elemento"
- assertNotVisible: "texto"
- assertTrue: ${output.someValue == 'expected'}
```

### Variables y reutilización

```yaml
# .maestro/flows/login.yaml — flow reutilizable
appId: com.embedbuild.myapp
---
- launchApp
- tapOn:
    id: "btn_login"
- inputText: ${EMAIL}
- tapOn:
    id: "btn_submit"
```

```yaml
# AC-01.yaml — invoca el subflow
appId: com.embedbuild.myapp
---
- runFlow:
    file: ../login.yaml
    env:
      EMAIL: test@embed.build
- tapOn:
    id: "fab_add_property"
```

---

## Ejecución

### Local

```bash
# Android (emulador o device conectado)
maestro test .maestro/flows/UC-001_crear_propiedad/

# Solo un AC
maestro test .maestro/flows/UC-001_crear_propiedad/AC-01_crear_con_datos_validos.yaml

# iOS (simulador corriendo)
maestro test --device "iPhone 16 Pro" .maestro/flows/

# Output JUnit XML para SpecBox
maestro test --format junit --output build/maestro/results.xml .maestro/flows/UC-001_crear_propiedad/

# Con screenshots dir (Maestro graba todos los takeScreenshot a este path)
maestro test --output-dir build/maestro/UC-001 .maestro/flows/UC-001_crear_propiedad/
```

### Estructura de output

Tras `maestro test --output-dir build/maestro/UC-001`:

```
build/maestro/UC-001/
  results.xml                              # JUnit XML
  AC-01_step_1_logged_in.png
  AC-01_step_2_form_open.png
  AC-01_step_3_save_success.png
  AC-02_step_1_empty_field.png
  ...
  recording.mp4                            # opcional (--record)
```

---

## Generar HTML Evidence Report

Maestro **no genera HTML reports**. Tras ejecutar los tests, usar el post-procesador de SpecBox:

```bash
node .quality/scripts/maestro-evidence-generator.js \
  --uc-id UC-001 \
  --us-id US-01 \
  --feature crear-propiedad \
  --junit build/maestro/UC-001/results.xml \
  --screenshots build/maestro/UC-001/ \
  --output .quality/evidence/crear-propiedad/acceptance/e2e-evidence-report.html
```

Esto genera el mismo HTML self-contained que Patrol/Playwright, con screenshots base64 embebidos. **AG-09b no distingue el origen** — el contrato `results.json` es idéntico.

`source` en `results.json` será `"maestro-junit-xml"` (nuevo en v5.28.0).

---

## CI/CD

### GitHub Actions — Android

```yaml
- name: Build Android APK
  run: flutter build apk --debug

- name: Install Maestro
  run: curl -Ls "https://get.maestro.mobile.dev" | bash

- name: Start Android emulator
  uses: reactivecircus/android-emulator-runner@v2
  with:
    api-level: 34
    target: google_apis
    arch: x86_64
    script: |
      flutter install --debug
      maestro test --format junit \
        --output build/maestro/results.xml \
        --output-dir build/maestro/ \
        .maestro/flows/

- name: Generate Evidence Report
  run: |
    node .quality/scripts/maestro-evidence-generator.js \
      --uc-id ${{ env.UC_ID }} \
      --feature ${{ env.FEATURE }} \
      --junit build/maestro/results.xml \
      --screenshots build/maestro/ \
      --output .quality/evidence/${{ env.FEATURE }}/acceptance/e2e-evidence-report.html
```

Template completo en `templates/github-actions/maestro-e2e.yml`.

### Maestro Cloud (paralelización)

`maestro cloud` ejecuta en infra de mobile-dev-inc (Android + iOS reales, paralelo). Es **paid**. Para SpecBox no es requisito; la CLI gratis basta para CI serial.

---

## Troubleshooting

### "Element not found" pese a usar Semantics
1. Confirma Flutter ≥ 3.19 (por `Semantics.identifier`).
2. En Android, verifica que el emulador tiene **TalkBack disponible**: Maestro lee la Semantics tree por accessibility APIs.
3. Inspecciona el árbol en vivo: `maestro studio` abre un visualizador interactivo.

### Tests pasan local, fallan en CI
- **Animaciones**: usa `--no-animations` en builds de test, o `assertVisible` con timeout más alto:
  ```yaml
  - assertVisible:
      text: "Guardado"
      timeout: 8000
  ```
- **Network requests**: si la app espera red real, mockea desde el lado app o usa fixtures determinísticos.

### Permisos del SO no se aceptan
- iOS: el simulador debe estar en **inglés** (mismo problema que Patrol).
- Android: textos varían por SO version y idioma; usa pipe `Allow|Permitir|OK`.

---

## Limitaciones conocidas

1. **Flutter Desktop NO soportado** — solo Android, iOS, Web (Web con caveats).
2. **Flutter Web sobre CanvasKit es frágil** — issue [mobile-dev-inc/maestro#2591](https://github.com/mobile-dev-inc/maestro/issues/2591). Mismo techo que Playwright sobre CanvasKit. **Para Web, SpecBox sigue usando Playwright**.
3. **Sin acceso a estado Dart-side** — black-box. Si necesitas leer/mockear un Provider o BLoC desde el test, usa Patrol.
4. **YAML menos expresivo que Dart** — para lógica condicional compleja existe `runScript` con JS, pero es workaround.
5. **iOS solo en inglés para diálogos del sistema** (mismo issue que Patrol).
6. **Maestro Cloud (paralelización) es paid** — la CLI local gratis ejecuta serial.

---

## Cuándo elegir Patrol en lugar de Maestro

Mantén Patrol si:
- Tu test necesita **leer estado interno Dart** (Provider, BLoC, GetIt singleton).
- Necesitas **mockear un servicio Flutter desde el test** (network, storage).
- Tu UC depende de **biometría** y necesitas controlar el simulador (Maestro lo soporta de forma más limitada).
- Ya tienes una suite Patrol funcionando y migrar no aporta ROI inmediato.

Si **no** se cumple ninguna de las anteriores, Maestro es la opción por defecto.

---

## Referencias

- Documentación oficial: [docs.maestro.dev](https://docs.maestro.dev/get-started/supported-platform/flutter)
- Flutter Semantics.identifier: [api.flutter.dev/flutter/semantics/SemanticsProperties/identifier.html](https://api.flutter.dev/flutter/semantics/SemanticsProperties/identifier.html)
- SpecBox decisión: ver entrada de changelog `5.28.0` en `ENGINE_VERSION.yaml`
- Generator: `.quality/scripts/maestro-evidence-generator.js`
- Patrol setup (legacy): `architecture/flutter/patrol-setup.md`

---

*SpecBox Engine v5.28.0 — Maestro Flutter Setup Guide*
