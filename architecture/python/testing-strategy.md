# Estrategia de Testing — Python/FastAPI

## Tipos de Tests

| Tipo | Qué testear | Cuándo | Herramientas |
|------|-------------|--------|--------------|
| **Unit** | Services, repositories, utils | Siempre | `pytest`, `pytest-asyncio` |
| **Integration** | Endpoints, DB queries | Siempre | `httpx`, `pytest` |
| **Acceptance** | Criterios AC-XX del PRD | Siempre (si hay PRD) | `pytest-bdd` |

---

## Unit Tests (pytest)

### Setup

```toml
# pyproject.toml
[project.optional-dependencies]
test = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "pytest-cov>=6.0",
]
```

### Estructura

```
tests/
├── conftest.py                # Fixtures (test db, client, user)
├── unit/
│   ├── services/
│   │   └── test_{feature}_service.py
│   └── utils/
│       └── test_{util}.py
├── integration/
│   └── api/
│       └── test_{feature}.py
└── acceptance/
    ├── features/
    │   └── UC-XXX_{nombre}.feature
    ├── steps/
    │   ├── common_steps.py
    │   └── UC-XXX_steps.py
    └── reports/
        ├── cucumber-report.json
        └── acceptance-report.pdf
```

### Template: Service Test

```python
# tests/unit/services/test_item_service.py
import pytest
from unittest.mock import AsyncMock
from services.item_service import ItemService
from schemas.item import ItemCreate

@pytest.fixture
def mock_repository():
    return AsyncMock()

@pytest.fixture
def service(mock_repository):
    return ItemService(repository=mock_repository)

@pytest.mark.asyncio
async def test_create_item(service, mock_repository):
    data = ItemCreate(name="Test Item", price=10.0)
    mock_repository.create.return_value = {"id": "1", "name": "Test Item", "price": 10.0}

    result = await service.create_item(data)

    mock_repository.create.assert_called_once()
    assert result["name"] == "Test Item"

@pytest.mark.asyncio
async def test_list_items_empty(service, mock_repository):
    mock_repository.get_all.return_value = []

    result = await service.list_items()

    assert result == []
```

### Template: Integration Test

```python
# tests/integration/api/test_items.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_create_item(client):
    response = await client.post("/items/", json={
        "name": "Test Item",
        "price": 10.0,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"

@pytest.mark.asyncio
async def test_list_items(client):
    response = await client.get("/items/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

---

## Acceptance Testing (BDD)

> Tests de aceptación basados en Gherkin que validan AC-XX directamente desde archivos `.feature`.
> Cada UC genera un `.feature`, cada AC genera un Escenario.

### Setup

```toml
# pyproject.toml
[project.optional-dependencies]
test = [
    "pytest>=8.1.0",
    "pytest-bdd>=8.1.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "pytest-cov>=6.0",
]
```

### Ejemplo .feature

```gherkin
# language: es
# tests/acceptance/features/UC-001_crear_propiedad.feature

@US-01 @UC-001
Característica: Crear propiedad
  Como propietario
  Quiero crear una propiedad con nombre, dirección y foto
  Para gestionar mis inmuebles

  Antecedentes:
    Dado que estoy autenticado como "propietario"
    Y el sistema tiene 0 propiedades

  @AC-01
  Escenario: Crear propiedad con datos válidos
    Cuando envío POST a "/propiedades" con nombre "Depto Centro" y dirección "Av. Libertador 1234"
    Entonces la respuesta tiene status 201
    Y la respuesta contiene "Depto Centro"
    Y capturo evidencia del response

  @AC-02
  Escenario: Validación de campos obligatorios
    Cuando envío POST a "/propiedades" sin nombre
    Entonces la respuesta tiene status 422
    Y la respuesta contiene "field required"
    Y capturo evidencia del response
```

### Step Definition (Python)

```python
# tests/acceptance/steps/UC-001_steps.py
import json
import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from httpx import AsyncClient, ASGITransport
from main import app

scenarios('../features/UC-001_crear_propiedad.feature')

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
def context():
    return {}

@given(parsers.parse('que estoy autenticado como "{role}"'))
def autenticado(context, role):
    context['headers'] = {'Authorization': f'Bearer test-token-{role}'}

@given(parsers.parse('el sistema tiene {count:d} propiedades'))
def sistema_con_propiedades(context, count):
    context['initial_count'] = count

@when(parsers.parse('envío POST a "{endpoint}" con nombre "{nombre}" y dirección "{direccion}"'))
async def envio_post(client, context, endpoint, nombre, direccion):
    response = await client.post(
        endpoint,
        json={'nombre': nombre, 'direccion': direccion},
        headers=context.get('headers', {}),
    )
    context['response'] = response

@then(parsers.parse('la respuesta tiene status {status:d}'))
def verificar_status(context, status):
    assert context['response'].status_code == status

@then(parsers.parse('la respuesta contiene "{texto}"'))
def verificar_contenido(context, texto):
    assert texto in context['response'].text

@then('capturo evidencia del response')
def capturo_evidencia(context):
    response = context['response']
    evidence = {
        'status': response.status_code,
        'body': response.json(),
        'headers': dict(response.headers),
    }
    with open('tests/acceptance/reports/evidence.json', 'a') as f:
        f.write(json.dumps(evidence) + '\n')
```

### Ejecución

```bash
# Ejecutar acceptance tests BDD
pytest tests/acceptance/ --cucumberjson=reports/cucumber-report.json

# Con verbose
pytest tests/acceptance/ -v --cucumberjson=reports/cucumber-report.json

# Con coverage
pytest tests/acceptance/ --cov=src --cucumberjson=reports/cucumber-report.json
```

### Report

- Formato: JSON Cucumber estándar (`--cucumberjson`)
- Ubicación: `tests/acceptance/reports/cucumber-report.json`
- PDF de evidencia generado y adjuntado a card UC en Trello (si spec-driven)

### Estructura

```
tests/acceptance/
├── features/
│   ├── UC-001_crear_propiedad.feature
│   └── UC-002_listar_propiedades.feature
├── steps/
│   ├── common_steps.py         # Auth, assertions comunes
│   └── UC-001_steps.py         # Steps específicos del UC
└── reports/
    ├── cucumber-report.json
    └── acceptance-report.pdf
```

---

## Cobertura

```bash
# Ejecutar tests con coverage
pytest --cov=src --cov-report=html --cov-report=term

# Ver reporte HTML
open htmlcov/index.html
```

**Cobertura mínima:** 85% (ratchet)

---

## Hooks de Testing

```bash
# Pre-commit:
ruff check . --fix && ruff format . && mypy . && pytest
```

---

*Referencia: SpecBox Engine v5.18.0*
