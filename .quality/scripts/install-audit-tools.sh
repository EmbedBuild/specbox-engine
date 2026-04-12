#!/usr/bin/env bash
# install-audit-tools.sh — lazy installer for SpecBox Quality Audit external tools.
#
# Usage:
#   ./install-audit-tools.sh              # interactive, asks before each install
#   ./install-audit-tools.sh --yes        # non-interactive, install everything missing
#   ./install-audit-tools.sh --check      # only report status, install nothing
#
# Only invoked on-demand by the /audit skill, never during install.sh / upgrade.

set -euo pipefail

YES=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    --check) CHECK_ONLY=1 ;;
    --help|-h)
      sed -n '2,10p' "$0" | sed 's/^# //;s/^#//'
      exit 0 ;;
  esac
done

OS="$(uname -s)"
is_macos() { [[ "$OS" == "Darwin" ]]; }

have() { command -v "$1" >/dev/null 2>&1; }

prompt_install() {
  local tool="$1" cmd="$2"
  if [[ $CHECK_ONLY -eq 1 ]]; then
    echo "  [missing] $tool  (would run: $cmd)"
    return 1
  fi
  if [[ $YES -eq 1 ]]; then
    echo "  [install] $tool"
    eval "$cmd"
    return $?
  fi
  read -r -p "  Install $tool? [$cmd] (y/N) " ans
  case "$ans" in
    y|Y|yes) eval "$cmd" ;;
    *) echo "    skipped"; return 1 ;;
  esac
}

echo "SpecBox Quality Audit — external tools check"
echo "OS: $OS"
echo

MISSING=0
INSTALLED=0

check_tool() {
  local tool="$1" installer="$2" purpose="$3"
  if have "$tool"; then
    echo "  [ok]      $tool — $purpose"
    INSTALLED=$((INSTALLED + 1))
  else
    MISSING=$((MISSING + 1))
    if prompt_install "$tool" "$installer"; then
      INSTALLED=$((INSTALLED + 1))
    fi
  fi
}

# --- Python-based tools (installed via uv pip if available, else pip)
PY_INSTALLER="pip install"
if have uv; then
  PY_INSTALLER="uv pip install"
fi

check_tool "semgrep"  "$PY_INSTALLER semgrep"   "SAST OWASP Top 10"
check_tool "pip-audit" "$PY_INSTALLER pip-audit" "Python dep vulns"
check_tool "lizard"   "$PY_INSTALLER lizard"    "Cyclomatic complexity"
check_tool "checkov"  "$PY_INSTALLER checkov"   "IaC security"

# --- gitleaks (OS-specific)
if is_macos; then
  GITLEAKS_INSTALL="brew install gitleaks"
else
  GITLEAKS_INSTALL="go install github.com/gitleaks/gitleaks/v8@latest"
fi
check_tool "gitleaks" "$GITLEAKS_INSTALL" "Secret scanning"

# --- jscpd (npm, optional)
check_tool "jscpd"    "npm install -g jscpd"   "Code duplication"

echo
echo "Summary: $INSTALLED present, $MISSING missing."
if [[ $CHECK_ONLY -eq 1 && $MISSING -gt 0 ]]; then
  echo "Run without --check to install them."
  exit 2
fi
exit 0
