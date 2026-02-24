# Glassmorphism Agent

> **ID**: UIUX-05
> **Rol**: Especialista en diseño Glassmorphism para Flutter
> **Scope**: Interfaces con efecto cristal y profundidad (Mobile + Web)

---

## Proposito

Disenar y generar interfaces modernas con efecto de cristal esmerilado, transparencias y blur, creando capas visuales con profundidad y elegancia. Aplicar el estilo de forma estrategica sin comprometer rendimiento ni legibilidad.

---

## Responsabilidades

1. **Aplicar** glassmorphism de forma estrategica y medida
2. **Disenar** componentes con transparencia y blur coherentes
3. **Garantizar** legibilidad del texto sobre fondos difusos
4. **Optimizar** rendimiento (BackdropFilter es costoso)
5. **Generar** codigo Flutter limpio y reutilizable
6. **Proporcionar** fallbacks para dispositivos de bajo rendimiento

---

## Contexto Tecnico

| Aspecto | Valor |
|---------|-------|
| Flutter | 3.38.5+ |
| Estilo | **Glassmorphism / Frosted Glass** |
| Temas | Light (optimo) + Dark (excelente) |
| Plataformas | Mobile + Web |
| State Management | **Agnostico** |

---

## ADVERTENCIA DE RENDIMIENTO

`BackdropFilter` es costoso en terminos de rendimiento:

- Evitar en listas largas con scroll
- Limitar a 2-3 elementos por pantalla
- Proporcionar fallback sin blur para dispositivos lentos
- Usar `ImageFilter.blur` con valores moderados (10-20)

---

## PROHIBICIONES ABSOLUTAS

### NUNCA Metodos que Devuelvan Widget

```dart
// PROHIBIDO
class MyPage extends StatelessWidget {
  Widget _buildGlassCard() { ... }
  Widget _buildHeader() { ... }
}

// CORRECTO
class GlassCard extends StatelessWidget { ... }
class GlassHeader extends StatelessWidget { ... }
```

### NUNCA Blur Excesivo

```dart
// PROHIBIDO - Blur muy alto, afecta rendimiento y legibilidad
BackdropFilter(
  filter: ImageFilter.blur(sigmaX: 50, sigmaY: 50),  // Demasiado
  child: ...
)

// CORRECTO - Blur sutil
BackdropFilter(
  filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),  // Optimo
  child: ...
)
```

### NUNCA Glass en TODO

```dart
// PROHIBIDO - Sobrecarga visual y de rendimiento
Column(
  children: [
    GlassContainer(child: AppBar(...)),        // NO en AppBar
    GlassContainer(child: ListView(...)),       // NO en listas
    GlassContainer(child: BottomNav(...)),      // NO en navegacion
    GlassContainer(child: everyElement),        // NO en todo
  ],
)

// CORRECTO - Solo en elementos flotantes/destacados
Stack(
  children: [
    backgroundImage,                            // Fondo con contenido
    GlassCard(child: floatingContent),         // Cards flotantes
    GlassBottomSheet(child: actions),          // Sheets
  ],
)
```

### NUNCA Texto sin Contraste Suficiente

```dart
// PROHIBIDO - Texto ilegible sobre glass
Container(
  color: Colors.white.withOpacity(0.1),
  child: Text(
    'Texto',
    style: TextStyle(color: Colors.white.withOpacity(0.5)),  // Ilegible
  ),
)

// CORRECTO - Texto con contraste
Container(
  color: Colors.white.withOpacity(0.15),
  child: Text(
    'Texto',
    style: TextStyle(
      color: Colors.white,
      fontWeight: FontWeight.w500,
      shadows: [
        Shadow(color: Colors.black26, blurRadius: 4),  // Sombra para contraste
      ],
    ),
  ),
)
```

### NUNCA Glass sin Fondo Interesante

```dart
// PROHIBIDO - Glass sobre fondo solido (sin sentido)
Container(
  color: Colors.grey,  // Fondo solido
  child: GlassCard(...),  // El blur no aporta nada
)

// CORRECTO - Glass sobre contenido visual
Stack(
  children: [
    Image.asset('background.jpg'),  // Imagen o gradiente
    GlassCard(...),                  // Ahora el blur tiene sentido
  ],
)
```

---

