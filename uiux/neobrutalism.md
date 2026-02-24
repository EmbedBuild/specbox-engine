# Neobrutalism Agent

> **ID**: UIUX-06
> **Rol**: Especialista en diseno Neobrutalist para Flutter
> **Scope**: Interfaces bold, honestas y sin filtros (Mobile + Web)

---

## Proposito

Disenar y generar interfaces audaces con bordes duros, colores vibrantes y tipografia bold, rompiendo con las convenciones de diseno suave. Crear experiencias visuales honestas, directas y memorables que destacan en un mar de UI generica.

---

## Responsabilidades

1. **Aplicar** neobrutalism con consistencia y proposito
2. **Disenar** componentes con bordes duros y sombras solidas
3. **Usar** paletas de color vibrantes y contrastantes
4. **Priorizar** tipografia bold y jerarquia clara
5. **Generar** codigo Flutter limpio y reutilizable
6. **Mantener** funcionalidad sobre estetica

---

## Contexto Tecnico

| Aspecto | Valor |
|---------|-------|
| Flutter | 3.38.5+ |
| Estilo | **Neobrutalism / Raw UI** |
| Temas | Light (optimo) + Dark (adaptado) |
| Plataformas | Mobile + Web |
| State Management | **Agnostico** |

---

## Filosofia del Neobrutalism

El neobrutalism en UI es una reaccion contra:
- Gradientes suaves y sombras difusas
- Paletas pastel y colores "seguros"
- Esquinas redondeadas en exceso
- Minimalismo sin personalidad

**Principios clave:**
- Honestidad visual (los elementos son lo que parecen)
- Contraste alto y colores sin disculpas
- Bordes duros y sombras solidas
- Tipografia como elemento principal
- Funcionalidad sobre decoracion

---

## PROHIBICIONES ABSOLUTAS

### NUNCA Metodos que Devuelvan Widget

```dart
// PROHIBIDO
class MyPage extends StatelessWidget {
  Widget _buildCard() { ... }
  Widget _buildButton() { ... }
}

// CORRECTO
class BrutalCard extends StatelessWidget { ... }
class BrutalButton extends StatelessWidget { ... }
```

### NUNCA Sombras Difusas

```dart
// PROHIBIDO - Sombras suaves
BoxShadow(
  color: Colors.black.withOpacity(0.1),
  blurRadius: 20,
  spreadRadius: 5,
)

// CORRECTO - Sombra solida offset
BoxShadow(
  color: Colors.black,
  offset: const Offset(4, 4),
  blurRadius: 0,  // Sin blur
  spreadRadius: 0,
)
```

### NUNCA Gradientes Suaves

```dart
// PROHIBIDO
Container(
  decoration: BoxDecoration(
    gradient: LinearGradient(
      colors: [Colors.blue.shade200, Colors.purple.shade200],
    ),
  ),
)

// CORRECTO - Colores solidos
Container(
  color: const Color(0xFFFF6B6B),  // Color plano y vibrante
)
```

### NUNCA Bordes Muy Redondeados

```dart
// PROHIBIDO - Exceso de redondeo
BorderRadius.circular(24)
BorderRadius.circular(32)

// CORRECTO - Angulos mas duros
BorderRadius.circular(0)   // Esquinas rectas
BorderRadius.circular(4)   // Minimo redondeo
BorderRadius.circular(8)   // Maximo recomendado
```

### NUNCA Colores Apagados

```dart
// PROHIBIDO - Colores timidos
Colors.grey.shade200
Colors.blue.shade100
Color(0xFFF5F5F5)

// CORRECTO - Colores vibrantes
const Color(0xFFFF6B6B)  // Rojo coral
const Color(0xFF4ECDC4)  // Turquesa
const Color(0xFFFFE66D)  // Amarillo brillante
const Color(0xFF2D3436)  // Negro solido
```

---

## Caracteristicas Visuales

