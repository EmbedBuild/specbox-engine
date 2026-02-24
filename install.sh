#!/bin/bash
# JPS Dev Engine v3.0 - Installer
# Instala commands, skills y hooks globales en ~/.claude/
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

## --- INSTALL SKILLS (v3.0) ---

SKILLS_DIR="$HOME/.claude/skills"
echo -e "${GREEN}Installing skills to $SKILLS_DIR${NC}"
echo ""

skills_installed=0
for skill_dir in "$ENGINE_DIR"/.claude/skills/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")

    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would install skill: ${GREEN}$skill_name${NC}"
    else
        mkdir -p "$SKILLS_DIR/$skill_name"
        cp -r "$skill_dir"* "$SKILLS_DIR/$skill_name/"
        echo -e "  Installed: ${GREEN}$skill_name${NC}"
    fi
    skills_installed=$((skills_installed + 1))
done

echo -e "  Skills installed: ${GREEN}$skills_installed${NC}"
echo ""

## --- INSTALL HOOKS (v3.0) ---

HOOKS_DIR="$HOME/.claude/hooks"
if [ -d "$ENGINE_DIR/.claude/hooks" ]; then
    echo -e "${GREEN}Installing hooks to $HOOKS_DIR${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would install hooks to $HOOKS_DIR"
    else
        mkdir -p "$HOOKS_DIR"
        cp "$ENGINE_DIR"/.claude/hooks/*.sh "$HOOKS_DIR/"
        chmod +x "$HOOKS_DIR"/*.sh
        echo -e "  Hooks installed"
    fi
    echo ""
fi

## --- INSTALL SETTINGS (v3.0) ---

if [ -f "$ENGINE_DIR/.claude/settings.json" ]; then
    if [ -f "$HOME/.claude/settings.json" ]; then
        echo -e "${YELLOW}  ~/.claude/settings.json already exists. Manual merge needed.${NC}"
        echo -e "  New settings at: $ENGINE_DIR/.claude/settings.json"
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would install: ${GREEN}settings.json${NC}"
        else
            cp "$ENGINE_DIR/.claude/settings.json" "$HOME/.claude/settings.json"
            echo -e "  ${GREEN}Settings installed${NC}"
        fi
    fi
    echo ""
fi

## --- SUMMARY ---

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}(Dry run - no changes made)${NC}"
else
    echo -e "${GREEN}Installation complete.${NC}"
    echo -e "Commands: /prd, /plan, /implement, /adapt-ui, /optimize-agents"
    echo -e "Skills:   /prd, /plan, /implement, /adapt-ui, /optimize-agents, /quality-gate, /explore"
    echo -e "Hooks:    pre-commit-lint, on-session-end, implement-checkpoint"
fi
echo ""
