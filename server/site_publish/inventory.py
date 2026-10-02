"""Parser del inventario de capacidades del engine (UC-2001, US-20).

Hermano de `parser.py`: mientras aquel deriva release/changelog de ENGINE_VERSION.yaml y
CHANGELOG.md, este deriva el **inventario de capacidades** —agentes, MCP tools, skills y la
extensión VSCode— directamente del código del engine. La verdad sale de donde ya vive (no de
un catálogo curado paralelo): así es imposible que el site y el engine se desincronicen.

Sin dependencias de red ni de Supabase: recibe un `engine_root` (Path) y devuelve dataclasses
puras. Esto lo hace trivial de testear (AC-01..05) con un árbol de ficheros fixture, y lo deja
reutilizable por el publicador (UC-2002) y por `__main__` (UC-2003).

Fuentes canónicas (verificadas en el repo, 2026-06-18):
- Agentes: ``agents/*.md`` — 1 entrada por fichero. Nombre del H1 ``# Título (Nombre)``.
- MCP tools: el registro del propio servidor (``server.server.mcp``), lo mismo que devuelve
  ``tools/list`` a un cliente (UC-6201). Leer decoradores con regex se perdía las tools
  registradas como ``mcp_instance.tool(...)(fn)``: el site decía 126 cuando el MCP exponía 192.
- Skills: ``.claude/skills/*/SKILL.md`` — 1 por directorio. ``command`` = ``/<dirname>``,
  ``description`` del front-matter YAML.
- Extensión VSCode: ``vscode-extension/package.json`` — name/publisher/version + marketplace_id.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from server.site_publish.publisher import (
    PublishCredentials,
    PublishRequest,
    PublishResult,
    execute_requests,
)


@dataclass
class AgentInfo:
    agent_key: str
    name: str = ""
    role: str = ""


@dataclass
class ToolInfo:
    tool_name: str
    module: str = ""


@dataclass
class SkillInfo:
    skill_key: str
    command: str = ""
    description: str = ""


@dataclass
class VscodeExtInfo:
    marketplace_id: str
    name: str = ""
    publisher: str = ""
    version: str = ""


@dataclass
class CapabilityInventory:
    """Inventario completo de capacidades del engine, listo para publicar a Supabase."""

    agents: list[AgentInfo] = field(default_factory=list)
    tools: list[ToolInfo] = field(default_factory=list)
    skills: list[SkillInfo] = field(default_factory=list)
    vscode_ext: VscodeExtInfo | None = None


# ---------------------------------------------------------------------------
# Agentes — agents/*.md
# ---------------------------------------------------------------------------

# H1 de un agente: "# Orquestador de Agentes (Orchestrator)" → name = lo de dentro del paréntesis
# si existe, si no el título completo.
_AGENT_H1 = re.compile(r"^#\s+(?P<title>.+?)\s*$")
_AGENT_PAREN = re.compile(r"^(?P<base>.+?)\s*\((?P<paren>[^)]+)\)\s*$")


def _parse_agent_file(path: Path) -> AgentInfo:
    """Deriva un AgentInfo de un fichero agents/*.md.

    name = contenido del paréntesis del H1 si lo hay (p.ej. "Orchestrator"), si no el título.
    role = primer párrafo no vacío tras la sección de propósito o tras el H1.
    """
    agent_key = path.stem  # nombre de fichero sin extensión, p.ej. "db-specialist"
    name = agent_key
    role = ""

    lines = path.read_text(encoding="utf-8").splitlines()
    seen_h1 = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not seen_h1:
            h1 = _AGENT_H1.match(line)
            if h1:
                seen_h1 = True
                title = h1.group("title").strip()
                paren = _AGENT_PAREN.match(title)
                name = paren.group("paren").strip() if paren else title
            continue
        # Tras el H1, el primer párrafo de texto (no blockquote, no header, no tabla) es el rol.
        if stripped and not stripped.startswith(("#", ">", "|", "-", "*", "```")):
            role = stripped
            break

    return AgentInfo(agent_key=agent_key, name=name, role=role)


def parse_agents(agents_dir: Path) -> list[AgentInfo]:
    """Lista los agentes de ``agents/*.md``, ordenados por nombre de fichero."""
    if not agents_dir.is_dir():
        return []
    return [_parse_agent_file(p) for p in sorted(agents_dir.glob("*.md"))]


# ---------------------------------------------------------------------------
# MCP tools — el registro del servidor (lo que devuelve tools/list)
# ---------------------------------------------------------------------------


def _tool_module(tool, engine_root: Path) -> str:
    """Fichero que define la tool, relativo a ``engine_root`` ("server/tools/foo.py").

    ``inspect.unwrap`` salta los decoradores que envuelven la función (p. ej.
    ``@requires_app_docs_sync``) para no atribuir la tool al módulo del decorador.
    """
    fn = getattr(tool, "fn", None)
    if fn is None:
        return ""
    try:
        source = inspect.getsourcefile(inspect.unwrap(fn))
    except TypeError:
        return ""
    if not source:
        return ""
    try:
        return str(Path(source).resolve().relative_to(engine_root))
    except ValueError:
        return ""


def registered_tools(engine_root: Path) -> list[ToolInfo]:
    """Las tools que expone el servidor MCP de ``engine_root``, en orden de registro.

    Pregunta al registro del propio servidor en vez de leer el código: cuenta cualquier forma de
    registrar una tool (decorador o ``mcp_instance.tool(...)(fn)``) y usa el nombre público, el
    mismo que ve un cliente en ``tools/list``.

    - Sin ``server/server.py`` bajo ``engine_root`` → lista vacía (fuente ausente).
    - El registro es el del servidor importado en este proceso: si ``engine_root`` es otro
      checkout, lanza ``ValueError`` en vez de publicar las tools de un engine distinto.
    - Síncrona (``asyncio.run``): no llamarla desde un bucle de eventos en marcha.
    """
    engine_root = Path(engine_root).resolve()
    if not (engine_root / "server" / "server.py").is_file():
        return []

    import server as server_package

    imported_root = Path(server_package.__file__).resolve().parents[1]
    if imported_root != engine_root:
        raise ValueError(
            f"El inventario de tools sale del servidor importado ({imported_root}) y no puede "
            f"describir otro engine ({engine_root}). Ejecuta site_publish desde ese engine."
        )

    from server.server import mcp

    tools = asyncio.run(mcp.list_tools())
    return [ToolInfo(tool_name=t.name, module=_tool_module(t, engine_root)) for t in tools]


# ---------------------------------------------------------------------------
# Skills — .claude/skills/*/SKILL.md
# ---------------------------------------------------------------------------