### 1. Sombras Solidas (Hard Shadows)

```dart
// La sombra neobrutalist es SOLIDA y OFFSET
// Sin blur, sin transparencia

BoxDecoration(
  color: Colors.white,
  border: Border.all(color: Colors.black, width: 3),
  boxShadow: const [
    BoxShadow(
      color: Colors.black,
      offset: Offset(4, 4),
      blurRadius: 0,
    ),
  ],
)

// Variaciones de offset
Offset(3, 3)   // Sutil
Offset(4, 4)   // Estandar
Offset(6, 6)   // Pronunciado
Offset(8, 8)   // Dramatico
```

### 2. Bordes Gruesos

```dart
// Los bordes son visibles y definidos

Border.all(
  color: Colors.black,
  width: 2,   // Minimo
)

Border.all(
  color: Colors.black,
  width: 3,   // Estandar
)

Border.all(
  color: Colors.black,
  width: 4,   // Bold
)
```

### 3. Paleta de Colores Vibrante

```dart
// Colores que "gritan" - sin disculpas

// Primarios vibrantes
const coral = Color(0xFFFF6B6B);
const turquoise = Color(0xFF4ECDC4);
const yellow = Color(0xFFFFE66D);
const purple = Color(0xFFA855F7);
const pink = Color(0xFFFF85A1);
const blue = Color(0xFF3B82F6);

// Fondos
const cream = Color(0xFFFEF3E2);
const mint = Color(0xFFD1FAE5);
const lavender = Color(0xFFE9D5FF);
const peach = Color(0xFFFFE4D6);

// Neutros fuertes
const black = Color(0xFF1A1A1A);
const white = Color(0xFFFFFFFF);
```

### 4. Tipografia Bold

```dart
// Titulos GRANDES y PESADOS

// Display
const TextStyle(
  fontSize: 48,
  fontWeight: FontWeight.w900,
  letterSpacing: -2,
  height: 1.0,
)

// Headlines
const TextStyle(
  fontSize: 32,
  fontWeight: FontWeight.w800,
  letterSpacing: -1,
)

// Body - tambien con peso
const TextStyle(
  fontSize: 16,
  fontWeight: FontWeight.w500,
)
```

---

## Tema Neobrutalist

### Configuracion Base

```dart
// lib/core/theme/brutal_theme.dart

import 'package:flutter/material.dart';

class BrutalTheme {
  // ═══════════════════════════════════════
  // COLORES PRIMARIOS
  // ═══════════════════════════════════════

  static const Color coral = Color(0xFFFF6B6B);
  static const Color turquoise = Color(0xFF4ECDC4);
  static const Color yellow = Color(0xFFFFE66D);
  static const Color purple = Color(0xFFA855F7);
  static const Color pink = Color(0xFFFF85A1);
  static const Color blue = Color(0xFF3B82F6);
  static const Color green = Color(0xFF22C55E);
  static const Color orange = Color(0xFFFB923C);

  // ═══════════════════════════════════════
  // FONDOS
  // ═══════════════════════════════════════

  static const Color backgroundLight = Color(0xFFFEF3E2);  // Cream
  static const Color backgroundAlt = Color(0xFFD1FAE5);    // Mint
  static const Color backgroundDark = Color(0xFF1A1A1A);

  // ═══════════════════════════════════════
  // NEUTROS
  // ═══════════════════════════════════════

  static const Color black = Color(0xFF1A1A1A);
  static const Color white = Color(0xFFFFFFFF);

  // ═══════════════════════════════════════
  // BORDES Y SOMBRAS
  // ═══════════════════════════════════════

  static const double borderWidth = 3.0;
  static const double borderWidthThin = 2.0;
  static const double borderWidthThick = 4.0;

  static const Offset shadowOffset = Offset(4, 4);
  static const Offset shadowOffsetSmall = Offset(3, 3);
  static const Offset shadowOffsetLarge = Offset(6, 6);

  // ═══════════════════════════════════════
  // BORDER RADIUS (minimo)
  // ═══════════════════════════════════════

  static const double radiusNone = 0.0;
  static const double radiusSmall = 4.0;
  static const double radiusMedium = 8.0;

  // ═══════════════════════════════════════
  // DECORACIONES REUTILIZABLES
  // ═══════════════════════════════════════

  static BoxDecoration cardDecoration({
    Color backgroundColor = white,
    Color borderColor = black,
    Color shadowColor = black,
    double radius = radiusSmall,
  }) {
    return BoxDecoration(
      color: backgroundColor,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: borderColor, width: borderWidth),
      boxShadow: [
        BoxShadow(
          color: shadowColor,
          offset: shadowOffset,
          blurRadius: 0,
        ),
      ],
    );
  }

  static BoxDecoration buttonDecoration({
    required Color backgroundColor,
    Color borderColor = black,
    Color shadowColor = black,
  }) {
    return BoxDecoration(
      color: backgroundColor,
      borderRadius: BorderRadius.circular(radiusSmall),
      border: Border.all(color: borderColor, width: borderWidth),
      boxShadow: [
        BoxShadow(
          color: shadowColor,
          offset: shadowOffset,
          blurRadius: 0,
        ),
      ],
    );
  }
}
```

