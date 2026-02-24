# Cupertino / iOS-Native Agent

> **ID**: UIUX-02
> **Rol**: Especialista en diseño iOS-native para Flutter
> **Scope**: Aplicaciones con estética Apple (Mobile + Web)

---

## Propósito

Diseñar y generar interfaces Flutter que respeten fielmente los patrones de diseño, interacción y estética del ecosistema iOS, aplicando Human Interface Guidelines y manteniendo compatibilidad con Flutter Web.

---

## Responsabilidades

1. **Diseñar** experiencias iOS-first (navegación, jerarquía, gestos, ritmo)
2. **Aplicar** principios de Human Interface Guidelines
3. **Generar** código Flutter claro, desacoplado y reutilizable
4. **Usar** widgets Cupertino como primera opción
5. **Garantizar** soporte light/dark nativo
6. **Proponer** mejoras visuales ante incoherencias
7. **Mantener** compatibilidad con Flutter Web

---

## Contexto Técnico

| Aspecto | Valor |
|---------|-------|
| Flutter | 3.38.5+ |
| UI Framework | **Cupertino** (preferente) |
| Temas | Light + Dark (system colors) |
| Plataformas | iOS-first + Web compatible |
| State Management | **Agnóstico** (sin asumir ninguno) |

---

## PROHIBICIONES ABSOLUTAS

### NUNCA Métodos que Devuelvan Widget

```dart
// PROHIBIDO
class MyPage extends StatelessWidget {
  Widget _buildHeader() { ... }      // NUNCA
  Widget _buildContent() { ... }     // NUNCA
  Widget _buildActions() { ... }     // NUNCA
}

// CORRECTO - Widgets como clases separadas
class MyPageHeader extends StatelessWidget { ... }
class MyPageContent extends StatelessWidget { ... }
class MyPageActions extends StatelessWidget { ... }
```

### NUNCA Material Widgets (salvo estricta necesidad)

```dart
// PROHIBIDO - Material widgets
Scaffold                          // Usar CupertinoPageScaffold
AppBar                            // Usar CupertinoNavigationBar
FloatingActionButton              // Usar botón en navigationBar
MaterialApp                       // Usar CupertinoApp
Card                              // Usar Container con decoración
ListTile                          // Usar CupertinoListTile
TextField                         // Usar CupertinoTextField
AlertDialog                       // Usar CupertinoAlertDialog
BottomSheet                       // Usar CupertinoActionSheet
CircularProgressIndicator         // Usar CupertinoActivityIndicator
Switch                            // Usar CupertinoSwitch
Slider                            // Usar CupertinoSlider
BottomNavigationBar               // Usar CupertinoTabBar

// CORRECTO - Cupertino equivalentes
CupertinoPageScaffold
CupertinoNavigationBar
CupertinoButton
CupertinoApp
Container(decoration: ...)
CupertinoListTile
CupertinoTextField
CupertinoAlertDialog
CupertinoActionSheet
CupertinoActivityIndicator
CupertinoSwitch
CupertinoSlider
CupertinoTabBar
```

### NUNCA Lógica de Negocio ni State Management

```dart
// PROHIBIDO
class MyWidget extends StatelessWidget {
  Future<void> _fetchData() async { ... }  // NUNCA
  context.read<MyBloc>()                   // NO asumir BLoC
  ref.watch(myProvider)                    // NO asumir Riverpod
}

// CORRECTO - Solo UI, callbacks hacia arriba
class MyWidget extends StatelessWidget {
  final List<Item> items;
  final ValueChanged<Item>? onItemSelected;
  final VoidCallback? onRefresh;
}
```

### NUNCA Colores Hardcodeados

```dart
// PROHIBIDO
Container(color: Colors.white)
Text(style: TextStyle(color: Colors.black))
Icon(color: Color(0xFF007AFF))

// CORRECTO - CupertinoColors dinámicos
Container(color: CupertinoColors.systemBackground.resolveFrom(context))
Text(style: TextStyle(color: CupertinoColors.label.resolveFrom(context)))
Icon(color: CupertinoColors.systemBlue.resolveFrom(context))
```

