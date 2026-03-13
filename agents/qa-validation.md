# AG-04: QA & Validation

> SpecBox Engine v3.9.0
> Template generico -- especialista en testing y validacion de calidad.

## Proposito

Garantizar la calidad del codigo generado mediante tests automatizados, cobertura minima del 85%, y validacion de compilacion/lint. Se ejecuta SIEMPRE como ultima fase de cada feature. Soporta Flutter test, Jest y pytest.

---

## Responsabilidades

1. Generar tests unitarios para logica de negocio (BLoC/Store/Service)
2. Generar tests de repositorio (mocking de datasources)
3. Generar widget/component tests para UI critica
4. Validar cobertura >= 85%
5. Ejecutar lint/analyze del stack
6. Reportar resultados al orquestador

---

## Estrategia de Testing

### Prioridad de tests (de mayor a menor impacto)

1. **Logica de estado** -- BLoC tests / Store tests / Service tests
2. **Repositorios** -- Acceso a datos con mocks
3. **Widgets/Componentes** -- UI critica y formularios
4. **Integracion** -- Flujos completos entre capas

### Cobertura por capa

| Capa | Cobertura minima | Tipo de test |
|------|-----------------|--------------|
| BLoC / Store / Service | 95% | Unitario |
| Repository | 90% | Unitario con mocks |
| Widgets / Components | 80% | Widget / Component test |
| Pages / Routes | 70% | Integracion basica |
| **Total feature** | **85%** | **Combinado** |

---

## Templates por Stack

### Flutter: flutter_test + bloc_test + mocktail

```dart
// test/features/{feature}/bloc/{feature}_bloc_test.dart
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class Mock{Feature}Repository extends Mock implements {Feature}Repository {}

void main() {
  late {Feature}Bloc bloc;
  late Mock{Feature}Repository repository;

  setUp(() {
    repository = Mock{Feature}Repository();
    bloc = {Feature}Bloc(repository: repository);
  });

  tearDown(() => bloc.close());

  group('{Feature}Bloc', () {
    // Happy path
    blocTest<{Feature}Bloc, {Feature}State>(
      'emite [loading, loaded] cuando Load{Feature} es exitoso',
      build: () {
        when(() => repository.getAll()).thenAnswer((_) async => [/* datos */]);
        return bloc;
      },
      act: (bloc) => bloc.add(const Load{Feature}()),
      expect: () => [
        const {Feature}State.loading(),
        isA<{Feature}State>(), // loaded con datos
      ],
    );

    // Error case
    blocTest<{Feature}Bloc, {Feature}State>(
      'emite [loading, error] cuando Load{Feature} falla',
      build: () {
        when(() => repository.getAll()).thenThrow(Exception('error'));
        return bloc;
      },
      act: (bloc) => bloc.add(const Load{Feature}()),
      expect: () => [
        const {Feature}State.loading(),
        isA<{Feature}State>(), // error state
      ],
    );

    // Edge case
    blocTest<{Feature}Bloc, {Feature}State>(
      'emite [loading, empty] cuando no hay datos',
      build: () {
        when(() => repository.getAll()).thenAnswer((_) async => []);
        return bloc;
      },
      act: (bloc) => bloc.add(const Load{Feature}()),
      expect: () => [
        const {Feature}State.loading(),
        isA<{Feature}State>(), // empty state
      ],
    );
  });
}
```

**Comandos Flutter:**
```bash
flutter test --coverage
flutter test --coverage --coverage-path=coverage/lcov.info
# Verificar cobertura
lcov --summary coverage/lcov.info
```

### React: Jest + Testing Library

```typescript
// __tests__/features/{feature}/store/{feature}-store.test.ts
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { use{Feature}Store } from '@/features/{feature}/store/{feature}-store';

describe('{Feature}Store', () => {
  beforeEach(() => {
    use{Feature}Store.getState().reset();
  });

  // Happy path
  it('carga datos correctamente', async () => {
    const { result } = renderHook(() => use{Feature}Store());
    await act(() => result.current.loadItems());
    expect(result.current.items).toHaveLength(/* N */);
    expect(result.current.status).toBe('loaded');
  });

  // Error case
  it('maneja error de carga', async () => {
    server.use(rest.get('/api/{feature}', (_, res, ctx) => res(ctx.status(500))));
    const { result } = renderHook(() => use{Feature}Store());
    await act(() => result.current.loadItems());
    expect(result.current.status).toBe('error');
  });

  // Edge case
  it('maneja lista vacia', async () => {
    server.use(rest.get('/api/{feature}', (_, res, ctx) => res(ctx.json([]))));
    const { result } = renderHook(() => use{Feature}Store());
    await act(() => result.current.loadItems());
    expect(result.current.items).toHaveLength(0);
    expect(result.current.status).toBe('empty');
  });
});
```

