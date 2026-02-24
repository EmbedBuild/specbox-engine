---
name: ui-adapter
description: >
  Scan project widget/component structure and generate UI mapping file.
  Use when the user says "scan UI", "map components", "adapt UI",
  "detect widgets", or needs to understand the project's UI inventory
  before planning a feature.
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash(find *), Bash(wc *)
---

# Comando: /adapt-ui

Genera el archivo `ui-adapter.md` para un proyecto escaneando su estructura de widgets existentes.
Opcionalmente normaliza la ubicación de widgets dispersos moviéndolos a `lib/core/widgets/`.

## Uso

```
/adapt-ui [ruta-del-proyecto] [--normalize]
```

## Parámetros

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `ruta-del-proyecto` | Path absoluto o relativo al proyecto | `/Users/jesus/proyectos/build_wealth_app` |
| `--normalize` | Ejecuta la normalización de widgets (mover a core) | Opcional |

Si no se proporciona ruta, preguntar al usuario.

---

## Proceso

### Paso 1: Validar proyecto

```bash
# Verificar que existe
ls [ruta-del-proyecto]

# Verificar que es un proyecto válido (Flutter, React, Apps Script, etc.)
# Flutter: buscar pubspec.yaml
# React: buscar package.json
# Apps Script: buscar .clasp.json o appsscript.json
```

**Si no es válido** → Informar y abortar.

### Paso 2: Detectar ubicación de widgets

Buscar en orden de prioridad:

| Framework | Rutas comunes |
|-----------|---------------|
| **Flutter** | `lib/core/widgets/`, `lib/presentation/shared/widgets/`, `lib/shared/widgets/`, `lib/widgets/` |
| **React** | `src/components/`, `src/shared/components/`, `src/ui/` |
| **Apps Script** | `src/html/`, `src/ui/`, `html/`, `Templates/` |
| **NiceGUI** | `components/`, `ui/` |

```bash
# Ejemplo Flutter
find [proyecto]/lib -type d -name "widgets" 2>/dev/null
```

**Output esperado**: Lista de carpetas de widgets encontradas.

### Paso 2.5: Detectar widgets dispersos (candidatos a normalizar)

Buscar widgets que deberían estar en `core/` pero están dispersos:

```bash
# Buscar en ubicaciones comunes de widgets "compartidos"
find [proyecto]/lib -type d \( \
  -name "shared" -o \
  -name "common" -o \
  -name "components" -o \
  -name "ui" -o \
  -name "utils" \
\) 2>/dev/null

# Buscar widgets dentro de features que tienen nombre genérico
find [proyecto]/lib/features -type f \( \
  -name "app_*.dart" -o \
  -name "custom_*.dart" -o \
  -name "common_*.dart" -o \
  -name "base_*.dart" -o \
  -name "shared_*.dart" \
\) 2>/dev/null

# Buscar widgets en presentation/widgets de cada feature
find [proyecto]/lib/features/*/presentation/widgets -type f -name "*.dart" 2>/dev/null
```

**Criterios para detectar widget "candidato a core":**

| Señal | Peso | Ejemplo |
|-------|------|---------|
| Nombre con prefijo `App`, `Custom`, `Base`, `Common` | Alto | `app_button.dart`, `custom_card.dart` |
| Ubicado en carpeta `shared/`, `common/` | Alto | `lib/shared/widgets/` |
| Importado desde 2+ features diferentes | Alto | Revisar imports |
| Widget genérico (button, card, input, dialog) | Medio | `primary_button.dart` |
| Sin lógica de negocio específica | Medio | No tiene imports de features |

**Análisis de imports (para detectar uso múltiple):**

```bash
# Para cada widget candidato, contar en cuántos archivos se importa
grep -r "import.*widget_name" [proyecto]/lib --include="*.dart" | wc -l
```

**Output de este paso:**