# description del front-matter YAML. Soporta forma inline ("description: foo") y bloque
# ("description: >" / "description: |" con líneas indentadas debajo).
def _parse_skill_description(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    # Aislar el front-matter (entre el primer y el segundo "---").
    end = text.find("\n---", 3)
    front = text[3:end] if end != -1 else text[3:]
    lines = front.splitlines()
    for idx, line in enumerate(lines):
        m = re.match(r"^description:\s*(.*)$", line)
        if not m:
            continue
        inline = m.group(1).strip()
        if inline and inline not in (">", "|", ">-", "|-", ">+", "|+"):
            return inline.strip().strip('"').strip("'")
        # Bloque multilínea: recoger líneas indentadas siguientes.
        collected: list[str] = []
        for cont in lines[idx + 1 :]:
            if cont.strip() == "":
                if collected:
                    break
                continue
            if cont[0].isspace():
                collected.append(cont.strip())
            else:
                break
        return " ".join(collected).strip()
    return ""


def parse_skills(skills_dir: Path) -> list[SkillInfo]:
    """Lista las skills de ``.claude/skills/*/SKILL.md``, una por directorio."""
    if not skills_dir.is_dir():
        return []
    skills: list[SkillInfo] = []
    for sub in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = sub / "SKILL.md"
        if not skill_md.is_file():
            continue
        skills.append(
            SkillInfo(
                skill_key=sub.name,
                command=f"/{sub.name}",
                description=_parse_skill_description(skill_md),
            )
        )
    return skills


# ---------------------------------------------------------------------------
# Extensión VSCode — vscode-extension/package.json
# ---------------------------------------------------------------------------


def parse_vscode_ext(package_json: Path) -> VscodeExtInfo | None:
    """Deriva la VscodeExtInfo de ``vscode-extension/package.json`` (None si no existe)."""
    if not package_json.is_file():
        return None
    data = json.loads(package_json.read_text(encoding="utf-8"))
    name = str(data.get("name", "") or "")
    publisher = str(data.get("publisher", "") or "")
    version = str(data.get("version", "") or "")
    marketplace_id = f"{publisher}.{name}" if publisher and name else (name or publisher)
    return VscodeExtInfo(
        marketplace_id=marketplace_id,
        name=name,
        publisher=publisher,
        version=version,
    )


# ---------------------------------------------------------------------------
# Entrypoint público
# ---------------------------------------------------------------------------


def build_capability_inventory(engine_root: Path) -> CapabilityInventory:
    """Construye el inventario completo de capacidades del engine (AC-01).

    No toca red ni Supabase. Lee agentes, skills y extensión bajo ``engine_root`` y las tools del
    registro de su servidor (``registered_tools``), y devuelve un CapabilityInventory. Cualquier
    fuente ausente degrada a lista vacía / None sin lanzar, de modo que el publicador puede
    decidir qué hacer.
    """
    engine_root = Path(engine_root)
    return CapabilityInventory(
        agents=parse_agents(engine_root / "agents"),
        tools=registered_tools(engine_root),
        skills=parse_skills(engine_root / ".claude" / "skills"),
        vscode_ext=parse_vscode_ext(engine_root / "vscode-extension" / "package.json"),
    )


# ---------------------------------------------------------------------------
# Publicación a Supabase (UC-2002) — mismo patrón que publisher.build_publish_requests
# ---------------------------------------------------------------------------


def build_inventory_publish_requests(inventory: CapabilityInventory) -> list[PublishRequest]:
    """Construye las peticiones idempotentes para publicar el inventario (AC-06).

    Hermano de ``publisher.build_publish_requests``: un UPSERT con
    ``Prefer: resolution=merge-duplicates`` por cada superficie del inventario a su tabla
    ``public.engine_*``. Reejecutarlo sobre el mismo inventario produce el mismo estado final
    (idempotente). No emite petición para una superficie vacía (evita POST con body []).

    El transporte (`publish`) y la credencial (`PublishCredentials`) se reutilizan de
    ``publisher.py``; aquí solo se decide *qué* peticiones hacer (función pura, testeable sin red).
    """
    requests: list[PublishRequest] = []

    if inventory.agents:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_agent",
                params={},
                json=[
                    {"agent_key": a.agent_key, "name": a.name or "", "role": a.role or ""}
                    for a in inventory.agents
                ],
                prefer="resolution=merge-duplicates",
            )
        )

    if inventory.tools:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_tool",
                params={},
                json=[
                    {"tool_name": t.tool_name, "module": t.module or ""}
                    for t in inventory.tools
                    if t.tool_name
                ],
                prefer="resolution=merge-duplicates",
            )
        )

    if inventory.skills:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_skill",
                params={},
                json=[
                    {
                        "skill_key": s.skill_key,
                        "command": s.command or "",
                        "description": s.description or "",
                    }
                    for s in inventory.skills
                ],
                prefer="resolution=merge-duplicates",
            )
        )

    if inventory.vscode_ext is not None:
        ext = inventory.vscode_ext
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_vscode_ext",
                params={},
                json=[
                    {
                        "marketplace_id": ext.marketplace_id,
                        "name": ext.name or "",
                        "publisher": ext.publisher or "",
                        "version": ext.version or "",
                    }
                ],
                prefer="resolution=merge-duplicates",
            )
        )

    return requests


def publish_inventory(
    inventory: CapabilityInventory, creds: PublishCredentials, http_client
) -> PublishResult:
    """Publica el inventario de capacidades a Supabase (UC-2002).

    Cierra el ciclo build→execute reutilizando el transporte de ``publisher.execute_requests``
    (misma credencial service-role, misma redacción, mismo manejo de errores que release/changelog).
    """
    return execute_requests(build_inventory_publish_requests(inventory), creds, http_client)