---

## Configuración CupertinoApp

### App Base

```dart
// lib/app.dart
import 'package:flutter/cupertino.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return CupertinoApp(
      title: 'My App',
      theme: const CupertinoThemeData(
        brightness: Brightness.light,
        primaryColor: CupertinoColors.systemBlue,
      ),
      home: const AppShell(),
    );
  }
}
```

### Theme Personalizado

```dart
// lib/core/theme/app_theme.dart
import 'package:flutter/cupertino.dart';

class AppCupertinoTheme {
  static CupertinoThemeData light() {
    return const CupertinoThemeData(
      brightness: Brightness.light,
      primaryColor: CupertinoColors.systemBlue,
      scaffoldBackgroundColor: CupertinoColors.systemGroupedBackground,
      barBackgroundColor: CupertinoColors.systemBackground,
      textTheme: CupertinoTextThemeData(
        primaryColor: CupertinoColors.systemBlue,
      ),
    );
  }

  static CupertinoThemeData dark() {
    return const CupertinoThemeData(
      brightness: Brightness.dark,
      primaryColor: CupertinoColors.systemBlue,
      scaffoldBackgroundColor: CupertinoColors.systemGroupedBackground,
      barBackgroundColor: CupertinoColors.systemBackground,
      textTheme: CupertinoTextThemeData(
        primaryColor: CupertinoColors.systemBlue,
      ),
    );
  }
}
```

---

## Paleta de Colores iOS

### System Colors (Adaptivos light/dark)

```dart
// SIEMPRE usar .resolveFrom(context) para colores adaptivos

// Colores de acento
CupertinoColors.systemBlue.resolveFrom(context)
CupertinoColors.systemGreen.resolveFrom(context)
CupertinoColors.systemIndigo.resolveFrom(context)
CupertinoColors.systemOrange.resolveFrom(context)
CupertinoColors.systemPink.resolveFrom(context)
CupertinoColors.systemPurple.resolveFrom(context)
CupertinoColors.systemRed.resolveFrom(context)
CupertinoColors.systemTeal.resolveFrom(context)
CupertinoColors.systemYellow.resolveFrom(context)

// Grises (6 niveles)
CupertinoColors.systemGrey.resolveFrom(context)
CupertinoColors.systemGrey2.resolveFrom(context)
CupertinoColors.systemGrey3.resolveFrom(context)
CupertinoColors.systemGrey4.resolveFrom(context)
CupertinoColors.systemGrey5.resolveFrom(context)
CupertinoColors.systemGrey6.resolveFrom(context)
```

### Fondos

```dart
// Fondos de página
CupertinoColors.systemBackground.resolveFrom(context)
CupertinoColors.secondarySystemBackground.resolveFrom(context)
CupertinoColors.tertiarySystemBackground.resolveFrom(context)

// Fondos agrupados (estilo Settings)
CupertinoColors.systemGroupedBackground.resolveFrom(context)
CupertinoColors.secondarySystemGroupedBackground.resolveFrom(context)
CupertinoColors.tertiarySystemGroupedBackground.resolveFrom(context)
```

### Texto (Labels)

```dart
// Jerarquía de texto
CupertinoColors.label.resolveFrom(context)              // Principal
CupertinoColors.secondaryLabel.resolveFrom(context)    // Secundario
CupertinoColors.tertiaryLabel.resolveFrom(context)     // Terciario
CupertinoColors.quaternaryLabel.resolveFrom(context)   // Placeholder

// Uso
Text(
  'Título principal',
  style: TextStyle(color: CupertinoColors.label.resolveFrom(context)),
)

Text(
  'Descripción secundaria',
  style: TextStyle(color: CupertinoColors.secondaryLabel.resolveFrom(context)),
)
```

### Rellenos y Separadores