```
📍 Widgets dispersos encontrados:

| Widget | Ubicación actual | Usado en | Acción sugerida |
|--------|------------------|----------|-----------------|
| app_button.dart | lib/shared/widgets/ | 12 archivos | → lib/core/widgets/buttons/ |
| custom_card.dart | lib/features/home/widgets/ | 5 archivos | → lib/core/widgets/cards/ |
| loading_indicator.dart | lib/common/ | 8 archivos | → lib/core/widgets/feedback/ |
| base_input.dart | lib/utils/ui/ | 3 archivos | → lib/core/widgets/inputs/ |
```

### Paso 3: Escanear widgets existentes

Para cada carpeta de widgets encontrada:

```bash
# Listar archivos
find [carpeta-widgets] -name "*.dart" -o -name "*.tsx" -o -name "*.vue" 2>/dev/null
```

Para cada archivo, extraer:
- Nombre del archivo → nombre probable del widget
- Categoría (inferir de la subcarpeta: buttons/, feedback/, inputs/, etc.)

### Paso 4: Categorizar widgets

Mapear widgets encontrados a las categorías del skill:

| Subcarpeta / Patrón | Categoría Skill |
|---------------------|-----------------|
| `buttons/`, `*_button.dart`, `*Button.dart` | ACTIONS |
| `navigation/`, `*_nav.dart`, `*drawer*`, `*tab*` | NAVIGATION |
| `inputs/`, `*_field.dart`, `*_input.dart`, `*dropdown*` | SELECTION / DATA ENTRY |
| `forms/`, `*_form.dart` | DATA ENTRY |
| `cards/`, `*_card.dart`, `*_tile.dart` | DATA DISPLAY |
| `lists/`, `*_list.dart` | DATA DISPLAY |
| `feedback/`, `*dialog*`, `*snackbar*`, `*toast*`, `*loader*` | FEEDBACK |
| `tables/`, `*_table.dart` | DATA DISPLAY |

### Paso 5: Detectar design tokens (opcional)

Buscar archivos de tema:

```bash
# Flutter
find [proyecto]/lib -name "*colors*" -o -name "*theme*" -o -name "*spacing*" 2>/dev/null
```

Si se encuentran, extraer referencias para incluir en el adapter.

### Paso 6: Generar ui-adapter.md

Usar este template y rellenar con datos reales:

```markdown
# UI Component Adapter

> Generado automáticamente por `/adapt-ui` el [FECHA]
> Proyecto: [NOMBRE_PROYECTO]

## Referencias

- **Skill global**: `.claude/skills/adapt-ui/`
- **Design system**: [RUTA_TEMA_DETECTADA]
- **Widgets base**: [RUTA_WIDGETS_DETECTADA]

---

## Design Tokens

[SI SE DETECTARON ARCHIVOS DE TEMA, REFERENCIARLOS]

```dart
// Ver: [ruta_colors]
// Ver: [ruta_spacing]
```

---

## Mapeo: Componente → Widget

| Componente (Skill) | Widget (Proyecto) | Ubicación | Estado |
|--------------------|-------------------|-----------|--------|
| **NAVIGATION** |
[WIDGETS_NAVEGACION_ENCONTRADOS]
| **DATA DISPLAY** |
[WIDGETS_DISPLAY_ENCONTRADOS]
| **SELECTION** |
[WIDGETS_SELECCION_ENCONTRADOS]
| **DATA ENTRY** |
[WIDGETS_ENTRADA_ENCONTRADOS]
| **ACTIONS** |
[WIDGETS_ACCIONES_ENCONTRADOS]
| **FEEDBACK** |
[WIDGETS_FEEDBACK_ENCONTRADOS]

---

## Widgets no mapeados

[LISTA DE WIDGETS QUE NO ENCAJAN EN CATEGORÍAS CLARAS]

---

## Componentes faltantes

Basado en el skill, estos componentes comunes NO existen aún:

| Componente | Categoría | Prioridad sugerida |
|------------|-----------|-------------------|
[LISTA_COMPONENTES_FALTANTES]

---

## Convenciones detectadas

- **Prefijo**: [App / Feature / Ninguno]
- **Estructura**: [Por tipo / Por feature / Mixta]
- **Nomenclatura**: [snake_case / PascalCase]

---

## Uso

Cuando `/plan` analiza un PRD:

1. Lee el skill global para decidir **qué tipo de componente**
2. Consulta este adapter para saber:
   - ¿Existe ya? → Reutilizar
   - ¿No existe? → Crear tarea en el plan
3. Usa los design tokens para specs del nuevo widget

---

> ⚠️ **Mantener actualizado**: Ejecutar `/adapt-ui` después de crear nuevos widgets core.
```

