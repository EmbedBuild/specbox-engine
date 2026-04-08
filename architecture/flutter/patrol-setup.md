# Patrol v4 — Flutter Mobile E2E Testing

> Guía para E2E testing nativo con Patrol v4 (LeanCode).
> Usar cuando se necesiten interacciones nativas: permisos, notificaciones, WebViews, biometría.
> Para Flutter Web: usar Playwright (`e2e-testing.md`). Ver `doc/decisions/e2e-flutter-strategy.md`.

---

## Cuándo usar Patrol vs Playwright

| Necesitas... | Usa |
|-------------|-----|
| Tests en browser (web) | Playwright (`e2e-testing.md`) |
| HTML Evidence Report nativo | Playwright |
| Permisos del dispositivo | **Patrol** |
| Notificaciones push | **Patrol** |
| WebViews embebidos | **Patrol** |
| Cámara / biometría | **Patrol** |
| Tests que corran en Android + iOS + Web | **Patrol** (write-once) + post-procesador para reporting |

---

## Setup

### 1. Dependencias

```yaml
# pubspec.yaml
dev_dependencies:
  patrol: ^4.5.0
  patrol_finders: ^3.2.0
```

```bash
# CLI
dart pub global activate patrol_cli ^4.3.0

# Verificar
patrol --version
```

### 2. Config nativa — Android

```java
// android/app/src/androidTest/java/com/example/app/MainActivityTest.java
package com.example.app;

import androidx.test.platform.app.InstrumentationRegistry;
import pl.leancode.patrol.PatrolJUnitRunner;

@RunWith(PatrolJUnitRunner.class)
public class MainActivityTest {
    @Rule
    public PatrolTestRule rule = new PatrolTestRule(MainActivityTest.class);

    @Test
    public void runPatrolTests() {
        PatrolTestRule.runDartTest(InstrumentationRegistry.getArguments());
    }
}
```

```groovy
// android/app/build.gradle
android {
    defaultConfig {
        minSdk = 21
        testInstrumentationRunner "pl.leancode.patrol.PatrolJUnitRunner"
    }
}
```

### 3. Config nativa — iOS

```ruby
# ios/Podfile (añadir al final)
target 'RunnerUITests' do
  pod 'patrol'
end
```

Crear scheme `RunnerUITests` en Xcode con target de UI Testing.

---

## Escribir tests

### Custom finders (`$`)

```dart
import 'package:patrol/patrol.dart';
import 'package:my_app/main.dart' as app;

void main() {
  patrolTest('AC-01: usuario crea propiedad', ($) async {
    app.main();
    await $.pumpAndSettle();

    // Custom finders — concisos, chainables
    await $(#nameField).enterText('Depto Centro');
    await $(#saveButton).tap();
    expect($('Depto Centro'), findsOneWidget);
  });
}
```

### Interacciones nativas

```dart
patrolTest('AC-03: usuario acepta permisos de cámara', ($) async {
  app.main();
  await $.pumpAndSettle();

  await $(#cameraButton).tap();

  // Patrol maneja el diálogo nativo del sistema
  await $.platform.grantPermissionWhenInUse();

  expect($(#cameraPreview), findsOneWidget);
});
```

### Platform API por plataforma

```dart
// Todas las plataformas
await $.platform.tap();

// Solo mobile
await $.platform.mobile.openNotifications();
await $.platform.mobile.tapOnNotificationByText('Nuevo mensaje');

// Solo Android
await $.platform.android.pressBack();

// Solo iOS
await $.platform.ios.acceptPermission();

// Solo Web
await $.platform.web.pressKey('Enter');
await $.platform.web.enableDarkMode();
```

---

## Screenshots para evidencia

### Naming convention obligatoria

```dart
Future<void> captureEvidence(
  PatrolIntegrationTester $,
  String acId,
  int step,
  String description,
) async {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  await binding.takeScreenshot('${acId}_step_${step}_$description');
}
```

### Uso en tests