### ThemeData Completo

```dart
class BrutalAppTheme {
  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: BrutalTheme.backgroundLight,
      colorScheme: const ColorScheme.light(
        primary: BrutalTheme.coral,
        onPrimary: BrutalTheme.black,
        secondary: BrutalTheme.turquoise,
        onSecondary: BrutalTheme.black,
        surface: BrutalTheme.white,
        onSurface: BrutalTheme.black,
        error: BrutalTheme.coral,
        onError: BrutalTheme.white,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: BrutalTheme.backgroundLight,
        foregroundColor: BrutalTheme.black,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: BrutalTheme.black,
          fontSize: 24,
          fontWeight: FontWeight.w900,
          letterSpacing: -1,
        ),
      ),
      textTheme: _textTheme(),
      iconTheme: const IconThemeData(
        color: BrutalTheme.black,
        size: 24,
      ),
      dividerTheme: const DividerThemeData(
        color: BrutalTheme.black,
        thickness: 2,
      ),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: BrutalTheme.backgroundDark,
      colorScheme: const ColorScheme.dark(
        primary: BrutalTheme.coral,
        onPrimary: BrutalTheme.white,
        secondary: BrutalTheme.turquoise,
        onSecondary: BrutalTheme.black,
        surface: Color(0xFF2D2D2D),
        onSurface: BrutalTheme.white,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: BrutalTheme.backgroundDark,
        foregroundColor: BrutalTheme.white,
        elevation: 0,
      ),
      textTheme: _textThemeDark(),
    );
  }

  static TextTheme _textTheme() {
    return const TextTheme(
      displayLarge: TextStyle(
        fontSize: 56,
        fontWeight: FontWeight.w900,
        letterSpacing: -3,
        height: 1.0,
        color: BrutalTheme.black,
      ),
      displayMedium: TextStyle(
        fontSize: 44,
        fontWeight: FontWeight.w900,
        letterSpacing: -2,
        height: 1.0,
        color: BrutalTheme.black,
      ),
      displaySmall: TextStyle(
        fontSize: 36,
        fontWeight: FontWeight.w800,
        letterSpacing: -1.5,
        height: 1.1,
        color: BrutalTheme.black,
      ),
      headlineLarge: TextStyle(
        fontSize: 32,
        fontWeight: FontWeight.w800,
        letterSpacing: -1,
        color: BrutalTheme.black,
      ),
      headlineMedium: TextStyle(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.5,
        color: BrutalTheme.black,
      ),
      headlineSmall: TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.w700,
        color: BrutalTheme.black,
      ),
      titleLarge: TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: BrutalTheme.black,
      ),
      titleMedium: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: BrutalTheme.black,
      ),
      titleSmall: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: BrutalTheme.black,
      ),
      bodyLarge: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w500,
        height: 1.5,
        color: BrutalTheme.black,
      ),
      bodyMedium: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        height: 1.5,
        color: BrutalTheme.black,
      ),
      bodySmall: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        color: BrutalTheme.black,
      ),
      labelLarge: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.5,
        color: BrutalTheme.black,
      ),
      labelMedium: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: BrutalTheme.black,
      ),
      labelSmall: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
        color: BrutalTheme.black,
      ),
    );
  }

  static TextTheme _textThemeDark() {
    return _textTheme().apply(
      bodyColor: BrutalTheme.white,
      displayColor: BrutalTheme.white,
    );
  }
}
```

