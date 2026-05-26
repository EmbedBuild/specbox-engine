#!/bin/bash
# sync-extension-version.sh — Mantiene vscode-extension/package.json en lockstep con ENGINE_VERSION.yaml
#
# Usage:
#   ./scripts/sync-extension-version.sh            # --check (default): verifica sync, exit 1 si drift
#   ./scripts/sync-extension-version.sh --check    # Idem
#   ./scripts/sync-extension-version.sh --write    # Reescribe package.json + package-lock.json para match
#
# Designed para v6.2.0+ (US-VSCODE-MARKETPLACE / UC-634).

set -euo pipefail

# --- Locate repo root (script may be invoked from anywhere) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENGINE_YAML="$REPO_ROOT/ENGINE_VERSION.yaml"
EXT_PACKAGE_JSON="$REPO_ROOT/vscode-extension/package.json"
EXT_PACKAGE_LOCK="$REPO_ROOT/vscode-extension/package-lock.json"

# --- Colors (only if stdout is a tty) ---
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; NC=''
fi

# --- Parse args ---
MODE="check"
if [ $# -gt 0 ]; then
    case "$1" in
        --check) MODE="check" ;;
        --write) MODE="write" ;;
        --help|-h)
            sed -n '2,8p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *)
            echo "ERROR: unknown arg '$1'. Use --check or --write." >&2
            exit 2
            ;;
    esac
fi

# --- Read engine version from ENGINE_VERSION.yaml ---
# Same pattern as install.sh:11
if [ ! -f "$ENGINE_YAML" ]; then
    echo "${RED}ERROR: $ENGINE_YAML not found${NC}" >&2
    exit 2
fi
ENGINE_VERSION=$(grep '^version:' "$ENGINE_YAML" | head -1 | awk '{print $2}' | tr -d '"' | tr -d "'")
if [ -z "$ENGINE_VERSION" ]; then
    echo "${RED}ERROR: could not parse 'version:' from $ENGINE_YAML${NC}" >&2
    exit 2
fi

# --- Read current extension version ---
if [ ! -f "$EXT_PACKAGE_JSON" ]; then
    echo "${RED}ERROR: $EXT_PACKAGE_JSON not found${NC}" >&2
    exit 2
fi
EXT_VERSION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$EXT_PACKAGE_JSON")

# --- Modes ---
if [ "$MODE" = "check" ]; then
    if [ "$ENGINE_VERSION" = "$EXT_VERSION" ]; then
        echo "${GREEN}✓ extension version $EXT_VERSION matches engine $ENGINE_VERSION${NC}"
        exit 0
    else
        echo "${RED}✗ DRIFT detected${NC}"
        echo "  engine:    $ENGINE_VERSION  (ENGINE_VERSION.yaml)"
        echo "  extension: $EXT_VERSION  (vscode-extension/package.json)"
        echo ""
        echo "  Fix with: bash scripts/sync-extension-version.sh --write"
        exit 1
    fi
fi

if [ "$MODE" = "write" ]; then
    if [ "$ENGINE_VERSION" = "$EXT_VERSION" ]; then
        echo "${YELLOW}⚠ already in sync ($ENGINE_VERSION) — nothing to do${NC}"
        exit 0
    fi
    # Write package.json
    python3 <<PYEOF
import json
from collections import OrderedDict

path = "$EXT_PACKAGE_JSON"
with open(path) as f:
    data = json.load(f, object_pairs_hook=OrderedDict)
data["version"] = "$ENGINE_VERSION"
with open(path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF
    echo "${GREEN}✓ wrote $EXT_PACKAGE_JSON: version = $ENGINE_VERSION${NC}"

    # Update package-lock.json if present
    if [ -f "$EXT_PACKAGE_LOCK" ]; then
        python3 <<PYEOF
import json
from collections import OrderedDict

path = "$EXT_PACKAGE_LOCK"
with open(path) as f:
    data = json.load(f, object_pairs_hook=OrderedDict)
# top-level version
data["version"] = "$ENGINE_VERSION"
# packages."".version is the canonical entry in lockfileVersion >= 2
if "packages" in data and "" in data["packages"]:
    data["packages"][""]["version"] = "$ENGINE_VERSION"
with open(path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF
        echo "${GREEN}✓ wrote $EXT_PACKAGE_LOCK: version = $ENGINE_VERSION${NC}"
    fi

    exit 0
fi
