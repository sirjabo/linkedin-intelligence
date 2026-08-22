#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://api-production-fd73.up.railway.app}"
EMAIL="smoketest-$(date +%s)@example.com"
PASSWORD="Test1234x"

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; }
section() { echo; echo "── $1 ──────────────────────────────"; }

section "1. Health"
HEALTH=$(curl -sf "$BASE/health")
echo "  $HEALTH"
echo "$HEALTH" | grep -q '"ok"' && pass "health ok" || { fail "health no ok"; exit 1; }

section "2. Register  ($EMAIL)"
REGISTER=$(curl -s -o /tmp/register.json -w "%{http_code}" -X POST "$BASE/api/v2/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "  HTTP $REGISTER  $(cat /tmp/register.json)"
[[ "$REGISTER" == "201" || "$REGISTER" == "200" ]] && pass "register" || fail "register (HTTP $REGISTER)"

section "3. Login"
LOGIN=$(curl -s -o /tmp/login.json -w "%{http_code}" -X POST "$BASE/api/v2/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "  HTTP $LOGIN  $(cat /tmp/login.json)"
TOKEN=$(cat /tmp/login.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] && pass "login — token OK" || { fail "login — no token"; exit 1; }

section "4. Create Candidate Profile"
PROFILE=$(curl -s -o /tmp/profile.json -w "%{http_code}" -X PUT "$BASE/api/v2/candidates/me" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Smoke Test User",
    "email": "'"$EMAIL"'",
    "location": "Buenos Aires",
    "title": "Backend Engineer",
    "years_experience": 5,
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "languages": [{"language": "Spanish", "level": "native"}]
  }')
echo "  HTTP $PROFILE  $(cat /tmp/profile.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id','') or d.get('detail',''))" 2>/dev/null)"
[[ "$PROFILE" == "200" || "$PROFILE" == "201" ]] && pass "candidate profile" || fail "candidate profile (HTTP $PROFILE)"

section "5. Create Job"
JOB=$(curl -s -o /tmp/job.json -w "%{http_code}" -X POST "$BASE/api/v2/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "raw_jd": "We need a Python expert with 5+ years experience in FastAPI and PostgreSQL. Must have strong SQL skills. Remote-friendly team building scalable APIs.",
    "job_url": "https://example.com/jobs/1"
  }')
JOB_ID=$(cat /tmp/job.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")
echo "  HTTP $JOB  job_id=$JOB_ID"
[[ "$JOB" == "200" || "$JOB" == "201" ]] && pass "job created" || fail "job (HTTP $JOB)"

section "6. Match"
if [[ -n "$JOB_ID" ]]; then
  MATCH=$(curl -s -o /tmp/match.json -w "%{http_code}" -X POST "$BASE/api/v2/match" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"job_id\":\"$JOB_ID\"}")
  SCORE=$(cat /tmp/match.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('overall_score', d.get('score','?')))" 2>/dev/null || echo "?")
  echo "  HTTP $MATCH  score=$SCORE"
  [[ "$MATCH" == "200" || "$MATCH" == "201" ]] && pass "match (score=$SCORE)" || fail "match (HTTP $MATCH)"
else
  fail "match — skipped (no job_id)"
fi

section "7. Create Application (no submit)"
if [[ -n "$JOB_ID" ]]; then
  APP=$(curl -s -o /tmp/app.json -w "%{http_code}" -X POST "$BASE/api/v2/applications" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"job_id\":\"$JOB_ID\"}")
  APP_ID=$(cat /tmp/app.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")
  echo "  HTTP $APP  app_id=$APP_ID"
  [[ "$APP" == "200" || "$APP" == "201" ]] && pass "application created" || fail "application (HTTP $APP)"
else
  fail "application — skipped (no job_id)"
fi

section "8. Frontend shell"
FRONTEND="${FRONTEND:-https://frontend-v2-production-a1c0.up.railway.app}"
FE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND/")
echo "  HTTP $FE_STATUS  $FRONTEND/"
[[ "$FE_STATUS" == "200" ]] && pass "frontend loads" || fail "frontend (HTTP $FE_STATUS)"

section "9. Frontend API rewrite (same-origin fallback)"
FE_API=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND/api/v2/auth/login" \
  -X POST -H "Content-Type: application/json" -d '{"email":"x","password":"y"}')
echo "  HTTP $FE_API  (expect 401/422 — proxy reachable, not 404)"
[[ "$FE_API" != "404" ]] && pass "frontend /api/v2 proxy reachable" || fail "frontend /api/v2 returns 404"

echo
echo "══════════════════════════════════════"
echo "  Smoke test complete"
echo "══════════════════════════════════════"
