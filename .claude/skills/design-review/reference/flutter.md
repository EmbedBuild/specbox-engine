# Verificar una pantalla Flutter

La misma verificación que en web ([verify.md](verify.md)), con lo que cambia en Flutter: las capturas
salen de las pruebas de widgets y las reglas se leen en el código Dart. La skill elige esta versión
cuando el proyecto tiene `pubspec.yaml`, y `verify.mjs` la usa cuando el destino es un `.dart`.

## 1. Capturar sin simulador

Desde la raíz del proyecto Flutter:

```bash
# Una vez por pantalla: la prueba de captura, con el widget tal como lo ve la persona
node <skill>/scripts/verify-flutter.mjs init --name {pantalla} \
  --import package:{app}/presentation/features/{feature}/page/{pantalla}_page.dart \
  --screen "MaterialApp(theme: AppTheme.light, home: {Pantalla}Page(repository: FakeRepository()))"

# Cada verificación
node <skill>/scripts/verify.mjs test/design_review/{pantalla}_design_review_test.dart \
  --out doc/design/{feature}/verify --name {pantalla}
```

- **Solo `flutter_test`**, que trae todo proyecto Flutter: ni `alchemist` ni `golden_toolkit`, ni
  simulador. Con `.fvmrc` usa `fvm flutter`; `FLUTTER_CMD` lo fuerza. Sin flutter sale con código 2.
- **Dos tamaños:** 390 × 844 (móvil) y 820 × 1180 (tableta), con `devicePixelRatio` 1.
- **Fuentes reales:** la prueba carga las fuentes del `pubspec` y Roboto e iconos de Material del SDK;
  sin eso, flutter_test pinta cada letra como un cuadro. Los emojis salen como un cuadro: no hay
  fuente de emoji en las pruebas (y un emoji como icono ya es un hallazgo).
- **Datos:** `--screen` monta la pantalla con su tema, sus proveedores y datos de prueba (fixtures,
  repositorios falsos), los mismos que usan las pruebas del proyecto. Nunca datos inventados para que
  quede bonita.
- **Desbordamiento:** cada `RenderFlex overflowed` se anota con el fichero y la línea del widget que
  desborda, sin romper la prueba. Es el equivalente del `scrollWidth` de la web.
- **Salida:** `{pantalla}-390.png`, `{pantalla}-820.png` y `{pantalla}-verify.json`, con la misma
  forma que en web (`stack: "flutter"`). El texto visible va en `numeros`, así que `--previous` y
  `--sources` señalan también aquí las cifras sin fuente tras una corrección.

## 2. Las reglas, en Flutter

| Lo que pide la rúbrica | En Flutter | Regla de `flutter-rules.mjs` |
|---|---|---|
| Área de pulsación de 44 px en táctil | **48 dp** (`kMinInteractiveDimension`). Nada de `MaterialTapTargetSize.shrinkWrap`, `VisualDensity.compact`, `BoxConstraints()` vacío ni cajas de menos de 48 alrededor de un control | `area-pulsacion` |
| Texto que respeta el tamaño del sistema | No anular el `TextScaler` (`TextScaler.noScaling`, `MediaQuery.withNoTextScaling`, `textScaleFactor: 1`). Probar a 1,3 y 2,0 con `MediaQuery(data: …copyWith(textScaler: TextScaler.linear(2)))` | `escala-texto` |
| Menos de 300 ms; `ease-out` en las respuestas, nunca `ease-in` | `Durations.short4` (200 ms) o `Durations.medium1` (250 ms); `Easing.emphasizedDecelerate` o `Curves.easeOutCubic`; nunca `Curves.easeIn`, `bounce*` ni `elastic*` | `movimiento` |
| `prefers-reduced-motion` respetado | `MediaQuery.disableAnimationsOf(context)` y, si es `true`, `Duration.zero` | `movimiento-reducido` |
| Material 3 | `useMaterial3` (verdadero por defecto). Con tokens del sistema, el `ColorScheme` y el `TextTheme` salen de los tokens, no de `ColorScheme.fromSeed` | `material3` |
| Iconos, no emojis | `Icon(Icons.…)` o el set de iconos del sistema | `emoji-icono` |
| Cifras tabulares | `TextStyle(fontFeatures: [FontFeature.tabularFigures()])` en cifras que se comparan | el revisor, en el código |
| Estados pulsado, deshabilitado y foco | `WidgetStateProperty.resolveWith` con `WidgetState.pressed`, `disabled` y `focused`; `onPressed: null` deshabilita | el revisor, en el código |
| Contraste | Se mide en las capturas y en los pares del tema | el revisor, en las capturas |
| Sin scroll horizontal | Sin `RenderFlex overflowed` a 390 | `desbordamiento` (en la prueba) |

Cada hallazgo lleva fichero, línea y columna. Las reglas leen el código, no lo ejecutan: son
patrones, así que el revisor los confirma en la captura o en el código. Una línea deliberada se marca
con `// design-review:ignore` y su motivo.

## 3. Revisar y corregir

Igual que en web: revisor aislado con el encargo de [verify.md](verify.md) (brief, rúbrica,
capturas, JSON y código), `{pantalla}.verify.md` y como mucho una ronda de corrección.
