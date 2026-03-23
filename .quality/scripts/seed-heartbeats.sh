#!/usr/bin/env bash
# seed-heartbeats.sh — Send initial heartbeat for all local repos
# Usage: .quality/scripts/seed-heartbeats.sh
set -uo pipefail

SALA_URL="${SALA_URL:-https://sala-maquinas.jpsdeveloper.com}"
TOKEN="${SPECBOX_SYNC_TOKEN:?Set SPECBOX_SYNC_TOKEN in your environment}"

# Map: slug|local_path (one per line)
REPOS="
3ch-control-horario|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/3ch/3ch-control-horario
build-wealth-app|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/chaparro project/repositorios/build_wealth_app
escandallo-app|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/escandalloapp/repositorio/escandallo-app
futplanner|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/futplanner/repositorios/futplanner
i-automat-web-portal|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/iautomat/i-automat-web-portal
jpsdeveloper-portfolio|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/portfolio
dev-engine-trello-mcp|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/dev-engine-trello-mcp
dev-engine-mcp|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/dev_engine_mcp
mcp-plaud-recall|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/mcp_plaud_recall
mcp-paddockmanager|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/mcp-paddockmanager
mcp-mcprofit-orchest|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/mcprofit/repositorios/mcp-mcprofit-orchest
mcprofit-people-api|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/mcprofit/repositorios/mcprofit_people_api
mcprofit-web|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/mcprofit/repositorios/mcprofit_web
marioperezfutbol|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/marioperezfutbol.com
moto-fan|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/moto.fan/repositorios/moto.fan
paddock-manager-app|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/paddockmanager/repositorios/Paddock-Manager-App
paddock-manager-data|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/paddockmanager/repositorios/Paddock-Manager-Data
paddock-manager-web|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/paddockmanager/repositorios/Paddock-Manager-Web
specbox-engine|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/specbox-engine
tempo-zenon|/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/tempo_zenon/repositorios/tempo_zenon
DDBoss-WebApp|/Users/jesusperezsanchez/Desktop/Proyectos/1_dental_data/repositorios/DDBoss-WebApp
DDBoss-engine-MCP|/Users/jesusperezsanchez/Desktop/Proyectos/1_dental_data/repositorios/DDBoss-engine-MCP
"

ok=0
fail=0

echo "$REPOS" | while IFS='|' read -r slug repo; do
  [[ -z "$slug" ]] && continue

  if [[ ! -d "$repo/.git" ]]; then
    echo "SKIP  $slug — not a git repo"
    continue
  fi

  # Extract git info
  branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  last_commit_at=$(git -C "$repo" log -1 --format="%aI" 2>/dev/null || echo "")

  # Detect stack
  stack="unknown"
  [[ -f "$repo/pubspec.yaml" ]] && stack="flutter"
  [[ -f "$repo/package.json" ]] && stack="react"
  [[ -f "$repo/pyproject.toml" || -f "$repo/requirements.txt" ]] && stack="python"
  [[ -f "$repo/appsscript.json" ]] && stack="google-apps-script"

  # Use python for safe JSON (handles any commit message chars)
  payload=$(python3 -c "
import json, subprocess
msg = subprocess.check_output(['git','-C','$repo','log','-1','--format=%s'], text=True).strip()[:200]
print(json.dumps({
    'project': '$slug',
    'engine_version': '5.5.0',
    'project_name': '$slug',
    'stack': '$stack',
    'phase': 'idle',
    'plan_total': 0,
    'plan_done': 0,
    'current_task': None,
    'branch': '$branch',
    'last_commit': msg,
    'last_commit_at': '$last_commit_at',
    'session_active': False,
    'test_coverage': 0,
    'tests_passing': 0,
    'tests_failing': 0,
    'self_healing': 0
}))
" 2>/dev/null)

  if [[ -z "$payload" ]]; then
    echo "FAIL  $slug — could not build payload"
    continue
  fi

  response=$(curl -s -X POST "$SALA_URL/api/heartbeat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$payload" 2>&1)

  if echo "$response" | grep -q '"status":"ok"'; then
    echo "OK    $slug ($branch)"
  else
    echo "FAIL  $slug — $response"
  fi
done
