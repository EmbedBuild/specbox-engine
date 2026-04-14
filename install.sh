#!/bin/bash
# SpecBox Engine - Installer
# Instala skills y hooks globales en ~/.claude/
# Usage: ./install.sh [--uninstall] [--dry-run]
#        ./install.sh --skill <path|git-url> [--local]
#        ./install.sh --remove-skill <name>

set -e

ENGINE_DIR="$(cd "$(dirname "$0")" && pwd)"
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
    echo -e "${BLUE}║  SpecBox Engine Installer ${VERSION}         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo ""
}

# Parse arguments
DRY_RUN=false
UNINSTALL=false
SKILL_PATH=""
SKILL_LOCAL=false
REMOVE_SKILL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)  DRY_RUN=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --skill)
            SKILL_PATH="$2"; shift 2 ;;
        --local)
            SKILL_LOCAL=true; shift ;;
        --remove-skill)
            REMOVE_SKILL="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run                Show what would be done without making changes"
            echo "  --uninstall              Remove installed symlinks"
            echo "  --skill <path|git-url>   Install an external skill"
            echo "  --local                  Install skill to project .claude/skills/ (with --skill)"
            echo "  --remove-skill <name>    Remove an external skill by name"
            echo "  --help, -h               Show this help"
            exit 0
            ;;
        *) shift ;;
    esac
done

print_header

