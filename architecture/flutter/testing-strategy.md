# Estrategia de Testing

## Tipos de Tests

| Tipo | Qué testear | Cuándo | Herramientas |
|------|-------------|--------|--------------|
| **Unit** | BLoCs, repositories, usecases | Siempre | `bloc_test`, `mockito` |
| **Widget** | Layouts con múltiples screen sizes | Siempre | `flutter_test` |
| **Golden** | Pantallas core | Features críticas | `alchemist` |
| **Acceptance** | Criterios AC-XX del PRD | Siempre (si hay PRD) | `patrol` |

## Screen Sizes para Tests

```dart
const screenSizes = [
  Size(375, 667),   // iPhone SE (mobile)
  Size(768, 1024),  // iPad Portrait (tablet)
  Size(1440, 900),  // MacBook (desktop)
];
```

---

## Unit Tests (BLoC)

### Setup

```yaml
# pubspec.yaml
dev_dependencies:
  bloc_test: ^9.1.0
  mocktail: ^1.0.0
```

### Estructura

```
test/
├── presentation/
│   └── features/
│       └── login/
│           └── bloc/
│               └── login_bloc_test.dart
├── data/
│   └── repositories/
│       └── auth_repository_test.dart
└── mocks/
    └── mock_repositories.dart
```

### Template: BLoC Test

```dart
// login_bloc_test.dart
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:my_app/presentation/features/login/bloc/login_bloc.dart';

class MockAuthRepository extends Mock implements AuthRepository {}

void main() {
  late MockAuthRepository authRepository;

  setUp(() {
    authRepository = MockAuthRepository();
  });

  group('LoginBloc', () {
    test('initial state is correct', () {
      final bloc = LoginBloc(authRepository: authRepository);
      expect(bloc.state, equals(const LoginState()));
    });

    blocTest<LoginBloc, LoginState>(
      'emits [loading, success] when login succeeds',
      build: () {
        when(() => authRepository.login(
          email: any(named: 'email'),
          password: any(named: 'password'),
        )).thenAnswer((_) async {});

        return LoginBloc(authRepository: authRepository);
      },
      act: (bloc) => bloc.add(
        const LoginSubmitted(email: 'test@test.com', password: '123456'),
      ),
      expect: () => [
        const LoginState(status: LoginStatus.loading),
        const LoginState(status: LoginStatus.success),
      ],
    );

    blocTest<LoginBloc, LoginState>(
      'emits [loading, failure] when login fails',
      build: () {
        when(() => authRepository.login(
          email: any(named: 'email'),
          password: any(named: 'password'),
        )).thenThrow(Exception('Invalid credentials'));

        return LoginBloc(authRepository: authRepository);
      },
      act: (bloc) => bloc.add(
        const LoginSubmitted(email: 'test@test.com', password: 'wrong'),
      ),
      expect: () => [
        const LoginState(status: LoginStatus.loading),
        isA<LoginState>()
            .having((s) => s.status, 'status', LoginStatus.failure)
            .having((s) => s.errorMessage, 'errorMessage', isNotNull),
      ],
    );
  });
}
```

---

## Widget Tests (Responsive)

### Template: Test Multi-Size

```dart
// dashboard_layout_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mocktail/mocktail.dart';

import 'package:my_app/presentation/features/dashboard/page/dashboard_page.dart';

class MockDashboardBloc extends MockBloc<DashboardEvent, DashboardState>
    implements DashboardBloc {}

void main() {
  late MockDashboardBloc dashboardBloc;

  setUp(() {
    dashboardBloc = MockDashboardBloc();
    when(() => dashboardBloc.state).thenReturn(
      const DashboardState(
        status: DashboardStatus.success,
        totalUsers: 100,
        totalRevenue: 5000,
        totalOrders: 50,
      ),
    );
  });

  group('DashboardPage responsive layouts', () {
    testWidgets('renders mobile layout on small screens', (tester) async {
      // iPhone SE size
      tester.view.physicalSize = const Size(375, 667);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider<DashboardBloc>.value(
            value: dashboardBloc,
            child: const DashboardPage(),
          ),
        ),
      );

      // Verificar elementos de mobile layout
      expect(find.byType(Drawer), findsNothing); // Drawer cerrado
      expect(find.byType(AppBar), findsOneWidget);

      // Cleanup
      addTearDown(tester.view.resetPhysicalSize);
    });

    testWidgets('renders tablet layout on medium screens', (tester) async {
      // iPad size
      tester.view.physicalSize = const Size(768, 1024);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider<DashboardBloc>.value(
            value: dashboardBloc,
            child: const DashboardPage(),
          ),
        ),
      );

      // Verificar elementos de tablet layout
      expect(find.byType(AppBar), findsOneWidget);

      addTearDown(tester.view.resetPhysicalSize);
    });

    testWidgets('renders desktop layout on large screens', (tester) async {
      // MacBook size
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider<DashboardBloc>.value(
            value: dashboardBloc,
            child: const DashboardPage(),
          ),
        ),
      );

      // Verificar elementos de desktop layout
      expect(find.byType(NavigationRail), findsOneWidget);

      addTearDown(tester.view.resetPhysicalSize);
    });
  });
}
```

### Helper para Tests Multi-Size

