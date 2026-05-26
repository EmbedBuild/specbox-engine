#!/bin/bash
# Tests for scripts/sync-extension-version.sh
# Run from repo root: bash scripts/tests/test-sync-extension-version.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/sync-extension-version.sh"

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; NC=''
fi

PASS=0
FAIL=0

# --- Helper: create a fake repo fixture ---
make_fixture() {
    local fixture_dir="$1"
    local engine_ver="$2"
    local ext_ver="$3"

    mkdir -p "$fixture_dir/vscode-extension" "$fixture_dir/scripts"

    cat > "$fixture_dir/ENGINE_VERSION.yaml" <<EOF
version: $engine_ver
codename: Test Fixture
EOF

    cat > "$fixture_dir/vscode-extension/package.json" <<EOF
{
  "name": "specbox-engine",
  "displayName": "SpecBox Engine",
  "version": "$ext_ver",
  "publisher": "EmbedBuild"
}
EOF

    cat > "$fixture_dir/vscode-extension/package-lock.json" <<EOF
{
  "name": "specbox-engine",
  "version": "$ext_ver",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "specbox-engine",
      "version": "$ext_ver"
    }
  }
}
EOF

    # Symlink the script under test so the fixture uses real script
    ln -sf "$SCRIPT_UNDER_TEST" "$fixture_dir/scripts/sync-extension-version.sh"
}

assert_eq() {
    local label="$1"
    local expected="$2"
    local actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  ${GREEN}✓${NC} $label"
        PASS=$((PASS + 1))
    else
        echo "  ${RED}✗${NC} $label"
        echo "      expected: $expected"
        echo "      got:      $actual"
        FAIL=$((FAIL + 1))
    fi
}

run_test() {
    local test_name="$1"
    echo ""
    echo "${YELLOW}TEST: $test_name${NC}"
}

# --- Test 1: already synced → --check returns 0 ---
run_test "already synced: --check exits 0"
TMPDIR_T1=$(mktemp -d)
trap "rm -rf '$TMPDIR_T1'" EXIT
make_fixture "$TMPDIR_T1" "6.2.0" "6.2.0"
set +e
output=$(cd "$TMPDIR_T1" && bash "$TMPDIR_T1/scripts/sync-extension-version.sh" --check 2>&1)
exit_code=$?
set -e
assert_eq "exit code 0" "0" "$exit_code"
echo "$output" | grep -q "matches engine" && assert_eq "output mentions match" "yes" "yes" || assert_eq "output mentions match" "yes" "no"

# --- Test 2: drift detected → --check returns 1 ---
run_test "drift detected: --check exits 1"
TMPDIR_T2=$(mktemp -d)
trap "rm -rf '$TMPDIR_T1' '$TMPDIR_T2'" EXIT
make_fixture "$TMPDIR_T2" "6.2.0" "5.21.1"
set +e
output=$(cd "$TMPDIR_T2" && bash "$TMPDIR_T2/scripts/sync-extension-version.sh" --check 2>&1)
exit_code=$?
set -e
assert_eq "exit code 1" "1" "$exit_code"
echo "$output" | grep -q "DRIFT" && assert_eq "output mentions DRIFT" "yes" "yes" || assert_eq "output mentions DRIFT" "yes" "no"
echo "$output" | grep -q "6.2.0" && assert_eq "shows engine version" "yes" "yes" || assert_eq "shows engine version" "yes" "no"
echo "$output" | grep -q "5.21.1" && assert_eq "shows extension version" "yes" "yes" || assert_eq "shows extension version" "yes" "no"

# --- Test 3: drift fixed by --write → exit 0, both files updated ---
run_test "drift fixed by --write: writes package.json + package-lock.json"
TMPDIR_T3=$(mktemp -d)
trap "rm -rf '$TMPDIR_T1' '$TMPDIR_T2' '$TMPDIR_T3'" EXIT
make_fixture "$TMPDIR_T3" "6.2.0" "5.21.1"
set +e
output=$(cd "$TMPDIR_T3" && bash "$TMPDIR_T3/scripts/sync-extension-version.sh" --write 2>&1)
exit_code=$?
set -e
assert_eq "exit code 0" "0" "$exit_code"

new_ext_ver=$(python3 -c "import json; print(json.load(open('$TMPDIR_T3/vscode-extension/package.json'))['version'])")
assert_eq "package.json version updated" "6.2.0" "$new_ext_ver"

new_lock_ver=$(python3 -c "import json; print(json.load(open('$TMPDIR_T3/vscode-extension/package-lock.json'))['version'])")
assert_eq "package-lock.json top-level version updated" "6.2.0" "$new_lock_ver"

new_lock_pkg_ver=$(python3 -c "import json; print(json.load(open('$TMPDIR_T3/vscode-extension/package-lock.json'))['packages']['']['version'])")
assert_eq "package-lock.json packages.\"\".version updated" "6.2.0" "$new_lock_pkg_ver"

# Subsequent --check should now pass
set +e
exit_code=$(cd "$TMPDIR_T3" && bash "$TMPDIR_T3/scripts/sync-extension-version.sh" --check >/dev/null 2>&1; echo $?)
set -e
assert_eq "--check after --write exits 0" "0" "$exit_code"

# --- Test 4: --write when already synced is a no-op ---
run_test "already synced: --write is no-op"
TMPDIR_T4=$(mktemp -d)
trap "rm -rf '$TMPDIR_T1' '$TMPDIR_T2' '$TMPDIR_T3' '$TMPDIR_T4'" EXIT
make_fixture "$TMPDIR_T4" "6.2.0" "6.2.0"
set +e
output=$(cd "$TMPDIR_T4" && bash "$TMPDIR_T4/scripts/sync-extension-version.sh" --write 2>&1)
exit_code=$?
set -e
assert_eq "exit code 0" "0" "$exit_code"
echo "$output" | grep -qi "already in sync\|nothing to do" && assert_eq "output mentions no-op" "yes" "yes" || assert_eq "output mentions no-op" "yes" "no"

# --- Test 5: unknown arg → exit 2 ---
run_test "unknown arg: exit 2"
TMPDIR_T5=$(mktemp -d)
trap "rm -rf '$TMPDIR_T1' '$TMPDIR_T2' '$TMPDIR_T3' '$TMPDIR_T4' '$TMPDIR_T5'" EXIT
make_fixture "$TMPDIR_T5" "6.2.0" "6.2.0"
set +e
exit_code=$(cd "$TMPDIR_T5" && bash "$TMPDIR_T5/scripts/sync-extension-version.sh" --bogus 2>/dev/null; echo $?)
set -e
assert_eq "exit code 2" "2" "$exit_code"

# --- Summary ---
echo ""
echo "════════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
    echo "${GREEN}✓ All $PASS assertions passed${NC}"
    exit 0
else
    echo "${RED}✗ $FAIL failed, $PASS passed${NC}"
    exit 1
fi