```dart
patrolTest('AC-01: crear propiedad', ($) async {
  app.main();
  await $.pumpAndSettle();

  // Step 1: navegar
  await $(#newPropertyButton).tap();
  await $.pumpAndSettle();
  await captureEvidence($, 'AC-01', 1, 'navigate_to_form');

  // Step 2: completar formulario
  await $(#nameField).enterText('Depto Centro');
  await $.pumpAndSettle();
  await captureEvidence($, 'AC-01', 2, 'fill_form');

  // Step 3: guardar
  await $(#saveButton).tap();
  await $.pumpAndSettle();
  await captureEvidence($, 'AC-01', 3, 'save_success');

  expect($('Depto Centro'), findsOneWidget);
});
```

### Dónde se guardan los screenshots

| Plataforma | Ruta |
|-----------|------|
| Android | `build/app/outputs/connected_android_test_additional_output/emulator-XXXX/` |
| iOS | Dentro del `.xcresult` bundle (`Attachments/`) |

---

## Integración con Gherkin BDD

### bdd_widget_test + Patrol

```yaml
# pubspec.yaml
dev_dependencies:
  bdd_widget_test: ^latest
  patrol: ^4.5.0
```

```yaml
# build.yaml
targets:
  $default:
    builders:
      bdd_widget_test:
        options:
          testMethodName: patrolTest
          testerName: $
          testerType: PatrolIntegrationTester
```

Los `.feature` se comparten con el path de Playwright (misma carpeta `test/acceptance/features/`).

---

## Ejecución

```bash
# Android (emulador corriendo)
patrol test --target test/acceptance/

# iOS (simulador corriendo)
patrol test --target test/acceptance/ --device iPhone-16

# Web (Chrome)
patrol test --device chrome --target test/acceptance/

# Un solo test
patrol test --target test/acceptance/ac_01_crear_propiedad_test.dart

# CI (headless)
patrol test --target test/acceptance/ --device chrome --web-headless true
```

---

## Generar HTML Evidence Report

Patrol no genera HTML reports. Tras ejecutar los tests, usar el post-procesador:

```bash
node .quality/scripts/patrol-evidence-generator.js \
  --uc-id UC-001 \
  --feature crear-propiedad \
  --screenshots build/app/outputs/connected_android_test_additional_output/emulator-5554/ \
  --junit build/app/outputs/androidTest-results/connected/TEST-MainActivityTest.xml \
  --output .quality/evidence/crear-propiedad/acceptance/e2e-evidence-report.html
```

Esto genera un HTML self-contained idéntico al que produce Playwright, con screenshots base64 embebidos.

Ver `.quality/scripts/patrol-evidence-generator.js` para el código del generador.

---

## CI/CD

### GitHub Actions (Android)

```yaml
- name: Build APK para tests
  run: patrol build android --target test/acceptance/

- name: Ejecutar en Firebase Test Lab
  uses: google-github-actions/firebase-test-lab@v1
  with:
    apk: build/app/outputs/apk/debug/app-debug.apk
    test-apk: build/app/outputs/apk/androidTest/debug/app-debug-androidTest.apk
    device: model=Pixel7,version=34

- name: Generar Evidence Report
  run: node .quality/scripts/patrol-evidence-generator.js ...
```

### Device Farms recomendadas

| Farm | Plataforma | Notas |
|------|-----------|-------|
| Firebase Test Lab | Android | Más popular, video incluido |
| emulator.wtf | Android | 2-5x más rápido que Firebase TL |
| BrowserStack | Android + iOS | Devices reales |

---

## Limitaciones conocidas

1. **iOS solo en inglés** para diálogos de permisos del sistema
2. **Hot restart no funciona en web** (bug upstream Flutter)
3. **Windows/Linux no soportado** (solo Android, iOS, macOS, Web)
4. **No genera reports HTML** — requiere post-procesador (`patrol-evidence-generator.js`)
5. **Screenshots no automáticos on-failure** — hay que capturarlos explícitamente

---

*Referencia: SpecBox Engine v5.19.0 — Patrol v4 Setup Guide*
*Decisión arquitectónica: `doc/decisions/e2e-flutter-strategy.md`*