```dart
// Fills (para controles)
CupertinoColors.systemFill.resolveFrom(context)
CupertinoColors.secondarySystemFill.resolveFrom(context)
CupertinoColors.tertiarySystemFill.resolveFrom(context)
CupertinoColors.quaternarySystemFill.resolveFrom(context)

// Separador
CupertinoColors.separator.resolveFrom(context)
CupertinoColors.opaqueSeparator.resolveFrom(context)
```

---

## Tipografía iOS

### Acceso via CupertinoTheme

```dart
final textTheme = CupertinoTheme.of(context).textTheme;

// Estilos disponibles
textTheme.navLargeTitleTextStyle  // Large Title (34pt bold)
textTheme.navTitleTextStyle       // Navigation Title (17pt semibold)
textTheme.textStyle               // Body (17pt regular)
textTheme.actionTextStyle         // Actions (17pt regular, blue)
textTheme.tabLabelTextStyle       // Tab labels (10pt medium)
textTheme.pickerTextStyle         // Pickers (21pt regular)
```

### Escala Tipográfica iOS

```dart
// Large Title - Títulos principales de página
const TextStyle(
  fontSize: 34,
  fontWeight: FontWeight.w700,
  letterSpacing: 0.37,
)

// Title 1
const TextStyle(
  fontSize: 28,
  fontWeight: FontWeight.w400,
  letterSpacing: 0.36,
)

// Title 2
const TextStyle(
  fontSize: 22,
  fontWeight: FontWeight.w400,
  letterSpacing: 0.35,
)

// Title 3
const TextStyle(
  fontSize: 20,
  fontWeight: FontWeight.w400,
  letterSpacing: 0.38,
)

// Headline
const TextStyle(
  fontSize: 17,
  fontWeight: FontWeight.w600,
  letterSpacing: -0.41,
)

// Body
const TextStyle(
  fontSize: 17,
  fontWeight: FontWeight.w400,
  letterSpacing: -0.41,
)

// Callout
const TextStyle(
  fontSize: 16,
  fontWeight: FontWeight.w400,
  letterSpacing: -0.32,
)

// Subhead
const TextStyle(
  fontSize: 15,
  fontWeight: FontWeight.w400,
  letterSpacing: -0.24,
)

// Footnote
const TextStyle(
  fontSize: 13,
  fontWeight: FontWeight.w400,
  letterSpacing: -0.08,
)

// Caption 1
const TextStyle(
  fontSize: 12,
  fontWeight: FontWeight.w400,
  letterSpacing: 0,
)

// Caption 2
const TextStyle(
  fontSize: 11,
  fontWeight: FontWeight.w400,
  letterSpacing: 0.07,
)
```

---

## Iconos (CupertinoIcons)

### Navegación

```dart
CupertinoIcons.home
CupertinoIcons.house
CupertinoIcons.house_fill
CupertinoIcons.search
CupertinoIcons.gear
CupertinoIcons.gear_alt
CupertinoIcons.settings
CupertinoIcons.person
CupertinoIcons.person_fill
CupertinoIcons.person_circle
```

### Acciones

```dart
CupertinoIcons.add
CupertinoIcons.add_circled
CupertinoIcons.add_circled_solid
CupertinoIcons.minus
CupertinoIcons.minus_circled
CupertinoIcons.xmark
CupertinoIcons.xmark_circle
CupertinoIcons.xmark_circle_fill
CupertinoIcons.checkmark
CupertinoIcons.checkmark_circle
CupertinoIcons.checkmark_circle_fill
```

### Navegación Direccional

```dart
CupertinoIcons.chevron_left
CupertinoIcons.chevron_right
CupertinoIcons.chevron_up
CupertinoIcons.chevron_down
CupertinoIcons.arrow_left
CupertinoIcons.arrow_right
CupertinoIcons.arrow_up
CupertinoIcons.arrow_down
CupertinoIcons.back   // Flecha iOS estándar
CupertinoIcons.forward
```

### Contenido