```dart
// test/helpers/screen_size_helper.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

extension ScreenSizeTestExtension on WidgetTester {
  void setScreenSize(Size size) {
    view.physicalSize = size;
    view.devicePixelRatio = 1.0;
  }

  void resetScreenSize() {
    view.resetPhysicalSize();
    view.resetDevicePixelRatio();
  }
}

void testAllScreenSizes(
  String description, {
  required Future<void> Function(WidgetTester tester, Size size) test,
}) {
  const sizes = {
    'mobile': Size(375, 667),
    'tablet': Size(768, 1024),
    'desktop': Size(1440, 900),
  };

  for (final entry in sizes.entries) {
    testWidgets('$description [${entry.key}]', (tester) async {
      tester.setScreenSize(entry.value);
      await test(tester, entry.value);
      addTearDown(tester.resetScreenSize);
    });
  }
}
```

---

## Golden Tests

### Setup

```yaml
# pubspec.yaml
dev_dependencies:
  alchemist: ^0.10.0
```

> **Nota**: `golden_toolkit` está discontinuado. Usar `alchemist` (por Betterment) que ofrece
> consistencia cross-platform con font Ahem para CI y goldens legibles para desarrollo local.

### Template

```dart
// dashboard_golden_test.dart
import 'package:alchemist/alchemist.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:my_app/presentation/features/dashboard/page/dashboard_page.dart';

void main() {
  goldenTest(
    'DashboardPage renders correctly',
    fileName: 'dashboard_page',
    builder: () => GoldenTestGroup(
      scenarioConstraints: BoxConstraints(maxWidth: 400),
      children: [
        GoldenTestScenario(
          name: 'default state',
          child: const DashboardPage(),
        ),
        GoldenTestScenario(
          name: 'empty state',
          child: const DashboardPage(isEmpty: true),
        ),
      ],
    ),
  );
}
```

### Goldens: CI vs Platform

- **CI goldens** (`goldens/ci/`): Usan font Ahem (cuadros), consistentes en todos los OS. Tracked en git.
- **Platform goldens** (`goldens/`): Legibles con fonts reales, solo para desarrollo local. `.gitignore`d.

### Generar/Actualizar Goldens

```bash
# Generar goldens
flutter test --update-goldens

# Ejecutar tests (comparar contra goldens existentes)
flutter test
```

---

## Cobertura

```bash
# Generar reporte de cobertura
flutter test --coverage

# Ver reporte HTML (requiere lcov)
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```

## Estructura de Tests Recomendada

```
test/
├── helpers/
│   ├── pump_app.dart           # Helper para pump widgets
│   └── screen_size_helper.dart # Helper para screen sizes
├── mocks/
│   ├── mock_repositories.dart
│   └── mock_blocs.dart
├── data/
│   ├── datasources/
│   └── repositories/
├── domain/
│   └── usecases/
├── presentation/
│   └── features/
│       └── {feature}/
│           ├── bloc/
│           │   └── {feature}_bloc_test.dart
│           └── layouts/
│               └── {feature}_layouts_test.dart
├── goldens/
│   └── {feature}_golden_test.dart
└── acceptance/
    ├── ac_01_{description}_test.dart
    └── ac_02_{description}_test.dart
```

---

## Acceptance Tests (Patrol)

> Tests E2E que validan acceptance criteria (AC-XX) del PRD con evidencia visual.
> Generados por AG-09a. Validados por AG-09b.

### Setup

```yaml
# pubspec.yaml
dev_dependencies:
  patrol: ^4.0.0
```

```yaml
# patrol.yaml (raíz del proyecto)
app_name: {app_name}
android:
  package_name: {package_name}
ios:
  bundle_id: {bundle_id}
```

### Template: Acceptance Test

```dart
// test/acceptance/ac_01_crear_propiedad_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';

import 'package:{app}/main.dart' as app;

void main() {
  patrolTest(
    'AC-01: Usuario puede crear propiedad con nombre, dirección y foto',
    ($) async {
      app.main();
      await $.pumpAndSettle();

      // Navegar a crear propiedad
      await $.tap(find.text('Nueva Propiedad'));
      await $.pumpAndSettle();

      // Completar formulario
      await $.enterText(
        find.byKey(const Key('name_field')),
        'Depto Centro',
      );
      await $.enterText(
        find.byKey(const Key('address_field')),
        'Av. Libertador 1234',
      );

      // Interacción nativa (permiso de cámara)
      await $.native.tap(NativeSelector(text: 'Allow'));

      // Guardar
      await $.tap(find.byKey(const Key('save_btn')));
      await $.pumpAndSettle();

      // Verificar resultado
      expect(find.text('Depto Centro'), findsOneWidget);

      // Capturar evidencia
      await $.takeScreenshot('AC-01_crear_propiedad');
    },
  );
}
```

### Ejecución

```bash
# Ejecutar acceptance tests
flutter test test/acceptance/ --reporter expanded

# Con Patrol (para interacciones nativas)
patrol test test/acceptance/
```

### Evidencia

Screenshots se guardan en `.quality/evidence/{feature}/acceptance/`:
- `AC-01_{description}.png`
- `AC-02_{description}.png`
- `results.json` (resumen de ejecución)

### Diferencia con otros tipos de test

| Tipo | Qué valida | Quién genera | Evidencia |
|------|-----------|-------------|-----------|
| Unit (AG-04) | Lógica de código funciona | AG-04 | Coverage % |
| Widget (AG-04) | UI renderiza correctamente | AG-04 | — |
| Golden (AG-04) | UI no cambió visualmente | AG-04 | Diff images |
| **Acceptance (AG-09a)** | **Feature cumple el PRD** | **AG-09a** | **Screenshots + report** |