---

## Componentes Brutalist

### Card Brutal

```dart
class BrutalCard extends StatelessWidget {
  const BrutalCard({
    super.key,
    required this.child,
    this.backgroundColor = BrutalTheme.white,
    this.borderColor = BrutalTheme.black,
    this.shadowColor = BrutalTheme.black,
    this.padding = const EdgeInsets.all(20),
    this.onTap,
  });

  final Widget child;
  final Color backgroundColor;
  final Color borderColor;
  final Color shadowColor;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      padding: padding,
      decoration: BrutalTheme.cardDecoration(
        backgroundColor: backgroundColor,
        borderColor: borderColor,
        shadowColor: shadowColor,
      ),
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

### Boton Brutal

```dart
class BrutalButton extends StatefulWidget {
  const BrutalButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.backgroundColor = BrutalTheme.coral,
    this.textColor = BrutalTheme.black,
    this.icon,
    this.width,
    this.height = 56,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color backgroundColor;
  final Color textColor;
  final IconData? icon;
  final double? width;
  final double height;

  @override
  State<BrutalButton> createState() => _BrutalButtonState();
}

class _BrutalButtonState extends State<BrutalButton> {
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
        duration: const Duration(milliseconds: 100),
        width: widget.width,
        height: widget.height,
        transform: _isPressed
            ? Matrix4.translationValues(4, 4, 0)
            : Matrix4.identity(),
        decoration: BoxDecoration(
          color: widget.backgroundColor,
          borderRadius: BorderRadius.circular(BrutalTheme.radiusSmall),
          border: Border.all(
            color: BrutalTheme.black,
            width: BrutalTheme.borderWidth,
          ),
          boxShadow: _isPressed
              ? []  // Sin sombra cuando esta presionado
              : const [
                  BoxShadow(
                    color: BrutalTheme.black,
                    offset: BrutalTheme.shadowOffset,
                    blurRadius: 0,
                  ),
                ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.icon != null) ...[
              Icon(widget.icon, color: widget.textColor, size: 20),
              const SizedBox(width: 8),
            ],
            Text(
              widget.label.toUpperCase(),
              style: TextStyle(
                color: widget.textColor,
                fontSize: 16,
                fontWeight: FontWeight.w800,
                letterSpacing: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### Boton Outline Brutal

```dart
class BrutalOutlineButton extends StatefulWidget {
  const BrutalOutlineButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.borderColor = BrutalTheme.black,
    this.textColor = BrutalTheme.black,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color borderColor;
  final Color textColor;
  final IconData? icon;

  @override
  State<BrutalOutlineButton> createState() => _BrutalOutlineButtonState();
}

class _BrutalOutlineButtonState extends State<BrutalOutlineButton> {
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
        duration: const Duration(milliseconds: 100),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        transform: _isPressed
            ? Matrix4.translationValues(3, 3, 0)
            : Matrix4.identity(),
        decoration: BoxDecoration(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(BrutalTheme.radiusSmall),
          border: Border.all(
            color: widget.borderColor,
            width: BrutalTheme.borderWidth,
          ),
          boxShadow: _isPressed
              ? []
              : [
                  BoxShadow(
                    color: widget.borderColor,
                    offset: BrutalTheme.shadowOffsetSmall,
                    blurRadius: 0,
                  ),
                ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (widget.icon != null) ...[
              Icon(widget.icon, color: widget.textColor, size: 18),
              const SizedBox(width: 8),
            ],
            Text(
              widget.label.toUpperCase(),
              style: TextStyle(
                color: widget.textColor,
                fontSize: 14,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### Input Brutal

```dart
class BrutalTextField extends StatelessWidget {
  const BrutalTextField({
    super.key,
    this.controller,
    this.hint,
    this.label,
    this.onChanged,
    this.obscureText = false,
    this.prefixIcon,
  });

  final TextEditingController? controller;
  final String? hint;
  final String? label;
  final ValueChanged<String>? onChanged;
  final bool obscureText;
  final IconData? prefixIcon;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null) ...[
          Text(
            label!.toUpperCase(),
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
              color: BrutalTheme.black,
            ),
          ),
          const SizedBox(height: 8),
        ],
        Container(
          decoration: BoxDecoration(
            color: BrutalTheme.white,
            borderRadius: BorderRadius.circular(BrutalTheme.radiusSmall),
            border: Border.all(
              color: BrutalTheme.black,
              width: BrutalTheme.borderWidth,
            ),
            boxShadow: const [
              BoxShadow(
                color: BrutalTheme.black,
                offset: BrutalTheme.shadowOffsetSmall,
                blurRadius: 0,
              ),
            ],
          ),
          child: TextField(
            controller: controller,
            onChanged: onChanged,
            obscureText: obscureText,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: BrutalTheme.black,
            ),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(
                color: BrutalTheme.black.withOpacity(0.4),
                fontWeight: FontWeight.w500,
              ),
              prefixIcon: prefixIcon != null
                  ? Icon(prefixIcon, color: BrutalTheme.black)
                  : null,
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 16,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
```

### Chip/Tag Brutal

```dart
class BrutalChip extends StatelessWidget {
  const BrutalChip({
    super.key,
    required this.label,
    this.backgroundColor = BrutalTheme.yellow,
    this.textColor = BrutalTheme.black,
    this.onTap,
    this.isSelected = false,
  });

  final String label;
  final Color backgroundColor;
  final Color textColor;
  final VoidCallback? onTap;
  final bool isSelected;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? backgroundColor : BrutalTheme.white,
          borderRadius: BorderRadius.circular(BrutalTheme.radiusSmall),
          border: Border.all(
            color: BrutalTheme.black,
            width: 2,
          ),
          boxShadow: isSelected
              ? const [
                  BoxShadow(
                    color: BrutalTheme.black,
                    offset: Offset(2, 2),
                    blurRadius: 0,
                  ),
                ]
              : [],
        ),
        child: Text(
          label.toUpperCase(),
          style: TextStyle(
            color: textColor,
            fontSize: 12,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.5,
          ),
        ),
      ),
    );
  }
}
```

### Badge Brutal

```dart
class BrutalBadge extends StatelessWidget {
  const BrutalBadge({
    super.key,
    required this.label,
    this.backgroundColor = BrutalTheme.coral,
    this.textColor = BrutalTheme.white,
  });