### Paso 7: Normalización (si --normalize)

**Solo ejecutar si el usuario pasó `--normalize` o confirma cuando se le pregunta.**

#### 7.1 Crear estructura destino

```bash
# Crear carpetas si no existen
mkdir -p [proyecto]/lib/core/widgets/buttons
mkdir -p [proyecto]/lib/core/widgets/cards
mkdir -p [proyecto]/lib/core/widgets/feedback
mkdir -p [proyecto]/lib/core/widgets/inputs
mkdir -p [proyecto]/lib/core/widgets/lists
mkdir -p [proyecto]/lib/core/widgets/navigation
mkdir -p [proyecto]/lib/core/widgets/forms
```

#### 7.2 Mover widgets

Para cada widget candidato:

```bash
# Mover archivo
mv [origen]/widget_name.dart [destino]/widget_name.dart

# Ejemplo:
mv lib/shared/widgets/app_button.dart lib/core/widgets/buttons/app_button.dart
```

#### 7.3 Actualizar imports en todo el proyecto

```bash
# Buscar y reemplazar imports antiguos
find [proyecto]/lib -name "*.dart" -exec sed -i '' \
  's|import.*shared/widgets/app_button.dart|import '\''package:[proyecto]/core/widgets/buttons/app_button.dart'\''|g' {} \;
```

**Estrategia de actualización de imports:**

| Import antiguo | Import nuevo |
|----------------|--------------|
| `package:app/shared/widgets/app_button.dart` | `package:app/core/widgets/buttons/app_button.dart` |
| `package:app/common/loading.dart` | `package:app/core/widgets/feedback/loading.dart` |
| `../../../shared/widgets/card.dart` | `package:app/core/widgets/cards/card.dart` |

**Nota**: Convertir imports relativos a imports de package para consistencia.

#### 7.4 Crear barrel file (opcional)

```dart
// lib/core/widgets/widgets.dart
export 'buttons/app_button.dart';
export 'buttons/icon_button.dart';
export 'cards/app_card.dart';
export 'feedback/app_dialog.dart';
export 'feedback/app_snackbar.dart';
// ... etc
```

#### 7.5 Verificar que compila

```bash
cd [proyecto]
flutter analyze
# o
flutter build --debug
```

**Si hay errores:**
- Mostrar lista de imports que fallaron
- Sugerir correcciones manuales
- NO revertir automáticamente (el usuario decide)

#### 7.6 Output de normalización

```
🔄 Normalización completada:

Widgets movidos: 6
├── app_button.dart → lib/core/widgets/buttons/
├── custom_card.dart → lib/core/widgets/cards/
├── loading_indicator.dart → lib/core/widgets/feedback/
├── base_input.dart → lib/core/widgets/inputs/
├── app_dialog.dart → lib/core/widgets/feedback/
└── shared_list_tile.dart → lib/core/widgets/lists/

Imports actualizados: 47 archivos

⚠️ Verificar manualmente:
- lib/features/auth/login_page.dart (import relativo complejo)

Ejecutar: flutter analyze
```

---

### Paso 8: Guardar archivo

```bash
# Crear .claude/ si no existe
mkdir -p [proyecto]/.claude/

# Guardar
# Ubicación: [proyecto]/.claude/ui-adapter.md
```

### Paso 9: Confirmar

Mostrar resumen:

```
✅ ui-adapter.md generado en [proyecto]/.claude/

Resumen:
- Widgets encontrados: [N]
- Categorías cubiertas: [lista]
- Componentes faltantes: [N]
- Design tokens: [detectados/no detectados]

Próximo paso: Revisar el archivo y ajustar si es necesario.
```

---

## Ejemplo de ejecución

### Sin normalización (solo detectar)

**Input:**
```
/adapt-ui /Users/jesus/proyectos/build_wealth_app
```

**Output esperado:**