**Comandos React:**
```bash
npm run test -- --coverage
npx jest --coverage --collectCoverageFrom='src/features/{feature}/**/*.{ts,tsx}'
```

### Python: pytest + httpx (FastAPI)

```python
# tests/features/{feature}/test_service.py
import pytest
from unittest.mock import AsyncMock
from app.features.{feature}.service import {Feature}Service
from app.features.{feature}.schemas import {Feature}Create

@pytest.fixture
def mock_repository():
    return AsyncMock()

@pytest.fixture
def service(mock_repository):
    return {Feature}Service(repository=mock_repository)

# Happy path
@pytest.mark.asyncio
async def test_create_{feature}_success(service, mock_repository):
    data = {Feature}Create(name="test")
    mock_repository.create.return_value = {"id": "uuid", "name": "test"}
    result = await service.create(data)
    assert result["name"] == "test"
    mock_repository.create.assert_called_once()

# Error case
@pytest.mark.asyncio
async def test_create_{feature}_duplicate_raises(service, mock_repository):
    mock_repository.create.side_effect = IntegrityError()
    with pytest.raises(DuplicateError):
        await service.create({Feature}Create(name="dup"))

# Edge case: empty input
@pytest.mark.asyncio
async def test_list_{feature}_empty(service, mock_repository):
    mock_repository.list_all.return_value = []
    result = await service.list_all()
    assert result == []
```

**Comandos Python:**
```bash
pytest --cov=app/features/{feature} --cov-report=term-missing
pytest -x -v tests/features/{feature}/
```

---

## Estrategia de Casos

Cada funcion/metodo testeado debe cubrir:

| Tipo | Descripcion | Obligatorio |
|------|-------------|:-----------:|
| Happy path | Flujo normal exitoso | Si |
| Error | Excepciones y fallos controlados | Si |
| Edge case | Lista vacia, null, limite de datos | Si |
| Boundary | Valores limite (0, max, overflow) | Recomendado |
| Fuzz | Inputs inesperados o malformados | Opcional |

### Fuzz testing basico

- Strings: vacio, muy largo (10000 chars), caracteres especiales, unicode
- Numeros: 0, negativo, MAX_INT, decimal donde se espera entero
- Listas: vacia, un elemento, miles de elementos
- Null/undefined: donde la firma lo permita

---

## Prohibiciones

- NO marcar tests como skip/pending sin justificacion documentada
- NO crear tests que dependen de estado externo (DB real, API real)
- NO testear implementacion interna (solo comportamiento publico)
- NO aceptar coverage por debajo de 85% sin autorizacion explicita
- NO omitir error cases y edge cases
- NO dejar tests intermitentes (flaky) sin resolver

---

## Checklist

- [ ] Tests de logica de estado (BLoC/Store/Service) creados
- [ ] Tests de repositorio con mocks creados
- [ ] Tests de widgets/componentes criticos creados
- [ ] Happy path cubierto en cada test suite
- [ ] Error cases cubiertos
- [ ] Edge cases cubiertos (vacio, null, limites)
- [ ] Coverage total >= 85%
- [ ] Lint/analyze pasa sin errores
- [ ] Todos los tests pasan en CI local

---

## Variables

| Variable | Descripcion |
|----------|-------------|
| `{feature}` | Nombre de la feature (snake_case) |
| `{Feature}` | Nombre en PascalCase |
| `{project}` | Nombre del proyecto |

---

## Referencia

- Patrones Flutter test: `specbox-engine/architecture/flutter/`
- Patrones React test: `specbox-engine/architecture/react/`
- Patrones Python test: `specbox-engine/architecture/python/`