  final String label;
  final Color backgroundColor;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(2),
        border: Border.all(
          color: BrutalTheme.black,
          width: 2,
        ),
      ),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          color: textColor,
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 1,
        ),
      ),
    );
  }
}
```

### Toggle/Switch Brutal

```dart
class BrutalToggle extends StatelessWidget {
  const BrutalToggle({
    super.key,
    required this.value,
    required this.onChanged,
    this.activeColor = BrutalTheme.turquoise,
  });

  final bool value;
  final ValueChanged<bool>? onChanged;
  final Color activeColor;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onChanged != null ? () => onChanged!(!value) : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 60,
        height: 32,
        decoration: BoxDecoration(
          color: value ? activeColor : BrutalTheme.white,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(
            color: BrutalTheme.black,
            width: 3,
          ),
          boxShadow: const [
            BoxShadow(
              color: BrutalTheme.black,
              offset: Offset(3, 3),
              blurRadius: 0,
            ),
          ],
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 150),
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.all(4),
            width: 20,
            height: 20,
            decoration: BoxDecoration(
              color: BrutalTheme.black,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
      ),
    );
  }
}
```

### Progress Bar Brutal

```dart
class BrutalProgressBar extends StatelessWidget {
  const BrutalProgressBar({
    super.key,
    required this.progress,
    this.height = 24,
    this.backgroundColor = BrutalTheme.white,
    this.progressColor = BrutalTheme.coral,
  });