# --- REMOVE EXTERNAL SKILL ---
if [ -n "$REMOVE_SKILL" ]; then
    SKILLS_DIR="$HOME/.claude/skills"
    target="$SKILLS_DIR/$REMOVE_SKILL"

    # Safety: refuse to remove core skills (symlinks into engine)
    if [ -L "$target" ]; then
        link_target=$(readlink "$target")
        if echo "$link_target" | grep -q "$ENGINE_DIR/.claude/skills/"; then
            echo -e "${RED}ERROR: '$REMOVE_SKILL' is a core skill. Cannot remove.${NC}"
            exit 1
        fi
    fi

    if [ -d "$target" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would remove external skill: ${RED}$REMOVE_SKILL${NC}"
        else
            rm -rf "$target"
            echo -e "  ${GREEN}Removed external skill: $REMOVE_SKILL${NC}"
        fi
    elif [ -L "$target" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would remove external skill symlink: ${RED}$REMOVE_SKILL${NC}"
        else
            rm "$target"
            echo -e "  ${GREEN}Removed external skill: $REMOVE_SKILL${NC}"
        fi
    else
        echo -e "${RED}ERROR: Skill '$REMOVE_SKILL' not found in $SKILLS_DIR${NC}"
        exit 1
    fi
    exit 0
fi

# --- INSTALL EXTERNAL SKILL ---
if [ -n "$SKILL_PATH" ]; then
    SKILL_SRC="$SKILL_PATH"

    # If it's a git URL, clone to a temp dir first
    if echo "$SKILL_SRC" | grep -qE '^(https?://|git@)'; then
        TMPDIR_SKILL=$(mktemp -d)
        echo -e "${BLUE}Cloning skill from $SKILL_SRC...${NC}"
        git clone --depth 1 "$SKILL_SRC" "$TMPDIR_SKILL/skill-repo" 2>/dev/null || {
            echo -e "${RED}ERROR: Failed to clone $SKILL_SRC${NC}"
            rm -rf "$TMPDIR_SKILL"
            exit 1
        }
        # Find the skill dir (root or first subdir with SKILL.md)
        if [ -f "$TMPDIR_SKILL/skill-repo/SKILL.md" ]; then
            SKILL_SRC="$TMPDIR_SKILL/skill-repo"
        else
            FOUND=$(find "$TMPDIR_SKILL/skill-repo" -maxdepth 2 -name "SKILL.md" -print -quit 2>/dev/null)
            if [ -n "$FOUND" ]; then
                SKILL_SRC=$(dirname "$FOUND")
            else
                echo -e "${RED}ERROR: No SKILL.md found in cloned repo${NC}"
                rm -rf "$TMPDIR_SKILL"
                exit 1
            fi
        fi
    fi

    # Resolve to absolute path
    SKILL_SRC=$(cd "$SKILL_SRC" && pwd)

    # Validate SKILL.md exists
    if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
        echo -e "${RED}ERROR: $SKILL_SRC/SKILL.md not found${NC}"
        exit 1
    fi

    # Validate manifest.yaml exists and has required fields
    if [ ! -f "$SKILL_SRC/manifest.yaml" ]; then
        echo -e "${RED}ERROR: $SKILL_SRC/manifest.yaml not found (required for external skills)${NC}"
        exit 1
    fi

    # Check required manifest fields
    MANIFEST_ERRORS=""
    for field in name version author description compatibility; do
        if ! grep -q "^${field}:" "$SKILL_SRC/manifest.yaml"; then
            MANIFEST_ERRORS="${MANIFEST_ERRORS}  missing required field: ${field}\n"
        fi
    done
    if [ -n "$MANIFEST_ERRORS" ]; then
        echo -e "${RED}ERROR: manifest.yaml validation failed:${NC}"
        echo -e "$MANIFEST_ERRORS"
        exit 1
    fi

    SKILL_NAME=$(basename "$SKILL_SRC")

    # Determine target directory
    if [ "$SKILL_LOCAL" = true ]; then
        TARGET_DIR=".claude/skills/$SKILL_NAME"
    else
        TARGET_DIR="$HOME/.claude/skills/$SKILL_NAME"
    fi

    # Check for core skill name collision
    CORE_SKILL="$ENGINE_DIR/.claude/skills/$SKILL_NAME"
    if [ -d "$CORE_SKILL" ]; then
        echo -e "${YELLOW}WARNING: Core skill '$SKILL_NAME' exists. Core takes priority at runtime.${NC}"
    fi

    # Check depends_on (warning only, non-blocking)
    if grep -q "^depends_on:" "$SKILL_SRC/manifest.yaml"; then
        DEPS=$(grep -A 20 "^depends_on:" "$SKILL_SRC/manifest.yaml" | grep "^  - " | sed 's/^  - //')
        SKILLS_DIR_CHECK="$HOME/.claude/skills"
        for dep in $DEPS; do
            if [ ! -d "$SKILLS_DIR_CHECK/$dep" ] && [ ! -d "$ENGINE_DIR/.claude/skills/$dep" ]; then
                echo -e "${YELLOW}WARNING: dependency '$dep' not found (non-blocking)${NC}"
            fi
        done
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would install skill '${GREEN}$SKILL_NAME${NC}' to $TARGET_DIR"
    else
        mkdir -p "$(dirname "$TARGET_DIR")"
        cp -r "$SKILL_SRC" "$TARGET_DIR"
        echo -e "  ${GREEN}Installed external skill: $SKILL_NAME → $TARGET_DIR${NC}"
    fi

    # Cleanup temp dir if used
    [ -n "${TMPDIR_SKILL:-}" ] && rm -rf "$TMPDIR_SKILL"
    exit 0
fi

# --- UNINSTALL ---
if [ "$UNINSTALL" = true ]; then
    echo -e "${YELLOW}Uninstalling SpecBox Engine...${NC}"

    # Remove skills (symlinks)
    SKILLS_DIR="$HOME/.claude/skills"
    for skill_dir in "$ENGINE_DIR"/.claude/skills/*/; do
        [ -d "$skill_dir" ] || continue
        skill_name=$(basename "$skill_dir")
        target="$SKILLS_DIR/$skill_name"
        if [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "  Would remove skill: ${RED}$skill_name${NC}"
            else
                rm "$target"
                echo -e "  Removed skill: ${RED}$skill_name${NC}"
            fi
        fi
    done

    # Remove hooks
    HOOKS_DIR="$HOME/.claude/hooks"
    for hook in "$ENGINE_DIR"/.claude/hooks/*.mjs; do
        [ -f "$hook" ] || continue
        hook_name=$(basename "$hook")
        target="$HOOKS_DIR/$hook_name"
        if [ -f "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "  Would remove hook: ${RED}$hook_name${NC}"
            else
                rm "$target"
                echo -e "  Removed hook: ${RED}$hook_name${NC}"
            fi
        fi
    done
    # Also remove legacy .sh hooks if they exist
    for hook in "$HOOKS_DIR"/*.sh; do
        [ -f "$hook" ] || continue
        hook_name=$(basename "$hook")
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would remove legacy hook: ${RED}$hook_name${NC}"
        else
            rm "$hook"
            echo -e "  Removed legacy hook: ${RED}$hook_name${NC}"
        fi
    done

    echo ""
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}(Dry run - no changes made)${NC}"
    else
        echo -e "${GREEN}Uninstall complete.${NC}"
    fi
    exit 0
fi

# --- INSTALL ---
## --- INSTALL SKILLS (v3.5) ---

SKILLS_DIR="$HOME/.claude/skills"
echo -e "${GREEN}Installing skills to $SKILLS_DIR (symlinks)${NC}"
echo ""

skills_installed=0
skills_updated=0
for skill_dir in "$ENGINE_DIR"/.claude/skills/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    target="$SKILLS_DIR/$skill_name"

    if [ -L "$target" ]; then
        current_target=$(readlink "$target")
        if [ "$current_target" = "$skill_dir" ] || [ "$current_target" = "${skill_dir%/}" ]; then
            continue
        else
            if [ "$DRY_RUN" = true ]; then
                echo -e "  Would update skill: ${YELLOW}$skill_name${NC}"
            else
                rm "$target"
                ln -s "${skill_dir%/}" "$target"
                echo -e "  Updated: ${YELLOW}$skill_name${NC}"
            fi
            skills_updated=$((skills_updated + 1))
        fi
    elif [ -d "$target" ]; then
        # Directory exists (from v3.0 cp -r) — replace with symlink
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would replace dir with symlink: ${YELLOW}$skill_name${NC}"
        else
            rm -rf "$target"
            ln -s "${skill_dir%/}" "$target"
            echo -e "  Migrated to symlink: ${YELLOW}$skill_name${NC}"
        fi
        skills_updated=$((skills_updated + 1))
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "  Would install skill: ${GREEN}$skill_name${NC}"
        else
            mkdir -p "$SKILLS_DIR"
            ln -s "${skill_dir%/}" "$target"
            echo -e "  Installed: ${GREEN}$skill_name${NC}"
        fi
        skills_installed=$((skills_installed + 1))
    fi
done

echo -e "  Skills new: ${GREEN}$skills_installed${NC}, updated: ${YELLOW}$skills_updated${NC}"
echo ""

## --- INSTALL HOOKS (v3.5) ---

HOOKS_DIR="$HOME/.claude/hooks"
if [ -d "$ENGINE_DIR/.claude/hooks" ]; then
    echo -e "${GREEN}Installing hooks to $HOOKS_DIR${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would install hooks to $HOOKS_DIR"
    else
        mkdir -p "$HOOKS_DIR"
        cp "$ENGINE_DIR"/.claude/hooks/*.mjs "$HOOKS_DIR/"
        # Copy shared lib/ directory for hook dependencies
        mkdir -p "$HOOKS_DIR/lib"
        cp "$ENGINE_DIR"/.claude/hooks/lib/*.mjs "$HOOKS_DIR/lib/"
        echo -e "  Hooks installed (Node.js)"
    fi
    echo ""
fi

## --- INSTALL GGA (Gentleman Guardian Angel) ---

echo -e "${GREEN}Checking GGA (cached lint validation)...${NC}"

if command -v gga &>/dev/null; then
    GGA_VERSION=$(gga --version 2>/dev/null || echo "unknown")
    echo -e "  ${GREEN}GGA already installed: $GGA_VERSION${NC}"
else
    echo -e "  ${YELLOW}GGA not found. Installing...${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would run: brew install gentleman-programming/tap/gga"
    else
        # Detect OS and install GGA
        OS_NAME="$(uname -s)"
        case "$OS_NAME" in
            Darwin)
                if command -v brew &>/dev/null; then
                    brew install gentleman-programming/tap/gga 2>/dev/null || {
                        echo -e "  ${RED}Failed to install GGA. Install manually:${NC}"
                        echo -e "    brew install gentleman-programming/tap/gga"
                    }
                else
                    echo -e "  ${YELLOW}Homebrew not found. Install GGA manually:${NC}"
                    echo -e "    # Install Homebrew first: https://brew.sh"
                    echo -e "    brew install gentleman-programming/tap/gga"
                    echo -e "    # Or clone and install:"
                    echo -e "    git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh"
                fi
                ;;
            Linux)
                if command -v brew &>/dev/null; then
                    brew install gentleman-programming/tap/gga 2>/dev/null || {
                        echo -e "  ${RED}Failed to install GGA. Install manually:${NC}"
                        echo -e "    git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh"
                    }
                else
                    echo -e "  ${YELLOW}Install GGA manually:${NC}"
                    echo -e "    git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh"
                fi
                ;;
            MINGW*|MSYS*|CYGWIN*)
                echo -e "  ${YELLOW}Install GGA manually:${NC}"
                echo -e "    git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh"
                ;;
        esac

        if command -v gga &>/dev/null; then
            echo -e "  ${GREEN}GGA installed successfully${NC}"
        fi
    fi
fi

# Install .gga config if target project has none
if [ -f "$ENGINE_DIR/.gga" ] && [ ! -f ".gga" ] && [ "$ENGINE_DIR" != "$(pwd)" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would copy .gga config to project root"
    else
        cp "$ENGINE_DIR/.gga" ".gga"
        echo -e "  ${GREEN}.gga config copied to project root${NC}"
    fi
fi
echo ""

## --- INSTALL SETTINGS (v3.5) ---

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

## --- INSTALL VSCODE EXTENSION (v5.21) ---

echo -e "${GREEN}Installing VSCode extension...${NC}"

if command -v code &>/dev/null || command -v code-insiders &>/dev/null || command -v cursor &>/dev/null; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "  Would install VSCode extension via install-ext.mjs"
    else
        node "$ENGINE_DIR/vscode-extension/install-ext.mjs" --vsix 2>/dev/null || {
            echo -e "  ${YELLOW}VSCode extension not pre-built. Building...${NC}"
            node "$ENGINE_DIR/vscode-extension/install-ext.mjs" 2>/dev/null || {
                echo -e "  ${YELLOW}Auto-install skipped. Install manually:${NC}"
                echo -e "    VSCode → Extensions → Install from VSIX → vscode-extension/specbox-engine-*.vsix"
            }
        }
    fi
else
    echo -e "  ${YELLOW}VSCode CLI not found. Install extension manually if using VSCode.${NC}"
fi
echo ""

## --- COMPATIBILITY SYMLINK (v4.0) ---

echo -e "${GREEN}Creating compatibility symlink...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "  Would create: ~/jps_dev_engine → ~/specbox-engine"
else
    ln -sf ~/specbox-engine ~/jps_dev_engine 2>/dev/null || true
    echo -e "  ${GREEN}~/jps_dev_engine → ~/specbox-engine${NC}"
fi
echo ""

## --- SUMMARY ---

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}(Dry run - no changes made)${NC}"
else
    # Build dynamic hooks list
    HOOK_NAMES=""
    for hook in "$ENGINE_DIR"/.claude/hooks/*.mjs; do
        [ -f "$hook" ] || continue
        name=$(basename "$hook" .mjs)
        # Skip test-hooks from the summary
        [ "$name" = "test-hooks" ] && continue
        if [ -z "$HOOK_NAMES" ]; then
            HOOK_NAMES="$name"
        else
            HOOK_NAMES="$HOOK_NAMES, $name"
        fi
    done

    # Check if VSCode extension was installed
    VSCODE_EXT_STATUS=""
    if command -v code &>/dev/null; then
        if code --list-extensions 2>/dev/null | grep -qi "jpsdeveloper.specbox-engine"; then
            VSCODE_EXT_STATUS="installed"
        fi
    fi

    echo -e "${GREEN}Installation complete.${NC}"
    echo -e "Skills:   /prd, /visual-setup, /plan, /implement, /adapt-ui, /optimize-agents, /quality-gate, /explore, /feedback, /check-designs, /acceptance-check, /quickstart, /remote, /release, /compliance, /audit"
    echo -e "Quality:  quality-first-guard.mjs (read before write), read-tracker.mjs (session tracking)"
    echo -e "Hooks:    $HOOK_NAMES"
    if [ "$VSCODE_EXT_STATUS" = "installed" ]; then
        echo -e "VSCode:   ${GREEN}SpecBox Engine extension installed${NC}"
    else
        echo -e "VSCode:   ${YELLOW}Extension not detected. Install from vscode-extension/specbox-engine-*.vsix${NC}"
    fi
fi
echo ""
