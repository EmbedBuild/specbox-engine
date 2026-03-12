#!/usr/bin/env bash
# design-baseline.sh — Measure design compliance for ratchet enforcement
# Usage: .quality/scripts/design-baseline.sh [path] [--update]
#
# Scans presentation/pages/ files and doc/design/ directories to measure
# design compliance. Outputs JSON compatible with quality-baseline.json.
#
# Modes:
#   (no flag)   — Print current metrics to stdout
#   --update    — Update baseline (ratchet: only improves, never regresses)
#   --init      — Create initial baseline (overwrites existing)

set -euo pipefail

PROJECT_ROOT="${1:-.}"
MODE="${2:---report}"

# Detect stack
detect_pages_dir() {
  if [ -d "$PROJECT_ROOT/lib/presentation" ]; then
    echo "lib/presentation"  # Flutter
  elif [ -d "$PROJECT_ROOT/src/pages" ]; then
    echo "src/pages"  # React/Next pages dir
  elif [ -d "$PROJECT_ROOT/app" ] && find "$PROJECT_ROOT/app" -name "page.tsx" -o -name "page.ts" 2>/dev/null | head -1 | grep -q .; then
    echo "app"  # Next.js App Router
  else
    echo ""
  fi
}

PAGES_DIR=$(detect_pages_dir)

# Count features with UI (directories in doc/design/)
FEATURES_WITH_DESIGN=0
if [ -d "$PROJECT_ROOT/doc/design" ]; then
  FEATURES_WITH_DESIGN=$(find "$PROJECT_ROOT/doc/design" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
fi

# Count total HTML designs
TOTAL_HTMLS=0
if [ -d "$PROJECT_ROOT/doc/design" ]; then
  TOTAL_HTMLS=$(find "$PROJECT_ROOT/doc/design" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
fi

# Count presentation pages
PAGES_TOTAL=0
PAGES_WITH_TRACEABILITY=0
PAGES_WITHOUT_TRACEABILITY=0
PAGES_LEGACY=0

if [ -n "$PAGES_DIR" ]; then
  # Find all page files
  PAGE_FILES=$(find "$PROJECT_ROOT/$PAGES_DIR" -type f \( -name "*.dart" -o -name "*.tsx" -o -name "*.ts" -o -name "*.jsx" -o -name "*.py" \) 2>/dev/null | grep -iE '(page|screen|view)' || true)

  if [ -n "$PAGE_FILES" ]; then
    PAGES_TOTAL=$(echo "$PAGE_FILES" | wc -l | tr -d ' ')

    while IFS= read -r f; do
      if head -5 "$f" | grep -q "Generated from: doc/design/"; then
        PAGES_WITH_TRACEABILITY=$((PAGES_WITH_TRACEABILITY + 1))
      fi
    done <<< "$PAGE_FILES"

    PAGES_WITHOUT_TRACEABILITY=$((PAGES_TOTAL - PAGES_WITH_TRACEABILITY))
  fi
fi

# Calculate compliance rate
COMPLIANCE_RATE=0
if [ "$PAGES_TOTAL" -gt 0 ]; then
  COMPLIANCE_RATE=$((PAGES_WITH_TRACEABILITY * 100 / PAGES_TOTAL))
fi

# Count features by compliance status
COMPLIANT=0
PARTIAL=0
MISSING=0

if [ -d "$PROJECT_ROOT/doc/plans" ]; then
  for plan in "$PROJECT_ROOT"/doc/plans/*_plan.md; do
    [ -f "$plan" ] || continue
    FEATURE=$(basename "$plan" _plan.md | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    DESIGN_DIR="$PROJECT_ROOT/doc/design/$FEATURE"
    HTML_COUNT=0
    if [ -d "$DESIGN_DIR" ]; then
      HTML_COUNT=$(find "$DESIGN_DIR" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Check stitch_designs field in plan
    STITCH_STATUS=$(grep -oP 'stitch_designs:\s*\K\w+' "$plan" 2>/dev/null || echo "NOT_SET")

    if [ "$HTML_COUNT" -gt 0 ]; then
      # Check if pages have traceability
      FEATURE_PAGES=$(find "$PROJECT_ROOT/$PAGES_DIR" -path "*$FEATURE*" -type f \( -name "*.dart" -o -name "*.tsx" \) 2>/dev/null || true)
      if [ -n "$FEATURE_PAGES" ]; then
        ALL_TRACED=true
        while IFS= read -r fp; do
          if ! head -5 "$fp" | grep -q "Generated from:"; then
            ALL_TRACED=false
            break
          fi
        done <<< "$FEATURE_PAGES"
        if $ALL_TRACED; then
          COMPLIANT=$((COMPLIANT + 1))
        else
          PARTIAL=$((PARTIAL + 1))
        fi
      else
        COMPLIANT=$((COMPLIANT + 1))  # Has designs, no pages yet = compliant
      fi
    else
      MISSING=$((MISSING + 1))
    fi
  done
fi

# Determine enforcement level based on compliance rate
if [ "$COMPLIANCE_RATE" -ge 80 ]; then
  ENFORCEMENT="L2"
elif [ "$COMPLIANCE_RATE" -ge 30 ]; then
  ENFORCEMENT="L1"
else
  ENFORCEMENT="L0"
fi

# Output JSON
cat <<EOF
{
  "designCompliance": {
    "totalFeaturesWithUI": $((COMPLIANT + PARTIAL + MISSING)),
    "compliant": $COMPLIANT,
    "partial": $PARTIAL,
    "missing": $MISSING,
    "legacy": $PAGES_WITHOUT_TRACEABILITY,
    "pagesTotal": $PAGES_TOTAL,
    "pagesWithTraceability": $PAGES_WITH_TRACEABILITY,
    "complianceRate": $COMPLIANCE_RATE,
    "designsTotal": $TOTAL_HTMLS,
    "featuresWithDesigns": $FEATURES_WITH_DESIGN,
    "policy": "ratchet",
    "ratchetDirection": "up",
    "enforcementLevel": "$ENFORCEMENT",
    "measuredAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF

# Ratchet check if --update
if [ "$MODE" = "--update" ]; then
  BASELINE_FILE="$PROJECT_ROOT/.quality/baselines/$(basename "$PROJECT_ROOT").json"
  if [ -f "$BASELINE_FILE" ]; then
    PREV_RATE=$(python3 -c "import json; d=json.load(open('$BASELINE_FILE')); print(d.get('designCompliance',{}).get('complianceRate',0))" 2>/dev/null || echo 0)
    if [ "$COMPLIANCE_RATE" -lt "$PREV_RATE" ]; then
      echo "❌ RATCHET VIOLATION: Design compliance dropped from ${PREV_RATE}% to ${COMPLIANCE_RATE}%"
      echo "   New code must not reduce design compliance."
      exit 1
    else
      echo "✅ Design compliance: ${PREV_RATE}% → ${COMPLIANCE_RATE}% (ratchet OK)"
    fi
  fi
fi