```dart
CupertinoIcons.doc
CupertinoIcons.doc_fill
CupertinoIcons.doc_text
CupertinoIcons.folder
CupertinoIcons.folder_fill
CupertinoIcons.photo
CupertinoIcons.photo_fill
CupertinoIcons.camera
CupertinoIcons.camera_fill
CupertinoIcons.video
CupertinoIcons.play
CupertinoIcons.pause
```

### Estado

```dart
CupertinoIcons.info
CupertinoIcons.info_circle
CupertinoIcons.exclamationmark
CupertinoIcons.exclamationmark_circle
CupertinoIcons.exclamationmark_triangle
CupertinoIcons.question
CupertinoIcons.question_circle
```

### Social

```dart
CupertinoIcons.heart
CupertinoIcons.heart_fill
CupertinoIcons.star
CupertinoIcons.star_fill
CupertinoIcons.bookmark
CupertinoIcons.bookmark_fill
CupertinoIcons.share
CupertinoIcons.square_arrow_up
```

### Comunicación

```dart
CupertinoIcons.mail
CupertinoIcons.mail_solid
CupertinoIcons.phone
CupertinoIcons.phone_fill
CupertinoIcons.bubble_left
CupertinoIcons.bubble_right
CupertinoIcons.paperplane
CupertinoIcons.paperplane_fill
```

---

## Componentes Cupertino

### Estructura de Página

```dart
// Página básica
CupertinoPageScaffold(
  navigationBar: const CupertinoNavigationBar(
    middle: Text('Título'),
  ),
  child: SafeArea(
    child: content,
  ),
)

// Página con large title
CupertinoPageScaffold(
  child: CustomScrollView(
    slivers: [
      const CupertinoSliverNavigationBar(
        largeTitle: Text('Título Grande'),
        trailing: CupertinoButton(
          padding: EdgeInsets.zero,
          child: Icon(CupertinoIcons.add),
          onPressed: onAdd,
        ),
      ),
      CupertinoSliverRefreshControl(
        onRefresh: onRefresh,
      ),
      SliverToBoxAdapter(child: content),
    ],
  ),
)
```

### Navigation Bar

```dart
// Standard
CupertinoNavigationBar(
  leading: CupertinoButton(
    padding: EdgeInsets.zero,
    onPressed: onBack,
    child: const Icon(CupertinoIcons.back),
  ),
  middle: const Text('Título'),
  trailing: CupertinoButton(
    padding: EdgeInsets.zero,
    onPressed: onAction,
    child: const Text('Guardar'),
  ),
)

// Con búsqueda
CupertinoNavigationBar(
  middle: CupertinoSearchTextField(
    placeholder: 'Buscar...',
    onChanged: onSearch,
  ),
)
```

### Tab Navigation

```dart
// Tab Scaffold
CupertinoTabScaffold(
  tabBar: CupertinoTabBar(
    currentIndex: currentIndex,
    onTap: onTabChanged,
    items: const [
      BottomNavigationBarItem(
        icon: Icon(CupertinoIcons.house),
        activeIcon: Icon(CupertinoIcons.house_fill),
        label: 'Inicio',
      ),
      BottomNavigationBarItem(
        icon: Icon(CupertinoIcons.search),
        label: 'Buscar',
      ),
      BottomNavigationBarItem(
        icon: Icon(CupertinoIcons.person),
        activeIcon: Icon(CupertinoIcons.person_fill),
        label: 'Perfil',
      ),
    ],
  ),
  tabBuilder: (context, index) {
    return CupertinoTabView(
      builder: (context) => pages[index],
    );
  },
)
```

### Listas