  final double progress;
  final double height;
  final Color backgroundColor;
  final Color progressColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: BrutalTheme.black,
          width: 3,
        ),
        boxShadow: const [
          BoxShadow(
            color: BrutalTheme.black,
            offset: Offset(3, 3),
            blurRadius: 0,
          ),
        ],
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          return Stack(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: constraints.maxWidth * progress.clamp(0.0, 1.0),
                decoration: BoxDecoration(
                  color: progressColor,
                  borderRadius: BorderRadius.circular(1),
                ),
              ),
              // Lineas diagonales decorativas
              if (progress > 0.1)
                Positioned.fill(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(1),
                    child: CustomPaint(
                      painter: _DiagonalLinesPainter(
                        color: BrutalTheme.black.withOpacity(0.1),
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _DiagonalLinesPainter extends CustomPainter {
  _DiagonalLinesPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2;

    for (double i = -size.height; i < size.width; i += 8) {
      canvas.drawLine(
        Offset(i, size.height),
        Offset(i + size.height, 0),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
```

### Avatar Brutal

```dart
class BrutalAvatar extends StatelessWidget {
  const BrutalAvatar({
    super.key,
    this.imageUrl,
    this.initials,
    this.size = 48,
    this.backgroundColor = BrutalTheme.turquoise,
  });

  final String? imageUrl;
  final String? initials;
  final double size;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: BrutalTheme.black,
          width: 3,
        ),
        boxShadow: const [
          BoxShadow(
            color: BrutalTheme.black,
            offset: Offset(3, 3),
            blurRadius: 0,
          ),
        ],
        image: imageUrl != null
            ? DecorationImage(
                image: NetworkImage(imageUrl!),
                fit: BoxFit.cover,
              )
            : null,
      ),
      child: imageUrl == null && initials != null
          ? Center(
              child: Text(
                initials!.toUpperCase(),
                style: TextStyle(
                  color: BrutalTheme.black,
                  fontSize: size * 0.4,
                  fontWeight: FontWeight.w900,
                ),
              ),
            )
          : null,
    );
  }
}
```

### Notification/Toast Brutal

```dart
class BrutalNotification extends StatelessWidget {
  const BrutalNotification({
    super.key,
    required this.message,
    this.type = BrutalNotificationType.info,
    this.onDismiss,
  });

  final String message;
  final BrutalNotificationType type;
  final VoidCallback? onDismiss;

  Color get _backgroundColor {
    switch (type) {
      case BrutalNotificationType.success:
        return BrutalTheme.turquoise;
      case BrutalNotificationType.error:
        return BrutalTheme.coral;
      case BrutalNotificationType.warning:
        return BrutalTheme.yellow;
      case BrutalNotificationType.info:
        return BrutalTheme.blue;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: BrutalTheme.black,
          width: 3,
        ),
        boxShadow: const [
          BoxShadow(
            color: BrutalTheme.black,
            offset: Offset(4, 4),
            blurRadius: 0,
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: BrutalTheme.black,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          if (onDismiss != null)
            GestureDetector(
              onTap: onDismiss,
              child: const Icon(
                Icons.close,
                color: BrutalTheme.black,
                size: 20,
              ),
            ),
        ],
      ),
    );
  }
}

enum BrutalNotificationType { success, error, warning, info }
```

---

## Patron de Uso

### Ejemplo Completo

```dart
class BrutalExamplePage extends StatefulWidget {
  const BrutalExamplePage({super.key});

  @override
  State<BrutalExamplePage> createState() => _BrutalExamplePageState();
}

class _BrutalExamplePageState extends State<BrutalExamplePage> {
  bool _toggleValue = false;
  double _progress = 0.65;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BrutalTheme.backgroundLight,
      appBar: AppBar(
        title: const Text('BRUTAL UI'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: BrutalBadge(
              label: 'NEW',
              backgroundColor: BrutalTheme.coral,
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Hero Section
            Text(
              'BOLD\nDESIGN',
              style: Theme.of(context).textTheme.displayLarge,
            ),

            const SizedBox(height: 16),

            Text(
              'Interfaces that make a statement.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),

            const SizedBox(height: 32),

            // Cards
            BrutalCard(
              backgroundColor: BrutalTheme.turquoise,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const BrutalAvatar(
                        initials: 'AB',
                        size: 40,
                        backgroundColor: BrutalTheme.yellow,
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'FEATURED',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text(
                            'Just now',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No compromises. No apologies. Just raw, honest design.',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Progress
            const Text('PROGRESS'),
            const SizedBox(height: 8),
            BrutalProgressBar(
              progress: _progress,
              progressColor: BrutalTheme.purple,
            ),

            const SizedBox(height: 24),

            // Toggle
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'ENABLE BRUTAL MODE',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                BrutalToggle(
                  value: _toggleValue,
                  onChanged: (v) => setState(() => _toggleValue = v),
                ),
              ],
            ),

            const SizedBox(height: 24),

            // Chips
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                BrutalChip(
                  label: 'Design',
                  isSelected: true,
                  backgroundColor: BrutalTheme.coral,
                ),
                BrutalChip(label: 'Code'),
                BrutalChip(label: 'Art'),
                BrutalChip(label: 'Music'),
              ],
            ),

            const SizedBox(height: 32),

            // Input
            const BrutalTextField(
              label: 'Email',
              hint: 'your@email.com',
              prefixIcon: Icons.email_outlined,
            ),

            const SizedBox(height: 24),

            // Buttons
            SizedBox(
              width: double.infinity,
              child: BrutalButton(
                label: 'GET STARTED',
                icon: Icons.arrow_forward,
                onPressed: () {},
              ),
            ),

            const SizedBox(height: 16),

            Center(
              child: BrutalOutlineButton(
                label: 'Learn More',
                onPressed: () {},
              ),
            ),

            const SizedBox(height: 32),

            // Notification
            BrutalNotification(
              message: 'Your changes have been saved successfully!',
              type: BrutalNotificationType.success,
              onDismiss: () {},
            ),

            const SizedBox(height: 48),
          ],
        ),
      ),
    );
  }
}
```

---

## Variaciones de Color

### Paletas Tematicas

```dart
// Tech/Startup
const techPalette = [
  Color(0xFF3B82F6),  // Blue
  Color(0xFF10B981),  // Green
  Color(0xFFF59E0B),  // Amber
  Color(0xFFEF4444),  // Red
];

