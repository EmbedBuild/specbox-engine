# Setup: OpenClaw Gateway + SpecBox Engine

## Que es OpenClaw

OpenClaw es un gateway que conecta plataformas de mensajeria (WhatsApp, Discord, Telegram) con Claude Code, permitiendo ejecutar skills y tools MCP desde cualquier chat.

## Arquitectura

```
WhatsApp/Discord → OpenClaw Gateway → Claude Code subprocess → MCP Tools
                                                                    ↓
                                                          SpecBox MCP Server (VPS)
                                                                    ↓
                                                          State Registry (/data/state/)
```

## Requisitos

- OpenClaw Gateway instalado en el VPS (o en cualquier servidor con acceso al MCP)
- SpecBox Engine desplegado con `MCP_TRANSPORT=http`
- `SPECBOX_SYNC_TOKEN` configurado

## Configuracion

### 1. Variables de entorno para OpenClaw

```bash
# MCP remoto de SpecBox
MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp
MCP_AUTH_TOKEN=<SPECBOX_SYNC_TOKEN>

# Canal de mensajeria (ejemplo WhatsApp via Twilio)
WHATSAPP_ACCOUNT_SID=<twilio_sid>
WHATSAPP_AUTH_TOKEN=<twilio_token>
WHATSAPP_FROM=whatsapp:+14155238886

# Canal Discord (opcional)
DISCORD_BOT_TOKEN=<discord_token>
DISCORD_CHANNEL_ID=<channel_id>
```

### 2. Configurar skill /remote

La skill `/remote` en `.claude/skills/remote/SKILL.md` define los comandos disponibles. OpenClaw la activa automaticamente cuando detecta mensajes que coinciden con los triggers.

### 3. Ejemplo de uso desde WhatsApp

```
Tu: "estado de mcprofit"
Bot: green_circle mcprofit — sesion activa
     - Feature: invoice-detail
     - Progreso: 12/18 UCs
     - Veredicto: ACCEPTED
     - Actualizado: hace 5 minutos

Tu: "resumen de todos"
Bot: 21 proyectos | 3 activos | 5 con feedback
     green_circle mcprofit — invoice-detail (5 min)
     yellow_circle futplanner — idle (2 dias)

Tu: "refresh mcprofit"
Bot: mcprofit actualizado desde GitHub (branch main)
```

## Limitaciones

- Respuestas limitadas a 2000 caracteres (limite WhatsApp)
- Sin tablas Markdown (WhatsApp no las renderiza)
- Solo operaciones de lectura en MVP; escritura en Fase 2
- Latencia: 2-5 segundos (OpenClaw → Claude Code → MCP → respuesta)