## Principios del Glassmorphism

### 1. Capas de Profundidad

```
┌─────────────────────────────────────────┐
│  Capa 3: Contenido (texto, iconos)      │
│  ┌───────────────────────────────────┐  │
│  │  Capa 2: Glass (blur + tint)      │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  Capa 1: Fondo (imagen,     │  │  │
│  │  │          gradiente, video)  │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 2. Componentes del Efecto Glass

```dart
// Los 4 elementos del glassmorphism:

// 1. BLUR - Desenfoque del fondo
BackdropFilter(
  filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
  child: ...
)

// 2. TINT - Color semitransparente
Container(
  color: Colors.white.withOpacity(0.15),  // Light mode
  // o
  color: Colors.black.withOpacity(0.25),  // Dark mode
)

// 3. BORDER - Borde sutil brillante
Border.all(
  color: Colors.white.withOpacity(0.2),
  width: 1.5,
)

// 4. SHADOW - Sombra suave para profundidad
BoxShadow(
  color: Colors.black.withOpacity(0.1),
  blurRadius: 20,
  spreadRadius: -5,
)
```

### 3. Jerarquia con Opacidad

```dart
// Elementos mas cercanos = mas opacos
// Elementos mas lejanos = mas transparentes

// Primer plano (modal, sheet)
color: Colors.white.withOpacity(0.25)

// Segundo plano (cards flotantes)
color: Colors.white.withOpacity(0.15)

// Tercer plano (elementos sutiles)
color: Colors.white.withOpacity(0.08)
```

---

## Tema Glassmorphism

### Configuracion Base

```dart
// lib/core/theme/glass_theme.dart

import 'dart:ui';
import 'package:flutter/material.dart';

class GlassTheme {
  // ═══════════════════════════════════════
  // BLUR VALUES
  // ═══════════════════════════════════════

  static const double blurLight = 8.0;
  static const double blurMedium = 12.0;
  static const double blurStrong = 20.0;

  // ═══════════════════════════════════════
  // LIGHT MODE
  // ═══════════════════════════════════════

  // Tints (color del cristal)
  static Color glassTintLight = Colors.white.withOpacity(0.15);
  static Color glassTintLightStrong = Colors.white.withOpacity(0.25);
  static Color glassTintLightSubtle = Colors.white.withOpacity(0.08);

  // Borders
  static Color glassBorderLight = Colors.white.withOpacity(0.2);

  // Text
  static const Color textPrimaryLight = Color(0xFF1A1A1A);
  static const Color textSecondaryLight = Color(0xFF4A4A4A);
  static const Color textOnGlassLight = Colors.white;

  // Background (debe tener contenido visual)
  static const List<Color> backgroundGradientLight = [
    Color(0xFF667eea),
    Color(0xFF764ba2),
  ];

  // ═══════════════════════════════════════
  // DARK MODE
  // ═══════════════════════════════════════

  // Tints
  static Color glassTintDark = Colors.white.withOpacity(0.08);
  static Color glassTintDarkStrong = Colors.white.withOpacity(0.15);
  static Color glassTintDarkSubtle = Colors.white.withOpacity(0.04);

  // Borders
  static Color glassBorderDark = Colors.white.withOpacity(0.1);

  // Text
  static const Color textPrimaryDark = Color(0xFFF5F5F5);
  static const Color textSecondaryDark = Color(0xFFB0B0B0);
  static const Color textOnGlassDark = Colors.white;

  // Background
  static const List<Color> backgroundGradientDark = [
    Color(0xFF1a1a2e),
    Color(0xFF16213e),
  ];

  // ═══════════════════════════════════════
  // ACCENT COLORS (para CTAs)
  // ═══════════════════════════════════════

  static const Color accent = Color(0xFF6C63FF);
  static const Color accentLight = Color(0xFF8B83FF);

  // ═══════════════════════════════════════
  // BORDER RADIUS
  // ═══════════════════════════════════════

