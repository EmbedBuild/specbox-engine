# Prompt: Crear dev-engine-trello MCP Server

> Prompt optimizado para Claude Code. Copiar y pegar en una sesion nueva
> dentro del directorio donde se va a crear el proyecto.

---

## Prompt

Necesito que crees un MCP Server llamado `dev-engine-trello` usando **FastMCP 3.x** (ultima version estable, actualmente 3.1.0) con Python 3.14+.

### Que es este MCP

Un servidor MCP que expone **operaciones de dominio del Dev Engine** sobre Trello. NO es un wrapper generico de la API de Trello. Cada tool representa una operacion de negocio del motor de desarrollo agenticoo (User Stories, Use Cases, Acceptance Criteria) que internamente orquesta multiples llamadas a la API REST de Trello.

El objetivo es que el LLM (Claude Code) piense en US/UC/AC, nunca en cards/lists/checklists de Trello.

### Contexto del ecosistema

Ya tengo MCPs desplegados con esta misma arquitectura. Usa como referencia de patron:
- **Repo existente**: Repositorio del MCP genérico de Trello (ver configuración local)
- **Auth Gateway**: `https://your-auth-gateway.example.com` — centraliza credenciales. El usuario llama `set_auth_token(jwt)` y el MCP obtiene API key + token de Trello del gateway.
- **Deploy**: Docker + EasyPanel. Transporte: Streamable HTTP en puerto 8000, endpoint `/mcp`

Lee el server.py, Dockerfile, docker-compose.yml y auth_gateway.py del MCP de Trello existente para entender el patron de autenticacion y transporte. Replica esa misma arquitectura.

### Stack tecnico

- **Python 3.14+** (o 3.11+ si hay problemas de compatibilidad con deps)
- **FastMCP 3.x** (`pip install fastmcp>=3.0.0`) — usar `from fastmcp import FastMCP, Context`
- **httpx** para llamadas async a Trello REST API
- **md2pdf** o **markdown + weasyprint** para conversion markdown->PDF (evalua la opcion mas ligera para Docker)
- **pydantic** para modelos de datos internos
- **structlog** para logging estructurado
- **Docker** para deploy (igual que el MCP de Trello existente)

### Modelo de datos en Trello (Opcion B)

El board de Trello tiene esta estructura:

```
Board: [PROYECTO]
  Listas (workflow states):
    - Backlog
    - Ready
    - In Progress
    - Review
    - Done

  Cards tipo US (User Story):
    - Label azul "US"
    - Custom Field "tipo" = "US"
    - Custom Field "us_id" = "US-01"
    - Custom Field "horas" = 11
    - Custom Field "pantallas" = "1A, 1B, 1C"
    - Description: markdown estructurado con detalle de la US
    - Checklist "Casos de Uso": items que referencian cards UC
    - Attachments: PDFs de evidencia (PRD, Plan, Delivery Report)

  Cards tipo UC (Use Case):
    - Label verde "UC"
    - Label morado "US-XX" (vincula a su US padre)
    - Custom Field "tipo" = "UC"
    - Custom Field "uc_id" = "UC-001"
    - Custom Field "us_id" = "US-01" (referencia al padre)
    - Custom Field "horas" = 3
    - Custom Field "pantallas" = "1A"
    - Custom Field "actor" = "Todos"
    - Description: markdown estructurado parseble
    - Checklist "Criterios de Aceptacion": items AC-XX
    - Attachments: PDFs de evidencia (PRD del UC, AG-09b report)

  Labels:
    - Azul: "US" (User Story)
    - Verde: "UC" (Use Case)
    - Morado: "US-01", "US-02"... (agrupacion por US)
    - Amarillo: "Infra" (infraestructura/tecnico)
    - Rojo: "Bloqueado"

  Custom Fields (6):
    - tipo: list (US | UC)
    - us_id: text (US-01, US-02...)
    - uc_id: text (UC-001, UC-002...)
    - horas: number
    - pantallas: text
    - actor: list (Todos | Profesional | Empresa | Centro | Admin | Dev)
```

### Tools a implementar (20 tools)

