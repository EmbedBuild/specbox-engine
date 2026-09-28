# Runbook — Higiene del registro compartido del MCP remoto (UC-3802 AC-04)

> Para el **operador del ecosistema**. Se ejecuta una vez tras desplegar UC-3802 y
> cada vez que se sospeche que el registro volvió a recibir datos que no debe.

## Qué hay en el servidor y por qué importa

El MCP remoto guarda en `/data/state` (volumen persistente del VPS) un índice de
todos los proyectos que alguna vez le reportaron:

| Fichero | Quién lo escribe | Qué contenía antes de UC-3802 |
|---|---|---|
| `registry.json` | `onboard_project`, `register_project`, `update_project_meta` y el auto-registro de la telemetría | `description` libre (clientes, importes, NDA), `repo_url`, a veces rutas locales |
| `projects.json` | `switch_backend`, `switch_project_backend`, `enable_mirror` | `board_id` de FreeForm = ruta absoluta de la máquina del developer |
| `projects/<nombre>/meta.json` | los mismos | `description`, `repo_url`, nombre del developer |

Desde UC-3802 las tools **ya no escriben** descripción ni rutas, y **solo
devuelven** a cada identidad sus propios proyectos. Pero lo que ya estaba en
disco sigue ahí hasta que se purga. Eso es lo que hace este runbook.

## Regla de oro

La purga **exige** una copia cifrada previa, y esa copia **sale del servidor**.
El objetivo es doble: no perder la evidencia que necesita la investigación del
reporte del tester, y no dejar en el host ni el original ni una copia legible.

## Pasos

Todo se ejecuta dentro del contenedor del engine (EasyPanel → servicio del MCP →
consola), o con `docker exec -it <contenedor> sh`.

### 1. Previsualizar (no escribe nada)

```bash
python -m server.registry_hygiene --state-path /data/state --dry-run
```

El informe dice, por fichero, cuántos campos se eliminarían (`removed_fields`)
y cuántos valores con pinta de ruta local se dejarían en blanco
(`blanked_paths`). Revisa que los números tengan sentido antes de seguir.

### 2. Purgar con copia cifrada

La passphrase se pasa **por variable de entorno**, nunca como argumento, para
que no quede en el historial de la shell. Elige una de al menos 12 caracteres y
guárdala en tu gestor de contraseñas: sin ella la copia no se puede abrir.

```bash
export SPECBOX_REGISTRY_BACKUP_PASSPHRASE='<passphrase larga>'
python -m server.registry_hygiene --state-path /data/state \
  --backup-to /data/state/backup/registry-$(date +%F).enc
unset SPECBOX_REGISTRY_BACKUP_PASSPHRASE
```

Orden interno del comando: primero escribe la copia cifrada (PBKDF2-SHA256 →
Fernet), y solo cuando está en disco reescribe los ficheros limpios. Si la copia
falla, no se purga nada.

### 3. Sacar la copia del servidor y borrarla del host

Desde tu máquina:

```bash
scp <usuario>@<vps>:/data/state/backup/registry-<fecha>.enc ~/specbox-audit/
ssh <usuario>@<vps> 'rm -f /data/state/backup/registry-<fecha>.enc'
```

Para leerla en local (con el clon del engine):

```bash
export SPECBOX_REGISTRY_BACKUP_PASSPHRASE='<passphrase larga>'
python -m server.registry_hygiene --decrypt ~/specbox-audit/registry-<fecha>.enc > registry-<fecha>.json
```

Ese JSON es el registro original con todos sus datos: trátalo como material de
la investigación (cifrado en reposo, no lo subas a ningún repositorio).

### 4. Reclamar las entradas legacy (opcional, decisión del operador)

Las entradas anteriores a UC-3802 no tienen `registered_by`, así que **nadie las
ve** desde el MCP hasta que se atribuyen. Si el operador registró él mismo un
proyecto, puede reclamarlo con su `developer_id` (el que devuelve `whoami`):

```bash
# solo algunos
python -m server.registry_hygiene --state-path /data/state --backup-to ... \
  --claim <developer_id> proyecto-a proyecto-b
# todos los que no tengan dueño
python -m server.registry_hygiene --state-path /data/state --backup-to ... \
  --claim <developer_id> --all
```

`--claim` nunca cambia una entrada que ya tiene dueño. Un proyecto que registró
otra persona (por ejemplo, los del tester) no debe reclamarse: esa persona lo
recupera registrándolo de nuevo con su identidad (`register_project` /
`onboard_project`), que respeta las entradas ajenas y rechaza el nombre si ya
pertenece a otro.

### 5. Verificar desde fuera

Con una sesión identificada del MCP (`set_auth_token(backend_type='native', …)`):

- `list_onboarded_projects()` devuelve solo tus proyectos, sin `description` ni rutas.
- Sin sesión, la misma llamada responde `UNAUTHENTICATED` y ningún proyecto.
- `python -m server.registry_hygiene --state-path /data/state --dry-run` informa
  `changed: false` en todos los ficheros.

## Qué NO hace este runbook

- No toca el board native (Supabase): allí no hay descripciones ni rutas del registro.
- No borra proyectos ni su telemetría (`sessions.jsonl`, `checkpoints.jsonl`…);
  solo elimina campos. El reinicio de estado es otra operación (UC-3804).
- No exporta los logs del contenedor; eso sigue en el paso 3 de la contención
  (`doc/discovery/ecosystem-hardening-unification/audit_findings.md` §4 del orquestador).