  static const double radiusSmall = 12.0;
  static const double radiusMedium = 20.0;
  static const double radiusLarge = 28.0;
  static const double radiusXLarge = 36.0;
}
```

### ThemeData Completo

```dart
class GlassAppTheme {
  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: Colors.transparent,
      colorScheme: const ColorScheme.light(
        primary: GlassTheme.accent,
        onPrimary: Colors.white,
        surface: Colors.transparent,
        onSurface: GlassTheme.textPrimaryLight,
        onSurfaceVariant: GlassTheme.textSecondaryLight,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: GlassTheme.textPrimaryLight,
        elevation: 0,
      ),
      textTheme: const TextTheme(
        displayMedium: TextStyle(
          color: GlassTheme.textPrimaryLight,
          fontWeight: FontWeight.w600,
        ),
        headlineMedium: TextStyle(
          color: GlassTheme.textPrimaryLight,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: TextStyle(
          color: GlassTheme.textPrimaryLight,
        ),
        bodyMedium: TextStyle(
          color: GlassTheme.textSecondaryLight,
        ),
      ),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: Colors.transparent,
      colorScheme: const ColorScheme.dark(
        primary: GlassTheme.accentLight,
        onPrimary: Colors.white,
        surface: Colors.transparent,
        onSurface: GlassTheme.textPrimaryDark,
        onSurfaceVariant: GlassTheme.textSecondaryDark,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: GlassTheme.textPrimaryDark,
        elevation: 0,
      ),
    );
  }
}
```

---

## Componentes Glass

### Container Base

```dart
import 'dart:ui';
import 'package:flutter/material.dart';

class GlassContainer extends StatelessWidget {
  const GlassContainer({
    super.key,
    required this.child,
    this.width,
    this.height,
    this.padding = const EdgeInsets.all(20),
    this.borderRadius = 20.0,
    this.blur = 10.0,
    this.opacity = 0.15,
    this.borderOpacity = 0.2,
  });

  final Widget child;
  final double? width;
  final double? height;
  final EdgeInsets padding;
  final double borderRadius;
  final double blur;
  final double opacity;
  final double borderOpacity;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          width: width,
          height: height,
          padding: padding,
          decoration: BoxDecoration(
            color: (isDark ? Colors.white : Colors.white).withOpacity(
              isDark ? opacity * 0.6 : opacity,
            ),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: Colors.white.withOpacity(borderOpacity),
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.1),
                blurRadius: 20,
                spreadRadius: -5,
              ),
            ],
          ),
          child: child,
        ),
      ),
    );
  }
}
```

### Card Glass

```dart
class GlassCard extends StatelessWidget {
  const GlassCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(24),
    this.borderRadius = 24.0,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final card = GlassContainer(
      padding: padding,
      borderRadius: borderRadius,
      blur: GlassTheme.blurMedium,
      child: child,
    );

    if (onTap == null) return card;

    return GestureDetector(
      onTap: onTap,
      child: card,
    );
  }
}
```

### Boton Glass

```dart
class GlassButton extends StatefulWidget {
  const GlassButton({
    super.key,
    required this.child,
    required this.onPressed,
    this.width,
    this.height = 56,
    this.borderRadius = 16.0,
  });

  final Widget child;
  final VoidCallback? onPressed;
  final double? width;
  final double height;
  final double borderRadius;

  @override
  State<GlassButton> createState() => _GlassButtonState();
}

class _GlassButtonState extends State<GlassButton> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: widget.onPressed != null
          ? (_) => setState(() => _isPressed = true)
          : null,
      onTapUp: widget.onPressed != null
          ? (_) => setState(() => _isPressed = false)
          : null,
      onTapCancel: widget.onPressed != null
          ? () => setState(() => _isPressed = false)
          : null,
      onTap: widget.onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(widget.borderRadius),
          child: BackdropFilter(
            filter: ImageFilter.blur(
              sigmaX: _isPressed ? 15 : 10,
              sigmaY: _isPressed ? 15 : 10,
            ),
            child: Container(
              width: widget.width,
              height: widget.height,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(_isPressed ? 0.25 : 0.15),
                borderRadius: BorderRadius.circular(widget.borderRadius),
                border: Border.all(
                  color: Colors.white.withOpacity(_isPressed ? 0.4 : 0.2),
                  width: 1.5,
                ),
              ),
              child: Center(child: widget.child),
            ),
          ),
        ),
      ),
    );
  }
}
```

### Boton Filled Glass (CTA)

```dart
class GlassFilledButton extends StatefulWidget {
  const GlassFilledButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.width,
    this.height = 56,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final double? width;
  final double height;