```
Analizando proyecto: build_wealth_app
Framework detectado: Flutter

📁 Widgets en lib/core/widgets/:
   buttons/ (4 archivos)
   cards/ (2 archivos)
   feedback/ (3 archivos)
   inputs/ (5 archivos)

📍 Widgets dispersos encontrados:

| Widget | Ubicación actual | Usado en | Sugerencia |
|--------|------------------|----------|------------|
| custom_loader.dart | lib/shared/ | 8 archivos | → core/widgets/feedback/ |
| app_text_field.dart | lib/common/ui/ | 6 archivos | → core/widgets/inputs/ |
| base_card.dart | lib/features/home/widgets/ | 4 archivos | → core/widgets/cards/ |

💡 Ejecuta `/adapt-ui [ruta] --normalize` para mover estos widgets a core/

✅ ui-adapter.md generado en .claude/

Resumen:
├── Widgets en core: 14
├── Widgets dispersos: 3 (candidatos a mover)
├── Categorías cubiertas: ACTIONS, DATA DISPLAY, FEEDBACK, DATA ENTRY
└── Design tokens: detectados

Próximo paso: Revisar .claude/ui-adapter.md
```

### Con normalización

**Input:**
```
/adapt-ui /Users/jesus/proyectos/build_wealth_app --normalize
```

**Output esperado:**

```
Analizando proyecto: build_wealth_app
Framework detectado: Flutter

📁 Widgets actuales en lib/core/widgets/: 14

📍 Widgets dispersos encontrados: 3

¿Mover estos widgets a lib/core/widgets/?

| Widget | De | A |
|--------|----|----|
| custom_loader.dart | lib/shared/ | lib/core/widgets/feedback/ |
| app_text_field.dart | lib/common/ui/ | lib/core/widgets/inputs/ |
| base_card.dart | lib/features/home/widgets/ | lib/core/widgets/cards/ |

[Confirmar movimiento? (s/n)]
> s

🔄 Moviendo widgets...
✓ custom_loader.dart → lib/core/widgets/feedback/
✓ app_text_field.dart → lib/core/widgets/inputs/
✓ base_card.dart → lib/core/widgets/cards/

🔄 Actualizando imports...
✓ 18 archivos actualizados

⚠️ Verificar manualmente:
- lib/features/auth/presentation/login_page.dart (import complejo)

🔍 Ejecutando flutter analyze...
✓ Sin errores

✅ ui-adapter.md generado en .claude/

Resumen:
├── Widgets en core: 17 (+3 movidos)
├── Imports actualizados: 18 archivos
├── Categorías cubiertas: ACTIONS, DATA DISPLAY, FEEDBACK, DATA ENTRY, SELECTION
└── Design tokens: detectados

Próximo paso: 
1. Revisar .claude/ui-adapter.md
2. Commit: git add -A && git commit -m "refactor: normalize widget locations"
```

---

## Notas

- El comando **detecta** pero el desarrollador debe **validar**
- Los nombres de widgets se infieren del archivo, pueden necesitar ajuste
- Ejecutar periódicamente para mantener el adapter sincronizado
- Si `.claude/ui-adapter.md` ya existe, preguntar antes de sobrescribir

### Sobre normalización

- **Siempre hacer backup o commit antes** de ejecutar `--normalize`
- El comando intenta ser conservador: solo mueve widgets con señales claras
- Los imports relativos se convierten a imports de package
- Si `flutter analyze` falla, revisar manualmente antes de commitear
- Widgets específicos de un feature (usados solo ahí) NO se mueven

### Ubicaciones que se normalizan

| Origen (disperso) | Destino (normalizado) |
|-------------------|----------------------|
| `lib/shared/widgets/` | `lib/core/widgets/[categoría]/` |
| `lib/common/` | `lib/core/widgets/[categoría]/` |
| `lib/components/` | `lib/core/widgets/[categoría]/` |
| `lib/ui/` | `lib/core/widgets/[categoría]/` |
| `lib/utils/ui/` | `lib/core/widgets/[categoría]/` |
| `lib/features/*/widgets/` (si es genérico) | `lib/core/widgets/[categoría]/` |