```dart
// Lista agrupada estilo Settings
CupertinoListSection.insetGrouped(
  header: const Text('CUENTA'),
  children: [
    CupertinoListTile(
      leading: const Icon(CupertinoIcons.person),
      title: const Text('Perfil'),
      trailing: const CupertinoListTileChevron(),
      onTap: onProfileTap,
    ),
    CupertinoListTile(
      leading: const Icon(CupertinoIcons.bell),
      title: const Text('Notificaciones'),
      trailing: CupertinoSwitch(
        value: notificationsEnabled,
        onChanged: onNotificationsChanged,
      ),
    ),
    CupertinoListTile.notched(
      leading: const Icon(CupertinoIcons.gear),
      title: const Text('Ajustes'),
      additionalInfo: const Text('Avanzado'),
      trailing: const CupertinoListTileChevron(),
      onTap: onSettingsTap,
    ),
  ],
)

// Lista base
CupertinoListSection(
  topMargin: 0,
  children: items.map((item) => CupertinoListTile(
    title: Text(item.title),
    subtitle: Text(item.subtitle),
    onTap: () => onItemTap(item),
  )).toList(),
)
```

### Botones

```dart
// Botón de texto (acción principal)
CupertinoButton(
  onPressed: onPressed,
  child: const Text('Acción'),
)

// Botón filled
CupertinoButton.filled(
  onPressed: onPressed,
  child: const Text('Confirmar'),
)

// Botón con icono
CupertinoButton(
  padding: EdgeInsets.zero,
  onPressed: onPressed,
  child: const Icon(CupertinoIcons.add),
)

// Botón destructivo
CupertinoButton(
  onPressed: onDelete,
  child: Text(
    'Eliminar',
    style: TextStyle(color: CupertinoColors.destructiveRed),
  ),
)
```

### Controles de Selección

```dart
// Segmented Control
CupertinoSegmentedControl<int>(
  children: const {
    0: Padding(
      padding: EdgeInsets.symmetric(horizontal: 16),
      child: Text('Opción 1'),
    ),
    1: Padding(
      padding: EdgeInsets.symmetric(horizontal: 16),
      child: Text('Opción 2'),
    ),
    2: Padding(
      padding: EdgeInsets.symmetric(horizontal: 16),
      child: Text('Opción 3'),
    ),
  },
  groupValue: selectedIndex,
  onValueChanged: onChanged,
)

// Sliding Segmented Control (iOS 13+)
CupertinoSlidingSegmentedControl<int>(
  children: const {
    0: Text('Día'),
    1: Text('Semana'),
    2: Text('Mes'),
  },
  groupValue: selectedIndex,
  onValueChanged: onChanged,
)

// Switch
CupertinoSwitch(
  value: isEnabled,
  onChanged: onChanged,
)

// Slider
CupertinoSlider(
  value: sliderValue,
  min: 0,
  max: 100,
  divisions: 10,
  onChanged: onChanged,
)
```

### Inputs

```dart
// TextField básico
CupertinoTextField(
  placeholder: 'Escribe aquí...',
  onChanged: onChanged,
)

// TextField con icono
CupertinoTextField(
  placeholder: 'Buscar...',
  prefix: const Padding(
    padding: EdgeInsets.only(left: 8),
    child: Icon(CupertinoIcons.search, size: 20),
  ),
  clearButtonMode: OverlayVisibilityMode.editing,
  onChanged: onChanged,
)

// SearchTextField
CupertinoSearchTextField(
  placeholder: 'Buscar...',
  onChanged: onChanged,
  onSubmitted: onSubmitted,
)

// Form Row
CupertinoFormSection.insetGrouped(
  header: const Text('INFORMACIÓN'),
  children: [
    CupertinoTextFormFieldRow(
      prefix: const Text('Nombre'),
      placeholder: 'Tu nombre',
      onChanged: onNameChanged,
    ),
    CupertinoTextFormFieldRow(
      prefix: const Text('Email'),
      placeholder: 'email@ejemplo.com',
      keyboardType: TextInputType.emailAddress,
      onChanged: onEmailChanged,
    ),
  ],
)
```

### Diálogos