Implementa EXACTAMENTE estas tools. Cada una es una operacion atomica de dominio.

#### 0. Auth (1 tool)

**`set_auth_token`** `(jwt: str) -> dict`
- Configura la sesion con JWT del Auth Gateway
- Obtiene credenciales de Trello (api_key, token)
- Patron identico al MCP de Trello existente

#### 1. Board & Setup (3 tools)

**`setup_board`** `(board_name: str) -> dict`
- Crea un board nuevo en Trello
- Crea las 5 listas: Backlog, Ready, In Progress, Review, Done
- Crea los 6 custom fields: tipo, us_id, uc_id, horas, pantallas, actor
- Crea los labels base: US (azul), UC (verde), Infra (amarillo), Bloqueado (rojo)
- Devuelve: `{board_id, board_url, lists: {backlog_id, ready_id, ...}, custom_fields: {...}, labels: {...}}`
- Internamente: 1 POST board + 5 POST lists + 6 POST customFields + 4 POST labels

**`get_board_status`** `(board_id: str) -> dict`
- Lee todas las listas y cuenta cards por lista
- Separa conteo US vs UC
- Calcula progreso: horas done / horas total, UCs done / UCs total
- Devuelve: `{lists: [{name, us_count, uc_count}], progress: {horas_done, horas_total, pct}, us_summary: [{us_id, name, status, uc_progress}]}`
- Internamente: GET board/lists + GET board/cards + GET customFieldItems por card

**`import_spec`** `(board_id: str, spec: dict) -> dict`
- Recibe JSON con estructura `{user_stories: [{us_id, name, hours, screens, description, use_cases: [{uc_id, name, actor, hours, screens, acceptance_criteria: [str], context}]}]}`
- Para cada US: crea card en Backlog con label US + custom fields + description markdown
- Para cada UC de esa US: crea card en Backlog con labels UC + US-XX + custom fields + description parseble + checklist "Criterios de Aceptacion" con items AC-XX numerados
- En card US: crea checklist "Casos de Uso" con items que incluyen link a card UC
- Devuelve: `{created: {us: N, uc: N, ac: N}, errors: []}`
- Internamente: N * (POST card + POST customFieldItems + POST checklist + N * POST checkItem + POST label)

#### 2. User Stories (4 tools)

**`list_us`** `(board_id: str, status: str | None = None) -> list[dict]`
- Filtra cards con custom field tipo=US
- Si status, filtra por lista (backlog, ready, in_progress, review, done)
- Devuelve: `[{us_id, name, hours, status, screens, uc_total, uc_done, ac_total, ac_done}]`

**`get_us`** `(board_id: str, us_id: str) -> dict`
- Lee card US + todas las cards UC hijas (via label US-XX)
- Devuelve: `{us_id, name, hours, status, screens, description, use_cases: [{uc_id, name, actor, hours, status, ac_total, ac_done}], attachments: [{name, url, date}]}`

**`move_us`** `(board_id: str, us_id: str, target: str) -> dict`
- target: "backlog" | "ready" | "in_progress" | "review" | "done"
- Logica de movimiento:
  - `backlog`: mueve US + TODOS sus UCs a Backlog
  - `ready`: mueve US a Ready + UCs en Backlog a Ready
  - `in_progress`: mueve US a In Progress + UCs en Backlog/Ready a Ready (no fuerza In Progress, el engine toma UCs uno a uno)
  - `review`: SOLO si todos los UCs estan en Review o Done. Si no, rechaza con error
  - `done`: SOLO si TODOS los UCs estan en Done. Si no, rechaza con error
- Devuelve: `{us_id, new_status, ucs_moved: N, errors: []}`

**`get_us_progress`** `(board_id: str, us_id: str) -> dict`
- Lee checklist de card US + cards UC hijas + sus checklists AC
- Devuelve: `{us_id, name, total_ucs, done_ucs, total_acs, passed_acs, hours_total, hours_done, ucs: [{uc_id, name, status, acs_total, acs_passed}]}`

#### 3. Use Cases (5 tools)