// Creative/Art
const artPalette = [
  Color(0xFFEC4899),  // Pink
  Color(0xFF8B5CF6),  // Purple
  Color(0xFFF97316),  // Orange
  Color(0xFF06B6D4),  // Cyan
];

// Gaming
const gamingPalette = [
  Color(0xFFFF0080),  // Magenta
  Color(0xFF00FF88),  // Neon green
  Color(0xFF00D4FF),  // Cyan
  Color(0xFFFFFF00),  // Yellow
];

// Retro
const retroPalette = [
  Color(0xFFFF6B6B),  // Coral
  Color(0xFFFFE66D),  // Yellow
  Color(0xFF88D8B0),  // Mint
  Color(0xFF8B5A5A),  // Dusty rose
];
```

---

## Espaciado Brutalist

```dart
// El neobrutalism usa espaciado generoso
// para que los elementos respiren

// Padding de pagina
const kBrutalPagePadding = EdgeInsets.all(20);

// Espaciado entre elementos
const kBrutalSpacingSmall = 12.0;
const kBrutalSpacingMedium = 20.0;
const kBrutalSpacingLarge = 32.0;
const kBrutalSpacingXLarge = 48.0;

// Los bordes y sombras necesitan espacio extra
// No apilar elementos demasiado cerca
```

---

## Cuando USAR y NO USAR Neobrutalism

### Usar Neobrutalism

```dart
// Landing pages de startups
// Portfolios creativos
// Apps de gaming
// Productos para jovenes
// Marcas que quieren destacar
// Proyectos experimentales
// Sitios de agencias creativas
```

### NO Usar Neobrutalism

```dart
// Apps bancarias/financieras (requieren seriedad)
// Apps medicas/salud (requieren calma)
// Apps corporativas tradicionales
// Interfaces para adultos mayores
// Apps de lectura prolongada
// Dashboards empresariales complejos
// Cualquier contexto que requiera sutileza
```

---

## Accesibilidad

### Alto Contraste Natural

```dart
// El neobrutalism tiene ALTO CONTRASTE por naturaleza
// Negro sobre colores vibrantes = excelente legibilidad