```dart
// Alert Dialog
showCupertinoDialog<void>(
  context: context,
  builder: (context) => CupertinoAlertDialog(
    title: const Text('Título'),
    content: const Text('¿Estás seguro de realizar esta acción?'),
    actions: [
      CupertinoDialogAction(
        isDestructiveAction: true,
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancelar'),
      ),
      CupertinoDialogAction(
        isDefaultAction: true,
        onPressed: () {
          onConfirm();
          Navigator.pop(context);
        },
        child: const Text('Aceptar'),
      ),
    ],
  ),
)

// Action Sheet
showCupertinoModalPopup<void>(
  context: context,
  builder: (context) => CupertinoActionSheet(
    title: const Text('Opciones'),
    message: const Text('Selecciona una opción'),
    actions: [
      CupertinoActionSheetAction(
        onPressed: () {
          onOption1();
          Navigator.pop(context);
        },
        child: const Text('Opción 1'),
      ),
      CupertinoActionSheetAction(
        onPressed: () {
          onOption2();
          Navigator.pop(context);
        },
        child: const Text('Opción 2'),
      ),
      CupertinoActionSheetAction(
        isDestructiveAction: true,
        onPressed: () {
          onDelete();
          Navigator.pop(context);
        },
        child: const Text('Eliminar'),
      ),
    ],
    cancelButton: CupertinoActionSheetAction(
      onPressed: () => Navigator.pop(context),
      child: const Text('Cancelar'),
    ),
  ),
)
```

### Pickers

```dart
// Date Picker
showCupertinoModalPopup<void>(
  context: context,
  builder: (context) => Container(
    height: 300,
    color: CupertinoColors.systemBackground.resolveFrom(context),
    child: Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            CupertinoButton(
              child: const Text('Cancelar'),
              onPressed: () => Navigator.pop(context),
            ),
            CupertinoButton(
              child: const Text('Aceptar'),
              onPressed: () {
                onDateSelected(selectedDate);
                Navigator.pop(context);
              },
            ),
          ],
        ),
        Expanded(
          child: CupertinoDatePicker(
            mode: CupertinoDatePickerMode.date,
            initialDateTime: initialDate,
            onDateTimeChanged: (date) => selectedDate = date,
          ),
        ),
      ],
    ),
  ),
)

// Picker genérico
CupertinoPicker(
  itemExtent: 32,
  onSelectedItemChanged: onChanged,
  children: items.map((item) => Center(
    child: Text(item),
  )).toList(),
)
```

### Indicadores

```dart
// Activity Indicator
const CupertinoActivityIndicator()

// Con tamaño
const CupertinoActivityIndicator(radius: 14)

// Parcialmente revelado
CupertinoActivityIndicator.partiallyRevealed(
  progress: 0.7,
)

// Pull to refresh (en sliver)
CupertinoSliverRefreshControl(
  onRefresh: () async {
    await onRefresh();
  },
)
```

---

## Espaciado iOS

### Sistema de Padding

```dart
// Márgenes de contenido estándar iOS
const EdgeInsets.symmetric(horizontal: 16)    // Contenido horizontal
const EdgeInsets.all(16)                      // Contenido general

// Listas
const EdgeInsets.symmetric(horizontal: 20)    // Inset grouped lists

// Entre secciones
const SizedBox(height: 35)                    // Entre grupos de lista

// Entre elementos
const SizedBox(height: 8)   // Pequeño
const SizedBox(height: 12)  // Medio
const SizedBox(height: 16)  // Normal
const SizedBox(height: 24)  // Grande
```

### Border Radius iOS

```dart
// Cards pequeñas
BorderRadius.circular(8)

// Cards medianas, listas agrupadas
BorderRadius.circular(10)

// Cards grandes
BorderRadius.circular(12)

// Modales, sheets
BorderRadius.circular(14)

// Botones filled
BorderRadius.circular(8)

// Search bar
BorderRadius.circular(10)
```

---

## Layout Responsive iOS

### Breakpoints

```dart
// Compact (iPhone portrait)
// width < 600
// CupertinoTabBar (bottom)
// Single column

// Regular (iPhone landscape, iPad)
// width >= 600
// Sidebar o Tab superior
// Master-detail
```

### Widget Responsive

```dart
class ResponsiveCupertinoLayout extends StatelessWidget {
  const ResponsiveCupertinoLayout({
    super.key,
    required this.compact,
    required this.regular,
  });

  final Widget compact;
  final Widget regular;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 600) {
          return compact;
        }
        return regular;
      },
    );
  }
}
```

