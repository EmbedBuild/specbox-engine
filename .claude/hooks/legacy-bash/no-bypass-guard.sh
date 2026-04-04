#!/usr/bin/env bash
# no-bypass-guard.sh — PreToolUse hook
# BLOCKING: Prevents the agent from accidentally bypassing quality hooks
# or performing destructive git operations.
#
# Context: The human developer using SpecBox is the primary beneficiary
# of quality enforcement. These guardrails exist to protect the AGENT
# from skipping steps due to hallucination, impatience, or error recovery
# shortcuts. The human never needs protection FROM themselves — they are
# the owner of the software and the most interested in its quality.
#
# Blocks:
#   - git commit --no-verify (skips e2e-gate, spec-guard, lint — quality lost)
#   - git push --force / -f (can overwrite shared history by mistake)
#   - git reset --hard (can lose uncommitted work the agent was building)
#
# Why these exist:
#   An LLM agent under pressure (failing tests, healing loops, timeouts)
#   may try shortcuts that sacrifice quality for speed. These guardrails
#   ensure the agent follows the pipeline even when it's "easier" not to.
#
# v5.12.0 — Agent Quality Guardrails

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | grep -oE '"command"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"command"\s*:\s*"//;s/"$//')

if [ -z "$COMMAND" ]; then
  exit 0
fi

BLOCKED=false
REASON=""
GUIDANCE=""

# Check for --no-verify (hook bypass)
if echo "$COMMAND" | grep -q -- '--no-verify'; then
  BLOCKED=true
  REASON="--no-verify skips quality hooks (e2e-gate, spec-guard, lint)."
  GUIDANCE="Fix the issue that the hook is catching instead of bypassing it."
fi

# Check for push --force or push -f (destructive push)
if echo "$COMMAND" | grep -qE 'push\s+.*(-f\b|--force)'; then
  BLOCKED=true
  REASON="Force push can overwrite branch history that other sessions depend on."
  GUIDANCE="Use a new commit to fix the issue instead of rewriting history."
fi

# Check for reset --hard (destructive reset)
if echo "$COMMAND" | grep -q -- 'reset --hard'; then
  BLOCKED=true
  REASON="Hard reset loses uncommitted changes without recovery."
  GUIDANCE="Use 'git stash' to save changes, or commit first, then fix."
fi

if [ "$BLOCKED" = true ]; then
  echo ""
  echo "============================================================"
  echo "  QUALITY GUARD: Operation blocked"
  echo "============================================================"
  echo "  Command: $COMMAND"
  echo "  Why: $REASON"
  echo "  Instead: $GUIDANCE"
  echo "============================================================"
  echo ""
  exit 1
fi

exit 0