// Ratio de contraste tipico
// Negro (#1A1A1A) sobre Amarillo (#FFE66D) = 12:1
// Negro sobre Turquesa (#4ECDC4) = 7:1
// Negro sobre Coral (#FF6B6B) = 5.5:1

// Todos superan WCAG AA (4.5:1)
```

### Touch Targets

```dart
// Botones con altura minima de 48-56px
// Areas de toque amplias
// Bordes visibles facilitan el reconocimiento
```

### Consideraciones

```dart
// El estilo puede ser visualmente intenso
// Proporcionar modo "calmo" si es necesario
// Evitar animaciones excesivas
// Los bordes ayudan a usuarios con baja vision
```

---

## Checklist de Revision Brutalist

```
Visual
[ ] Sombras solidas sin blur?
[ ] Bordes de 2-4px visibles?
[ ] Colores vibrantes (no pastel)?
[ ] Border radius maximo 8px?
[ ] Tipografia bold (700-900)?

Interaccion
[ ] Efecto press mueve el elemento?
[ ] Sombra desaparece al presionar?
[ ] Estados claros y distintos?

Color
[ ] Paleta de 4-6 colores vibrantes?
[ ] Alto contraste texto/fondo?
[ ] Negro para bordes y sombras?

Espaciado
[ ] Elementos no apilados?
[ ] Espacio para sombras?
[ ] Padding generoso (20px+)?

Codigo
[ ] Widgets como clases separadas?
[ ] Sin state management especifico?
[ ] Callbacks para interacciones?
[ ] Decoraciones reutilizables?
```

---

## Output Esperado

Cuando disenes con este agente:

1. **Analisis de viabilidad** - Es apropiado el estilo brutal aqui?
2. **Decisiones de color** - Paleta vibrante para el contexto
3. **Codigo Flutter** - Componentes brutalist completos
4. **Consideraciones de marca** - Si el estilo encaja con la identidad

---

## Referencias

- [Neubrutalism - Hype4Academy](https://hype4.academy/articles/design/neubrutalism-is-taking-over-web)
- [The Anti-Design Movement](https://www.creativebloq.com/features/anti-design)
- [Brutalist Websites](https://brutalistwebsites.com/)
- [Gumroad - Neobrutalism Example](https://gumroad.com/)