**`list_uc`** `(board_id: str, us_id: str | None = None, status: str | None = None) -> list[dict]`
- Filtra cards con tipo=UC. Si us_id, filtra por label US-XX. Si status, filtra por lista.
- Devuelve: `[{uc_id, us_id, name, actor, hours, status, screens, ac_total, ac_done}]`

**`get_uc`** `(board_id: str, uc_id: str) -> dict`
- Lee card UC completa. PARSEA la description markdown a JSON estructurado.
- Lee checklist ACs con estado de cada item.
- Lee custom fields.
- **Devuelve JSON optimizado para que el LLM lo use directamente en /prd**:
```json
{
  "uc_id": "UC-001",
  "name": "Iniciar sesion con email y contrasena",
  "us_id": "US-01",
  "us_name": "Autenticacion y Registro",
  "actor": "Todos",
  "hours": 3,
  "screens": ["1A", "1B", "1C"],
  "status": "ready",
  "acceptance_criteria": [
    {"id": "AC-01", "text": "Valida formato email", "done": false},
    {"id": "AC-02", "text": "Muestra error si credenciales invalidas", "done": false},
    {"id": "AC-03", "text": "Redirige segun rol", "done": false}
  ],
  "context": "Sistema completo de acceso. Supabase Auth email+password.",
  "description_raw": "...(markdown original)...",
  "attachments": [{"name": "UC-001_PRD.pdf", "url": "...", "date": "..."}],
  "trello_card_id": "abc123",
  "trello_card_url": "https://trello.com/c/..."
}
```

**`move_uc`** `(board_id: str, uc_id: str, target: str) -> dict`
- Mueve card UC a la lista target
- Post-move: si target=done, marca checkitem correspondiente como complete en checklist de card US padre
- Si es el ultimo UC en Done de esa US, añade comment a card US: "Todos los UCs completados"
- Devuelve: `{uc_id, new_status, us_checklist_updated: bool, us_all_done: bool}`

**`start_uc`** `(board_id: str, uc_id: str) -> dict`
- Shortcut: mueve a In Progress + añade comment con timestamp "Desarrollo iniciado: {datetime}"
- Devuelve el JSON completo del UC (misma estructura que get_uc) para que el LLM tenga todo listo

**`complete_uc`** `(board_id: str, uc_id: str, evidence: str | None = None) -> dict`
- Mueve a Done
- Marca checkitem en checklist de US padre como complete
- Si evidence: añade comment con el texto de evidencia
- Si es el ultimo UC de la US: añade comment a card US "US-XX completada: X/X UCs, Y/Y ACs"
- Devuelve: `{uc_id, completed_at, us_checklist_updated, us_all_done, us_id}`

#### 4. Acceptance Criteria (3 tools)

**`mark_ac`** `(board_id: str, uc_id: str, ac_id: str, passed: bool, evidence: str | None = None) -> dict`
- Marca checkitem AC-XX como complete/incomplete en checklist de card UC
- Añade comment: "AC-XX: PASSED|FAILED {evidence}" con timestamp
- Devuelve: `{uc_id, ac_id, passed, ac_total, ac_done}`

**`mark_ac_batch`** `(board_id: str, uc_id: str, results: list[dict]) -> dict`
- Cada result: `{ac_id: str, passed: bool, evidence: str | None}`
- Marca multiples ACs de golpe
- Añade UN comment consolidado: "Validacion AG-09b: AC-01 PASSED, AC-02 PASSED, AC-03 FAILED..."
- Si todos passed: comment extra "Todos los criterios de aceptacion validados"
- Devuelve: `{uc_id, total, passed, failed, details: [{ac_id, passed}]}`

**`get_ac_status`** `(board_id: str, uc_id: str) -> dict`
- Lee checklist ACs de la card UC
- Devuelve: `{uc_id, total, done, pending, criteria: [{id, text, done}]}`

#### 5. Evidence (2 tools)