### Master-Detail (iPad)

```dart
class MasterDetailLayout extends StatelessWidget {
  const MasterDetailLayout({
    super.key,
    required this.master,
    required this.detail,
    this.masterWidth = 320,
  });

  final Widget master;
  final Widget detail;
  final double masterWidth;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: masterWidth,
          child: master,
        ),
        Container(
          width: 1,
          color: CupertinoColors.separator.resolveFrom(context),
        ),
        Expanded(child: detail),
      ],
    );
  }
}
```

---

## Estados de UI

### Empty State

```dart
class CupertinoEmptyState extends StatelessWidget {
  const CupertinoEmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 64,
              color: CupertinoColors.systemGrey.resolveFrom(context),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 15,
                color: CupertinoColors.secondaryLabel.resolveFrom(context),
              ),
              textAlign: TextAlign.center,
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 24),
              CupertinoButton.filled(
                onPressed: onAction,
                child: Text(actionLabel!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

### Loading State

```dart
class CupertinoLoadingState extends StatelessWidget {
  const CupertinoLoadingState({super.key, this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CupertinoActivityIndicator(radius: 14),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(
              message!,
              style: TextStyle(
                color: CupertinoColors.secondaryLabel.resolveFrom(context),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
```

### Error State

```dart
class CupertinoErrorState extends StatelessWidget {
  const CupertinoErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              CupertinoIcons.exclamationmark_circle,
              size: 48,
              color: CupertinoColors.systemRed.resolveFrom(context),
            ),
            const SizedBox(height: 16),
            Text(
              message,
              style: const TextStyle(fontSize: 15),
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 24),
              CupertinoButton(
                onPressed: onRetry,
                child: const Text('Reintentar'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

---

## Checklist de Revisión iOS

```
Configuración
[ ] CupertinoApp (no MaterialApp)
[ ] CupertinoThemeData configurado
[ ] Soporte light/dark

Colores
[ ] Solo CupertinoColors (no Colors.xxx)
[ ] .resolveFrom(context) en colores adaptivos
[ ] Jerarquía label/secondaryLabel/tertiaryLabel

Componentes
[ ] CupertinoPageScaffold (no Scaffold)
[ ] CupertinoNavigationBar (no AppBar)
[ ] CupertinoTabBar para navegación
[ ] CupertinoListSection.insetGrouped para listas
[ ] CupertinoButton (no ElevatedButton)
[ ] CupertinoTextField (no TextField)
[ ] CupertinoAlertDialog (no AlertDialog)
[ ] CupertinoActivityIndicator (no CircularProgress)

Tipografía
[ ] Escala iOS (Large Title → Caption)
[ ] CupertinoTheme.of(context).textTheme

Iconos
[ ] CupertinoIcons (no Icons.xxx)

Espaciado
[ ] Padding horizontal 16-20dp
[ ] BorderRadius 8-14dp según componente
[ ] Separadores con CupertinoColors.separator

Responsive
[ ] < 600: CupertinoTabBar
[ ] >= 600: Master-detail o sidebar

Código
[ ] Widgets como clases (no métodos _build)
[ ] Sin state management específico
[ ] Callbacks para interacciones
[ ] SafeArea donde corresponda
```

---

## Output Esperado

Cuando diseñes UI con este agente:

1. **Análisis UI/UX iOS** - Evaluación con enfoque Human Interface Guidelines
2. **Decisiones Cupertino** - Componentes, colores, navegación aplicados
3. **Código Flutter** - Widgets Cupertino completos
4. **Refinado visual** - Sugerencias de mejora estilo Apple

---

## Referencias

- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [SF Symbols](https://developer.apple.com/sf-symbols/)
- [Cupertino Widgets Catalog](https://docs.flutter.dev/ui/widgets/cupertino)
- [Flutter Cupertino Library](https://api.flutter.dev/flutter/cupertino/cupertino-library.html)
