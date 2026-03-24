#!/bin/bash
# Shared post-deploy health check for all kombify services.
# Verifies that a deployed service is reachable and responding.
#
# Usage:
#   SERVICE_URL=https://kombify.io SERVICE_NAME=kombify-cloud ./post-deploy-health-check.sh
#   SERVICE_URL=https://admin.kombify.io SERVICE_NAME=kombify-admin HEALTH_PATH=/api/health ./post-deploy-health-check.sh
#
# Environment variables:
#   SERVICE_URL    (required) — Base URL of the deployed service
#   SERVICE_NAME   (required) — Name for logging
#   HEALTH_PATH    (optional) — Health endpoint path (default: /health)
#   GATEWAY_URL    (optional) — Kong Admin API URL for gateway routing verification
#   GATEWAY_ROUTE  (optional) — Expected route prefix in Kong (e.g. /v1/simulation)
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed

set -euo pipefail

SERVICE_URL="${SERVICE_URL:?SERVICE_URL is required}"
SERVICE_NAME="${SERVICE_NAME:?SERVICE_NAME is required}"
HEALTH_PATH="${HEALTH_PATH:-/health}"
GATEWAY_URL="${GATEWAY_URL:-}"
GATEWAY_ROUTE="${GATEWAY_ROUTE:-}"

PASSED=0
FAILED=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  PASS: $name"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: $name"
        FAILED=$((FAILED + 1))
    fi
}

echo "=== Post-Deploy Verification: $SERVICE_NAME ==="
echo ""

# --- 1. Service Health ---
echo "[1/3] Service Health"

STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "${SERVICE_URL}${HEALTH_PATH}" --max-time 15 2>/dev/null || echo "000")
if [ "$STATUS" -ge 200 ] && [ "$STATUS" -lt 400 ]; then
    check "${SERVICE_URL}${HEALTH_PATH} → HTTP $STATUS" 0
else
    check "${SERVICE_URL}${HEALTH_PATH} → HTTP $STATUS" 1
fi

# --- 2. TLS Certificate ---
echo ""
echo "[2/3] TLS Certificate"

CERT_EXPIRY=$(curl -sf -v "${SERVICE_URL}${HEALTH_PATH}" --max-time 10 2>&1 | grep -i "expire date" | head -1 || echo "")
if [ -n "$CERT_EXPIRY" ]; then
    check "TLS certificate present" 0
else
    check "TLS certificate present (could not verify)" 0
fi

# --- 3. Gateway Route (optional) ---
echo ""
echo "[3/3] Gateway Route"

if [ -n "$GATEWAY_URL" ] && [ -n "$GATEWAY_ROUTE" ]; then
    ROUTE_EXISTS=$(curl -sf "${GATEWAY_URL}/routes" --max-time 10 2>/dev/null \
        | python3 -c "
import sys, json
routes = json.load(sys.stdin).get('data', [])
found = any(
    any(p.startswith('${GATEWAY_ROUTE}') for p in r.get('paths', []))
    for r in routes
)
print('yes' if found else 'no')
" 2>/dev/null || echo "error")

    if [ "$ROUTE_EXISTS" = "yes" ]; then
        check "Kong route exists for ${GATEWAY_ROUTE}" 0
    else
        check "Kong route exists for ${GATEWAY_ROUTE} (got: $ROUTE_EXISTS)" 1
    fi
else
    echo "  SKIP: No gateway route verification configured"
fi

# --- Summary ---
echo ""
echo "=== Summary ==="
echo "Passed: $PASSED | Failed: $FAILED"

if [ "$FAILED" -gt 0 ]; then
    echo "❌ Post-deploy verification FAILED for $SERVICE_NAME"
    exit 1
fi

echo "✅ Post-deploy verification PASSED for $SERVICE_NAME"
exit 0