**`attach_evidence`** `(board_id: str, target_id: str, target_type: str, evidence_type: str, markdown_content: str, summary: str | None = None) -> dict`
- target_type: "us" | "uc"
- evidence_type: "prd" | "plan" | "ag09" | "delivery" | "feedback"
- Convierte markdown_content a PDF usando md2pdf/weasyprint
- Genera nombre: `{target_id}_{evidence_type}.pdf` (ej: `US-01_PRD.pdf`, `UC-001_ag09.pdf`)
- Sube PDF como attachment a la card correspondiente
- Añade comment con summary (o genera uno automatico): "{evidence_type} generado — {summary}"
- Devuelve: `{target_id, evidence_type, attachment_id, attachment_url, comment_added: true}`

**`get_evidence`** `(board_id: str, target_id: str, target_type: str, evidence_type: str | None = None) -> dict`
- Lee attachments + comments de la card
- Si evidence_type, filtra por nombre de archivo que contenga el tipo
- Devuelve: `{target_id, attachments: [{name, url, date, size}], activity: [{text, date}]}`

#### 6. Dashboard (3 tools)

**`get_sprint_status`** `(board_id: str) -> dict`
- Resumen ejecutivo del board completo
- Devuelve:
```json
{
  "board_name": "TALENT-ON",
  "total_us": 15, "total_uc": 75, "total_ac": 224,
  "by_status": {
    "backlog": {"us": 10, "uc": 50},
    "ready": {"us": 2, "uc": 8},
    "in_progress": {"us": 1, "uc": 3},
    "review": {"us": 1, "uc": 5},
    "done": {"us": 1, "uc": 9}
  },
  "hours": {"total": 224, "done": 35, "in_progress": 11, "pct": 15.6},
  "acs": {"total": 224, "passed": 28, "pct": 12.5},
  "blocked": []
}
```

**`get_delivery_report`** `(board_id: str) -> dict`
- Report orientado al cliente: por cada US, progreso y estado
- Devuelve:
```json
{
  "project": "TALENT-ON",
  "generated_at": "2026-03-10T14:00:00Z",
  "summary": {"total_us": 15, "completed_us": 3, "pct": 20.0},
  "user_stories": [
    {
      "us_id": "US-01", "name": "Autenticacion y Registro",
      "status": "done", "hours": 11,
      "ucs_completed": "4/4", "acs_passed": "12/12"
    }
  ]
}
```

**`find_next_uc`** `(board_id: str) -> dict | None`
- Busca el siguiente UC a ejecutar
- Prioridad: 1) UCs en Ready cuya US ya tiene UCs en In Progress (mantener foco), 2) UCs en Ready de la US con mas UCs en Ready (empezar bloque), 3) Primer UC en Ready por orden
- Devuelve: JSON completo del UC (misma estructura que get_uc) o null si no hay nada en Ready

### Estructura del proyecto

```
dev-engine-trello/
  src/
    __init__.py
    __main__.py              # Entry point: python -m src
    server.py                # FastMCP server + tools registration
    auth_gateway.py          # Copia/adapta del MCP de Trello existente
    trello_client.py         # Wrapper async httpx para Trello REST API
    models.py                # Pydantic models: US, UC, AC, BoardConfig, etc.
    tools/
      __init__.py
      auth.py                # set_auth_token
      board.py               # setup_board, get_board_status, import_spec
      user_story.py          # list_us, get_us, move_us, get_us_progress
      use_case.py            # list_uc, get_uc, move_uc, start_uc, complete_uc
      acceptance.py          # mark_ac, mark_ac_batch, get_ac_status
      evidence.py            # attach_evidence, get_evidence
      dashboard.py           # get_sprint_status, get_delivery_report, find_next_uc
    pdf_generator.py         # Markdown -> PDF conversion
    board_helpers.py         # Funciones helper: find_card_by_custom_field, get_list_id_by_name, etc.
  tests/
    __init__.py
    test_models.py
    test_board_helpers.py
    test_trello_client.py
    conftest.py              # Fixtures con mocks de httpx
  Dockerfile
  docker-compose.yml
  pyproject.toml
  requirements.txt
  .env.example
  README.md
```

### Patron del trello_client.py

