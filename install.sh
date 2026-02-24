#!/bin/bash
# JPS Dev Engine - Installer
# Instala commands globales en ~/.claude/commands/ como symlinks
# Usage: ./install.sh [--uninstall] [--dry-run]

set -e

ENGINE_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_COMMANDS_DIR="$HOME/.claude/commands"
VERSION=$(grep 'version:' "$ENGINE_DIR/ENGINE_VERSION.yaml" | head -1 | awk '{print $2}')

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  JPS Dev Engine Installer ${VERSION}         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo ""
}

# Parse arguments
DRY_RUN=false
UNINSTALL=false

for arg in "$@"; do
    case $arg in
        --dry-run)  DRY_RUN=true ;;
        --uninstall) UNINSTALL=true ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run     Show what would be done without making changes"
            echo "  --uninstall   Remove installed symlinks"
            echo "  --help, -h    Show this help"
            exit 0
            ;;
    esac
done

print_header

# --- UNINSTALL ---
if [ "$UNINSTALL" = true ]; then
    echo -e "${YELLOW}Uninstalling JPS Dev Engine commands...${NC}"

    for cmd in "$ENGINE_DIR"/commands/*.md; do
        [ -f "$cmd" ] || continue
        filename=$(basename "$cmd")
        target="$CLAUDE_COMMANDS_DIR/$filename"

        if [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "  Would remove: ${RED}$target${NC}"
            else
                rm "$target"
                echo -e "  Removed: ${RED}$target${NC}"
            fi
        fi
    done

    echo ""
    echo -e "${GREEN}Done.${NC}"
    exit 0
fi

# --- INSTALL ---
echo -e "${GREEN}Installing commands to $CLAUDE_COMMANDS_DIR${NC}"
echo ""

# Create commands dir if needed
if [ ! -d "$CLAUDE_COMMANDS_DIR" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would create: ${BLUE}$CLAUDE_COMMANDS_DIR${NC}"
    else
        mkdir -p "$CLAUDE_COMMANDS_DIR"
        echo -e "  Created: ${BLUE}$CLAUDE_COMMANDS_DIR${NC}"
    fi
fi

# Install each command as symlink
installed=0
updated=0
skipped=0

for cmd in "$ENGINE_DIR"/commands/*.md; do
    [ -f "$cmd" ] || continue
    filename=$(basename "$cmd")
    target="$CLAUDE_COMMANDS_DIR/$filename"

    if [ -L "$target" ]; then
        # Symlink exists - check if points to same place
        current_target=$(readlink "$target")
        if [ "$current_target" = "$cmd" ]; then
            skipped=$((skipped + 1))
            continue
        else
            # Different target - update
            if [ "$DRY_RUN" = true ]; then
                echo -e "  Would update: ${YELLOW}$filename${NC} → $cmd"
            else
                rm "$target"
                ln -s "$cmd" "$target"
                echo -e "  Updated: ${YELLOW}$filename${NC}"
            fi
            updated=$((updated + 1))
        fi
    elif [ -f "$target" ]; then
        # Regular file exists - backup and replace
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would backup and replace: ${YELLOW}$filename${NC}"
        else
            mv "$target" "${target}.backup.$(date +%Y%m%d%H%M%S)"
            ln -s "$cmd" "$target"
            echo -e "  Replaced: ${YELLOW}$filename${NC} (backup created)"
        fi
        updated=$((updated + 1))
    else
        # New install
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would install: ${GREEN}$filename${NC} → $cmd"
        else
            ln -s "$cmd" "$target"
            echo -e "  Installed: ${GREEN}$filename${NC}"
        fi
        installed=$((installed + 1))
    fi
done

echo ""
echo -e "${GREEN}Summary:${NC}"
echo -e "  New:     ${GREEN}$installed${NC}"
echo -e "  Updated: ${YELLOW}$updated${NC}"
echo -e "  Unchanged: $skipped"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}(Dry run - no changes made)${NC}"
else
    echo -e "${GREEN}Installation complete.${NC}"
    echo -e "Commands available: /prd, /plan, /adapt-ui, /optimize-agents"
fi
echo ""
