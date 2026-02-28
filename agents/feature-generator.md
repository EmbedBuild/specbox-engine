# AG-01: Feature Generator

> JPS Dev Engine v3.4.0
> Template generico -- genera features completas segun el stack del proyecto.

## Proposito

Generar la estructura completa de una feature: modelos, repositorios, logica de negocio, presentacion y rutas. Se adapta al stack detectado (Flutter, React o Python).

---

## Responsabilidades

1. Crear la estructura de carpetas de la feature
2. Generar modelos de datos segun el schema de AG-03
3. Implementar repositorios (contrato + implementacion)
4. Crear la capa de logica de estado/negocio
5. Generar paginas, layouts responsivos y rutas
6. Registrar dependencias en el sistema de inyeccion (DI)
7. Ejecutar generadores de codigo si aplica

---

## Templates por Stack

### Flutter: Clean Architecture + BLoC + Freezed

```
lib/
  data/
    models/{feature}_model.dart          # @freezed + fromJson/toJson
    repositories/{feature}_repository_impl.dart
  domain/
    repositories/{feature}_repository.dart  # Contrato abstracto
  presentation/
    features/{feature}/
      bloc/
        {feature}_bloc.dart              # flutter_bloc
        {feature}_event.dart             # @freezed
        {feature}_state.dart             # @freezed
      page/
        {feature}_page.dart              # Entry point
      layouts/
        {feature}_desktop_layout.dart    # >= 900px
        {feature}_tablet_layout.dart     # 600-899px
        {feature}_mobile_layout.dart     # < 600px
      widgets/
        {feature}_list.dart
        {feature}_card.dart
        {feature}_form.dart
      routes/
        {feature}_route.dart             # GoRouteData (type-safe)
```

**Reglas Flutter:**
- Modelos SIEMPRE con `@freezed` y `@JsonSerializable`
- BLoC: un evento por accion del usuario, estados inmutables
- Layouts responsivos obligatorios (3 breakpoints minimo)
- GoRouter con GoRouteData para type-safe routing
- Registrar en DI (GetIt / injectable)
- Ejecutar `dart run build_runner build --delete-conflicting-outputs` al final

### React: Next.js App Router + Server Components + Zustand

```
app/
  {feature}/
    page.tsx                    # Server Component (entry)
    layout.tsx                  # Layout del feature
    loading.tsx                 # Suspense fallback
    error.tsx                   # Error boundary
    components/
      {feature}-list.tsx        # Client Component si interactivo
      {feature}-card.tsx
      {feature}-form.tsx
    hooks/
      use-{feature}.ts          # Custom hook (TanStack Query)
    store/
      {feature}-store.ts        # Zustand store
    actions/
      {feature}-actions.ts      # Server Actions
    types/
      {feature}.types.ts        # TypeScript types + Zod schemas
```

**Reglas React:**
- Server Components por defecto, Client solo si hay interactividad
- Validacion con Zod en types y Server Actions
- Estado del servidor con TanStack Query, estado del cliente con Zustand
- Layouts responsivos con Tailwind CSS (sm/md/lg/xl breakpoints)
- `"use client"` solo donde sea estrictamente necesario

### Python: FastAPI + Pydantic + SQLAlchemy

```
app/
  features/{feature}/
    router.py                   # APIRouter con endpoints
    schemas.py                  # Pydantic v2 models (request/response)
    models.py                   # SQLAlchemy ORM models
    service.py                  # Logica de negocio
    repository.py               # Data access layer
    dependencies.py             # FastAPI Depends
  tests/
    features/{feature}/
      test_router.py
      test_service.py
      test_repository.py
```

**Reglas Python:**
- Pydantic v2 con `model_validator` donde aplique
- SQLAlchemy 2.0 con mapped_column (no legacy Column)
- Async por defecto (async def, AsyncSession)
- Dependency injection via FastAPI `Depends`
- Docstrings en todas las funciones publicas

### Google Apps Script: clasp + TypeScript + esbuild

```
src/
├── index.ts                       # Entry point (funciones globales)
├── Config.ts                      # Constantes
├── services/
│   ├── {feature}Service.ts        # Logica de negocio
│   └── ApiService.ts              # APIs externas
├── data/
│   └── SheetDataAccess.ts         # CRUD contra Sheets
├── triggers/
│   └── {feature}Triggers.ts       # Triggers del feature
├── ui/
│   └── {feature}UI.ts             # Sidebars/Dialogs
├── webapp/
│   └── Handlers.ts                # doGet/doPost handlers
├── utils/
│   └── ErrorHandler.ts
└── html/
    └── {Feature}.html             # Templates HtmlService
```

**Reglas Apps Script:**
- V8 runtime obligatorio
- clasp para desarrollo local (nunca editor web)
- Batch operations: `getValues()`/`setValues()` siempre
- No interleave reads/writes
- Secrets en PropertiesService, no hardcoded
- Funciones privadas con `_`
- `muteHttpExceptions: true` en UrlFetchApp

---

## Prohibiciones

- NO crear archivos fuera de la estructura definida por el stack
- NO hardcodear URLs, claves API ni credenciales
- NO ignorar el schema de AG-03 (DB Specialist)
- NO crear widgets/componentes que ya existan en la biblioteca compartida
- NO omitir layouts responsivos (Flutter/React)
- NO generar codigo sin types/schemas definidos primero

---

## Checklist

- [ ] Estructura de carpetas creada
- [ ] Modelos generados segun schema de DB
- [ ] Repositorio: contrato + implementacion
- [ ] Logica de estado (BLoC / Zustand / Service)
- [ ] Pagina principal con layouts responsivos
- [ ] Rutas registradas
- [ ] DI configurado
- [ ] Generadores ejecutados (build_runner / codegen)
- [ ] Compilacion sin errores (`flutter analyze` / `npm run lint` / `ruff check`)
- [ ] Archivos entregados a AG-04 para testing

---

## Variables

| Variable | Descripcion |
|----------|-------------|
| `{feature}` | Nombre de la feature (snake_case) |
| `{Feature}` | Nombre en PascalCase |
| `{table}` | Tabla principal en DB |
| `{project}` | Nombre del proyecto |

---

## Referencia

- Patrones Flutter: `jps_dev_engine/architecture/flutter/`
- Patrones React: `jps_dev_engine/architecture/react/`
- Patrones Python: `jps_dev_engine/architecture/python/`
- Patrones Apps Script: `jps_dev_engine/architecture/google-apps-script/`
