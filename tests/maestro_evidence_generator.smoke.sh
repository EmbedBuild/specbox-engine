#!/usr/bin/env bash
# Smoke test for .quality/scripts/maestro-evidence-generator.js
#
# - Runs the generator against tests/fixtures/maestro/ (3 ACs, 1 failure)
# - Validates resulting results.json against the SpecBox contract
# - Asserts HTML contains expected markers (Maestro source, AC ids, base64 imgs)
# - Cleans up tmp output on success
#
# Usage: bash tests/maestro_evidence_generator.smoke.sh
# Exit code 0 = pass, non-zero = fail. Designed for CI invocation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GENERATOR=".quality/scripts/maestro-evidence-generator.js"
VALIDATOR=".quality/scripts/validate-results-json.js"
FIXTURES="tests/fixtures/maestro"
OUT_DIR="$(mktemp -d -t maestro-smoke.XXXXXX)"
OUT_HTML="$OUT_DIR/e2e-evidence-report.html"
OUT_JSON="$OUT_DIR/results.json"

cleanup() { rm -rf "$OUT_DIR"; }
trap cleanup EXIT

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -f "$GENERATOR" ]  || fail "Generator not found: $GENERATOR"
[ -f "$VALIDATOR" ]  || fail "Validator not found: $VALIDATOR"
[ -d "$FIXTURES" ]   || fail "Fixtures not found: $FIXTURES"

echo "→ Running maestro-evidence-generator on fixtures..."
node "$GENERATOR" \
  --uc-id UC-001 \
  --us-id US-01 \
  --feature crear_propiedad \
  --junit "$FIXTURES/results.xml" \
  --screenshots "$FIXTURES" \
  --output "$OUT_HTML" >/dev/null

[ -f "$OUT_HTML" ] || fail "HTML output not generated"
[ -f "$OUT_JSON" ] || fail "results.json not generated alongside HTML"

# --- Assert results.json shape ---
echo "→ Validating results.json against SpecBox contract..."
node "$VALIDATOR" "$OUT_JSON" --check-evidence >/dev/null \
  || fail "results.json failed validate-results-json.js (--check-evidence)"

# --- Assert specific fields via node one-liner (no jq required) ---
node -e "
  const j = JSON.parse(require('fs').readFileSync('$OUT_JSON', 'utf-8'));
  const errs = [];
  if (j.source !== 'maestro-junit-xml') errs.push('source != maestro-junit-xml: ' + j.source);
  if (j.stack !== 'flutter-mobile')     errs.push('stack != flutter-mobile: ' + j.stack);
  if (j.evidence_type !== 'screenshot') errs.push('evidence_type != screenshot');
  if (j.tests_total !== 3)              errs.push('tests_total != 3: ' + j.tests_total);
  if (j.tests_passed !== 2)             errs.push('tests_passed != 2: ' + j.tests_passed);
  if (j.tests_failed !== 1)             errs.push('tests_failed != 1: ' + j.tests_failed);
  if (j.uc_id !== 'UC-001')             errs.push('uc_id != UC-001');
  if (j.results.length !== 3)           errs.push('results.length != 3');
  const failed = j.results.filter(r => r.status === 'FAIL');
  if (failed.length !== 1)              errs.push('expected 1 failed result, got ' + failed.length);
  if (failed[0] && failed[0].id !== 'AC-02') errs.push('failed AC should be AC-02, got ' + failed[0].id);
  if (failed[0] && !failed[0].error)    errs.push('failed AC must carry error message');
  const ac01 = j.results.find(r => r.id === 'AC-01');
  if (!ac01 || !ac01.evidence)          errs.push('AC-01 must have screenshot evidence');
  if (errs.length) { console.error(errs.join('\\n')); process.exit(1); }
" || fail "results.json field assertions failed"

# --- Assert HTML markers ---
echo "→ Asserting HTML markers..."
grep -q '<!DOCTYPE html>' "$OUT_HTML" || fail "HTML missing DOCTYPE"
grep -q 'UC-001'                 "$OUT_HTML" || fail "HTML missing UC-001 reference"
grep -q 'AC-01'                  "$OUT_HTML" || fail "HTML missing AC-01 card"
grep -q 'AC-02'                  "$OUT_HTML" || fail "HTML missing AC-02 card"
grep -q 'AC-03'                  "$OUT_HTML" || fail "HTML missing AC-03 card"
grep -q 'Maestro'                "$OUT_HTML" || fail "HTML must label source as Maestro"
grep -q 'Pass Rate'              "$OUT_HTML" || fail "HTML missing Pass Rate section"
grep -q 'data:image/png;base64'  "$OUT_HTML" || fail "HTML must embed base64 PNGs"
grep -q 'PASS'                   "$OUT_HTML" || fail "HTML must contain PASS badges"
grep -q 'FAIL'                   "$OUT_HTML" || fail "HTML must contain FAIL badges (1 failure expected)"

# Minimum size: 1KB enforced by validator anyway, but assert here too
SIZE=$(wc -c <"$OUT_HTML")
[ "$SIZE" -gt 4096 ] || fail "HTML report too small ($SIZE bytes), expected >4KB"

echo "PASS — maestro-evidence-generator smoke test"
echo "  output: $OUT_HTML"
echo "  results.json: $OUT_JSON"
echo "  size: $SIZE bytes"