```python
class TrelloClient:
    """Async client para Trello REST API. Encapsula TODAS las llamadas HTTP."""

    def __init__(self, api_key: str, token: str):
        self.client = httpx.AsyncClient(
            base_url="https://api.trello.com/1",
            params={"key": api_key, "token": token},
            timeout=30.0,
        )

    # Board
    async def create_board(self, name: str) -> dict: ...
    async def get_board(self, board_id: str) -> dict: ...
    async def get_board_lists(self, board_id: str) -> list[dict]: ...
    async def get_board_cards(self, board_id: str) -> list[dict]: ...
    async def get_board_labels(self, board_id: str) -> list[dict]: ...
    async def get_board_custom_fields(self, board_id: str) -> list[dict]: ...

    # Lists
    async def create_list(self, board_id: str, name: str, pos: str = "bottom") -> dict: ...

    # Cards
    async def create_card(self, list_id: str, name: str, desc: str = "", labels: list[str] = None) -> dict: ...
    async def get_card(self, card_id: str) -> dict: ...
    async def move_card(self, card_id: str, list_id: str) -> dict: ...
    async def add_comment(self, card_id: str, text: str) -> dict: ...
    async def get_card_attachments(self, card_id: str) -> list[dict]: ...
    async def add_attachment(self, card_id: str, file: bytes, name: str, mime_type: str = "application/pdf") -> dict: ...
    async def get_card_actions(self, card_id: str, filter: str = "commentCard") -> list[dict]: ...

    # Custom Fields
    async def create_custom_field(self, board_id: str, name: str, field_type: str, options: list[str] = None) -> dict: ...
    async def set_custom_field(self, card_id: str, field_id: str, value: Any) -> dict: ...
    async def get_card_custom_fields(self, card_id: str) -> list[dict]: ...

    # Checklists
    async def create_checklist(self, card_id: str, name: str) -> dict: ...
    async def add_checklist_item(self, checklist_id: str, name: str) -> dict: ...
    async def update_checklist_item(self, card_id: str, checkitem_id: str, state: str) -> dict: ...
    async def get_card_checklists(self, card_id: str) -> list[dict]: ...

    # Labels
    async def create_label(self, board_id: str, name: str, color: str) -> dict: ...
    async def add_label_to_card(self, card_id: str, label_id: str) -> dict: ...

    # Cleanup
    async def close(self): ...
```

### Patron del server.py

```python
from fastmcp import FastMCP, Context

mcp = FastMCP(
    name="dev-engine-trello",
    instructions="""
    MCP server for SDD-JPS Engine — Trello project management.

    Operates on User Stories (US), Use Cases (UC), and Acceptance Criteria (AC).
    Each tool is a domain operation that orchestrates multiple Trello API calls.

    Authentication: Call set_auth_token(jwt) first with a JWT from Auth Gateway.

    Board structure: Lists are workflow states (Backlog -> Ready -> In Progress -> Review -> Done).
    Cards are either US (User Story) or UC (Use Case), linked via labels and custom fields.
    """,
)

# Register all tools from modules
from .tools import auth, board, user_story, use_case, acceptance, evidence, dashboard

# Each module registers its tools on the mcp instance

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))

    if transport == "streamable-http":
        mcp.run(transport="http", host=host, port=port)
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run()  # stdio
```

### board_helpers.py — funciones clave

Necesito helpers reutilizables que usen los custom fields para encontrar cards:

```python
async def find_card_by_custom_field(client: TrelloClient, board_id: str, field_name: str, value: str) -> dict | None:
    """Busca una card en el board por valor de custom field (ej: us_id=US-01)"""

async def get_list_id_by_name(client: TrelloClient, board_id: str, name: str) -> str | None:
    """Obtiene el ID de una lista por su nombre (case-insensitive)"""

async def get_us_children(client: TrelloClient, board_id: str, us_id: str) -> list[dict]:
    """Obtiene todas las cards UC que pertenecen a una US (via label US-XX o custom field us_id)"""

async def get_list_name_for_card(client: TrelloClient, card: dict, lists: list[dict]) -> str:
    """Dado una card y las listas del board, devuelve el nombre de la lista donde esta"""

async def parse_uc_description(description: str) -> dict:
    """Parsea el markdown estructurado de una card UC a JSON"""

async def build_us_description(us: dict) -> str:
    """Genera el markdown para la description de una card US"""

async def build_uc_description(uc: dict) -> str:
    """Genera el markdown parseble para la description de una card UC"""
```