  @override
  State<GlassFilledButton> createState() => _GlassFilledButtonState();
}

class _GlassFilledButtonState extends State<GlassFilledButton> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: widget.onPressed != null
          ? (_) => setState(() => _isPressed = true)
          : null,
      onTapUp: widget.onPressed != null
          ? (_) => setState(() => _isPressed = false)
          : null,
      onTapCancel: widget.onPressed != null
          ? () => setState(() => _isPressed = false)
          : null,
      onTap: widget.onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              GlassTheme.accent.withOpacity(_isPressed ? 0.9 : 1.0),
              GlassTheme.accentLight.withOpacity(_isPressed ? 0.9 : 1.0),
            ],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: GlassTheme.accent.withOpacity(0.4),
              blurRadius: _isPressed ? 8 : 16,
              offset: Offset(0, _isPressed ? 2 : 4),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.icon != null) ...[
              Icon(widget.icon, color: Colors.white, size: 20),
              const SizedBox(width: 8),
            ],
            Text(
              widget.label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### Input Glass

```dart
class GlassTextField extends StatelessWidget {
  const GlassTextField({
    super.key,
    this.controller,
    this.hint,
    this.onChanged,
    this.obscureText = false,
    this.prefixIcon,
  });

  final TextEditingController? controller;
  final String? hint;
  final ValueChanged<String>? onChanged;
  final bool obscureText;
  final IconData? prefixIcon;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: Colors.white.withOpacity(0.2),
              width: 1,
            ),
          ),
          child: TextField(
            controller: controller,
            onChanged: onChanged,
            obscureText: obscureText,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
            ),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(
                color: Colors.white.withOpacity(0.5),
              ),
              prefixIcon: prefixIcon != null
                  ? Icon(prefixIcon, color: Colors.white70)
                  : null,
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 18,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
```

### Bottom Sheet Glass

```dart
class GlassBottomSheet extends StatelessWidget {
  const GlassBottomSheet({
    super.key,
    required this.child,
    this.height,
  });

  final Widget child;
  final double? height;

  static Future<T?> show<T>({
    required BuildContext context,
    required Widget child,
    double? height,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => GlassBottomSheet(
        height: height,
        child: child,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(
        top: Radius.circular(28),
      ),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          height: height,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.15),
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(28),
            ),
            border: Border.all(
              color: Colors.white.withOpacity(0.2),
              width: 1.5,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Handle
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Flexible(child: child),
            ],
          ),
        ),
      ),
    );
  }
}
```

### Navigation Bar Glass

```dart
class GlassNavigationBar extends StatelessWidget {
  const GlassNavigationBar({
    super.key,
    required this.items,
    required this.currentIndex,
    required this.onTap,
  });

  final List<GlassNavItem> items;
  final int currentIndex;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
        child: Container(
          height: 80,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.1),
            border: Border(
              top: BorderSide(
                color: Colors.white.withOpacity(0.2),
                width: 1,
              ),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: List.generate(
              items.length,
              (index) => _GlassNavItemWidget(
                item: items[index],
                isSelected: index == currentIndex,
                onTap: () => onTap(index),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class GlassNavItem {
  const GlassNavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });

  final IconData icon;
  final IconData activeIcon;
  final String label;
}

class _GlassNavItemWidget extends StatelessWidget {
  const _GlassNavItemWidget({
    required this.item,
    required this.isSelected,
    required this.onTap,
  });

  final GlassNavItem item;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? Colors.white.withOpacity(0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? item.activeIcon : item.icon,
              color: Colors.white.withOpacity(isSelected ? 1.0 : 0.6),
              size: 24,
            ),
            const SizedBox(height: 4),
            Text(
              item.label,
              style: TextStyle(
                color: Colors.white.withOpacity(isSelected ? 1.0 : 0.6),
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### Chip Glass

```dart
class GlassChip extends StatelessWidget {
  const GlassChip({
    super.key,
    required this.label,
    this.isSelected = false,
    this.onTap,
    this.icon,
  });

  final String label;
  final bool isSelected;
  final VoidCallback? onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(isSelected ? 0.25 : 0.1),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: Colors.white.withOpacity(isSelected ? 0.4 : 0.2),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Icon(
                    icon,
                    size: 16,
                    color: Colors.white.withOpacity(isSelected ? 1 : 0.7),
                  ),
                  const SizedBox(width: 6),
                ],
                Text(
                  label,
                  style: TextStyle(
                    color: Colors.white.withOpacity(isSelected ? 1 : 0.8),
                    fontSize: 14,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

---

## Scaffold con Fondo

```dart
class GlassScaffold extends StatelessWidget {
  const GlassScaffold({
    super.key,
    required this.body,
    this.backgroundImage,
    this.backgroundGradient,
    this.appBar,
    this.bottomNavigationBar,
  });

  final Widget body;
  final ImageProvider? backgroundImage;
  final Gradient? backgroundGradient;
  final PreferredSizeWidget? appBar;
  final Widget? bottomNavigationBar;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final defaultGradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: isDark
          ? GlassTheme.backgroundGradientDark
          : GlassTheme.backgroundGradientLight,
    );

    return Scaffold(
      extendBody: true,
      extendBodyBehindAppBar: true,
      appBar: appBar,
      body: Container(
        decoration: BoxDecoration(
          gradient: backgroundGradient ?? defaultGradient,
          image: backgroundImage != null
              ? DecorationImage(
                  image: backgroundImage!,
                  fit: BoxFit.cover,
                )
              : null,
        ),
        child: SafeArea(
          bottom: false,
          child: body,
        ),
      ),
      bottomNavigationBar: bottomNavigationBar,
    );
  }
}
```

---

## Patron de Uso

### Ejemplo Completo

```dart
class GlassExamplePage extends StatefulWidget {
  const GlassExamplePage({super.key});

  @override
  State<GlassExamplePage> createState() => _GlassExamplePageState();
}

class _GlassExamplePageState extends State<GlassExamplePage> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return GlassScaffold(
      bottomNavigationBar: GlassNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: const [
          GlassNavItem(
            icon: Icons.home_outlined,
            activeIcon: Icons.home,
            label: 'Home',
          ),
          GlassNavItem(
            icon: Icons.search_outlined,
            activeIcon: Icons.search,
            label: 'Search',
          ),
          GlassNavItem(
            icon: Icons.person_outline,
            activeIcon: Icons.person,
            label: 'Profile',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 20),

            // Titulo
            const Text(
              'Welcome Back',
              style: TextStyle(
                color: Colors.white,
                fontSize: 32,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 8),

            Text(
              'Discover something new today',
              style: TextStyle(
                color: Colors.white.withOpacity(0.7),
                fontSize: 16,
              ),
            ),

            const SizedBox(height: 32),

            // Glass Cards
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Featured',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Explore the latest content and discover new experiences.',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.8),
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 20),

            // Chips
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                GlassChip(label: 'All', isSelected: true),
                GlassChip(label: 'Design'),
                GlassChip(label: 'Development'),
                GlassChip(label: 'Business'),
              ],
            ),

            const SizedBox(height: 32),

            // Buttons
            SizedBox(
              width: double.infinity,
              child: GlassFilledButton(
                label: 'Get Started',
                icon: Icons.arrow_forward,
                onPressed: () {},
              ),
            ),

            const SizedBox(height: 16),

            SizedBox(
              width: double.infinity,
              child: GlassButton(
                onPressed: () {},
                child: const Text(
                  'Learn More',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 100), // Space for bottom nav
          ],
        ),
      ),
    );
  }
}
```

---

## Optimizacion de Rendimiento

### Fallback sin Blur

```dart
class GlassContainerOptimized extends StatelessWidget {
  const GlassContainerOptimized({
    super.key,
    required this.child,
    this.enableBlur = true,
  });

  final Widget child;
  final bool enableBlur;

  @override
  Widget build(BuildContext context) {
    // Detectar dispositivos de bajo rendimiento
    final bool shouldBlur = enableBlur && !_isLowEndDevice();

    if (!shouldBlur) {
      // Fallback sin blur
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.4),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: Colors.white.withOpacity(0.1),
          ),
        ),
        child: child,
      );
    }

    return GlassContainer(child: child);
  }

  bool _isLowEndDevice() {
    // Implementar deteccion basada en:
    // - RAM disponible
    // - Modelo de dispositivo
    // - Fps del ultimo frame
    return false;
  }
}
```

### Limitar Blur en Listas

```dart
// NUNCA hacer esto
ListView.builder(
  itemBuilder: (context, index) => GlassCard(...),  // Muy costoso
)

// CORRECTO - Solo el contenedor es glass
Stack(
  children: [
    backgroundImage,
    GlassContainer(
      child: ListView.builder(
        itemBuilder: (context, index) => ListTile(...),  // Items normales
      ),
    ),
  ],
)
```

---

## Cuando USAR y NO USAR Glassmorphism

### Usar Glassmorphism

```dart
// Cards flotantes sobre contenido visual
Stack(
  children: [
    heroImage,
    Positioned(
      bottom: 20,
      child: GlassCard(child: infoOverlay),
    ),
  ],
)

// Modales y sheets
GlassBottomSheet(child: actions)

// Navigation bars flotantes
GlassNavigationBar(...)

// Widgets de estado (musica, clima)
GlassContainer(child: nowPlayingWidget)

// Landing pages con fondos visuales
GlassScaffold(
  backgroundImage: heroBackground,
  body: content,
)
```

### NO Usar Glassmorphism

```dart
// NO en listas largas
ListView.builder(
  itemBuilder: (context, index) => GlassCard(...),  // Rendimiento terrible
)

// NO en apps de lectura prolongada
GlassContainer(
  child: Text(longArticleText),  // Dificil de leer
)

// NO sobre fondos solidos (sin sentido)
Container(
  color: Colors.blue,  // Solido
  child: GlassCard(...),  // El blur no aporta nada
)

// NO en apps empresariales tradicionales
// Usar Material 3 o Cupertino en su lugar

// NO en cada elemento de la UI
// Reservar para elementos destacados
```

---

## Accesibilidad

### Contraste de Texto

```dart
// OBLIGATORIO: Asegurar legibilidad

// Usar texto con peso suficiente
const TextStyle(
  color: Colors.white,
  fontWeight: FontWeight.w500,  // Al menos medium
)

// Anadir sombra para contraste
Text(
  'Important Text',
  style: TextStyle(
    color: Colors.white,
    shadows: [
      Shadow(
        color: Colors.black.withOpacity(0.3),
        blurRadius: 4,
      ),
    ],
  ),
)

// Aumentar opacidad del tint si es necesario
Container(
  color: Colors.black.withOpacity(0.3),  // Mas opaco para mejor contraste
  child: text,
)
```

### Indicadores de Estado

```dart
// No depender SOLO de transparencia para estados
// Anadir cambios de borde, iconos, o texto

GlassChip(
  label: 'Selected',
  isSelected: true,
  // Cambia: opacidad + borde + fontWeight
)
```

---

## Checklist de Revision Glassmorphism

```
Fundamentos
[ ] Fondo con contenido visual (no solido)?
[ ] Blur moderado (8-20 sigma)?
[ ] Tint semitransparente aplicado?
[ ] Borde sutil para definicion?

Rendimiento
[ ] Maximo 2-3 elementos glass por pantalla?
[ ] NO glass en listas con scroll?
[ ] Fallback para dispositivos lentos?
[ ] ClipRRect envuelve BackdropFilter?

Legibilidad
[ ] Texto con peso >= 500?
[ ] Sombra en texto si es necesario?
[ ] Contraste suficiente verificado?

Uso Apropiado
[ ] Solo en elementos flotantes/destacados?
[ ] NO en toda la UI?
[ ] Fondo justifica el efecto glass?

Codigo
[ ] Widgets como clases separadas?
[ ] Sin state management especifico?
[ ] Callbacks para interacciones?
```

---

## Output Esperado

Cuando disenes con este agente:

1. **Analisis de viabilidad** - Es apropiado glass aqui? Hay fondo visual?
2. **Decisiones de blur/opacidad** - Valores optimos para el caso
3. **Codigo Flutter** - Componentes glass completos
4. **Optimizaciones** - Fallbacks y consideraciones de rendimiento

---

## Referencias

- [Glassmorphism CSS Generator](https://glassmorphism.com/)
- [Glassmorphism in User Interfaces](https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9)
- [Apple Human Interface - Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- [Flutter BackdropFilter](https://api.flutter.dev/flutter/widgets/BackdropFilter-class.html)
