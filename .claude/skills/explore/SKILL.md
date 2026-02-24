---
name: codebase-explore
description: >
  Read-only codebase exploration and analysis. Use when the user asks
  "analyze codebase", "explore code", "what does this project do",
  "find files related to", "understand architecture", or needs to
  research the codebase before making changes. Cannot modify any files.
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash(find *), Bash(wc *), Bash(cat *), Bash(head *), Bash(tail *)
---

# Codebase Explorer

Explore and analyze the codebase for: $ARGUMENTS

## Analysis Protocol

1. **Project Detection**: Identify framework, language, and architecture pattern
2. **Structure Scan**: Map directory structure (2 levels deep)
3. **Entry Points**: Find main files, routers, app entry points
4. **Dependencies**: Read package manager files (pubspec.yaml, package.json, requirements.txt)
5. **Architecture**: Identify patterns (Clean Architecture, MVC, feature-first, etc.)
6. **Key Files**: List the 10 most important files with brief descriptions
7. **Technical Debt**: Flag obvious issues (large files, duplicated code, missing tests)

## Output Format

Provide a structured report with:
- Project summary (1 paragraph)
- Architecture diagram (ASCII)
- File inventory table (path | purpose | lines | complexity)
- Dependencies list with versions
- Recommendations (max 5, prioritized)

---

## Paso 0: Detectar Stack

```bash
# Detectar archivos de configuración
ls pubspec.yaml package.json pyproject.toml requirements.txt Cargo.toml go.mod Gemfile .clasp.json appsscript.json 2>/dev/null
```

| Archivo encontrado | Stack |
|-------------------|-------|
| pubspec.yaml | Flutter/Dart |
| package.json | Node (React/Next/Vue/etc.) |
| pyproject.toml / requirements.txt | Python |
| Cargo.toml | Rust |
| go.mod | Go |
| .clasp.json / appsscript.json | Google Apps Script |

---

## Paso 1: Estructura del Proyecto

```bash
# Mapear estructura (2 niveles)
find . -maxdepth 2 -type d -not -path '*/\.*' -not -path '*/node_modules/*' -not -path '*/.dart_tool/*' -not -path '*/build/*' | sort

# Contar archivos por extensión
find . -type f -not -path '*/\.*' -not -path '*/node_modules/*' | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -15
```

---

## Paso 2: Entry Points

| Stack | Archivos a buscar |
|-------|-------------------|
| Flutter | lib/main.dart, lib/app.dart, lib/core/router/ |
| React | src/App.tsx, src/index.tsx, pages/_app.tsx, app/layout.tsx |
| Python | main.py, app.py, manage.py, src/main.py |
| Apps Script | src/index.ts, Code.gs, appsscript.json |

---

## Paso 3: Dependencias

Lee el archivo de dependencias y extrae:
- Nombre del paquete
- Versión
- Propósito (inferir de nombre)
- ¿Es core o dev dependency?

---

## Paso 4: Patrones de Arquitectura

Detectar:

| Patrón | Señales |
|--------|---------|
| Clean Architecture | domain/, data/, presentation/ |
| Feature-first | features/*/  con subcarpetas por capa |
| MVC | models/, views/, controllers/ |
| MVVM | viewmodels/ o *_viewmodel.* |
| Hexagonal | ports/, adapters/ |
| Modular | modules/ con independencia |

---

## Paso 5: Key Files

Identificar los 10 archivos más importantes:
1. Entry point principal
2. Router/Navigation
3. State management setup
4. DI/Service locator
5. Base model/entity
6. API client/repository base
7. Theme/Design system
8. Config/Environment
9. Main test file
10. CI/CD config

---

## Paso 6: Technical Debt

Escanear:

```bash
# Archivos grandes (>300 líneas)
find . -name "*.dart" -o -name "*.ts" -o -name "*.tsx" -o -name "*.py" | xargs wc -l 2>/dev/null | sort -rn | head -20

# TODOs y FIXMEs
grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.dart" --include="*.ts" --include="*.py" . 2>/dev/null | head -20

# Tests existence
find . -type d -name "test" -o -name "tests" -o -name "__tests__" -o -name "spec" 2>/dev/null
```

---

## Paso 7: Generar Reporte

```markdown
# Codebase Analysis: [project_name]

> Generated: [date]
> Stack: [detected_stack]
> Architecture: [detected_pattern]

## Summary

[1 paragraph describing what this project does]

## Architecture

```
[ASCII diagram of project structure]
```

## Key Files

| # | File | Purpose | Lines |
|---|------|---------|-------|
| 1 | [path] | [description] | [N] |
| ... | ... | ... | ... |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [name] | [ver] | [desc] |

## Technical Debt

| Issue | Location | Severity |
|-------|----------|----------|
| [desc] | [path] | High/Med/Low |

## Recommendations

1. **[Title]**: [Description]
2. **[Title]**: [Description]
3. **[Title]**: [Description]
```