### Formato del markdown de description de UC (para que sea parseble)

```markdown
## UC-001: Iniciar sesion con email y contrasena

**User Story**: US-01 Autenticacion y Registro
**Actor**: Todos
**Horas**: 3
**Pantallas**: 1A, 1B, 1C

### Criterios de Aceptacion
- AC-01: Valida formato email
- AC-02: Muestra error si credenciales invalidas
- AC-03: Redirige segun rol (Admin->Dashboard, Profesional->Home, Empresa->Mi Empresa)

### Contexto
Sistema completo de acceso a la aplicacion. Supabase Auth con email+password.
Tres roles: Admin, Centro/Empresa, Profesional.

### Notas
[Notas adicionales del cliente o de la llamada]
```

### PDF Generation

Para `attach_evidence`, necesito convertir markdown a PDF. Evalua estas opciones y elige la mas ligera para Docker:

1. **md2pdf** (usa weasyprint internamente) — pip install md2pdf
2. **markdown + weasyprint** directo — mas control pero mas deps del sistema (cairo, pango)
3. **fpdf2 + markdown** — pure Python, sin deps del sistema, pero menos bonito

Prioriza que funcione en Docker sin problemas. Si weasyprint requiere muchas deps del sistema, usa fpdf2.

El PDF debe tener:
- Header con logo/nombre del proyecto (simple, texto)
- Fecha de generacion
- Contenido del markdown renderizado (headers, tablas, listas, code blocks)
- Footer con pagina X de Y

### Docker

Replica el patron del Dockerfile del MCP de Trello existente:
- Base: python:3.11-slim (o 3.14-slim si las deps lo permiten)
- PYTHONUNBUFFERED=1
- Transporte: streamable-http por defecto
- Puerto: 8000
- Healthcheck en /mcp
- CMD: python -m src

### .env.example

```
# Auth Gateway
AUTH_GATEWAY_URL=https://your-auth-gateway.example.com
AUTH_GATEWAY_API_KEY=

# Transport
MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Trello (obtenidos automaticamente via Auth Gateway, solo para dev local)
TRELLO_API_KEY=
TRELLO_TOKEN=
```

### Tests

Crea tests con pytest + pytest-asyncio:
- Mock httpx con respuestas realistas de Trello
- Test cada helper de board_helpers.py
- Test parse_uc_description con diferentes formatos de markdown
- Test la logica de move_us (validaciones de estado)
- Test import_spec con un spec minimo (1 US, 2 UCs)
- Test mark_ac_batch consolidacion de resultados

### Instrucciones de implementacion

1. **Empieza por los modelos** (models.py) — define bien los Pydantic models
2. **Luego trello_client.py** — wrapper puro de la API, sin logica de negocio
3. **Luego board_helpers.py** — funciones helper que usan el client
4. **Luego los tools uno por uno**, empezando por auth -> board -> user_story -> use_case -> acceptance -> evidence -> dashboard
5. **Tests en paralelo** conforme avanzas
6. **PDF generator al final** (es independiente)
7. **Docker al final** (solo empaqueta)

### Criterios de calidad

- Cada tool devuelve JSON estructurado, nunca texto libre
- Los errores se devuelven como `{"error": "mensaje", "code": "ERROR_CODE"}`
- Logging con structlog en cada operacion (tool name, board_id, duracion)
- Type hints en todo
- Docstrings claros en cada tool (el LLM los lee como descripcion de la tool)
- Zero hardcoding: todo configurable via env vars o parametros

---

**IMPORTANTE**: Este MCP reemplazara al MCP generico de Trello para operaciones del Dev Engine. El MCP generico (`trello-iautomat`) sigue existiendo para operaciones genericas. Este nuevo MCP (`dev-engine-trello`) es especifico para el flujo US/UC/AC del motor de desarrollo.
