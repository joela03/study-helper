#!/usr/bin/env bash
# Mint an invite code. Prompts for the password so it stays out of history.
#
#   ./scripts/invite.sh                      one use, no expiry
#   ./scripts/invite.sh "cohort" 20 30       note, 20 uses, expires in 30 days
#   ./scripts/invite.sh --list               show existing codes
set -euo pipefail

API="${API:-http://localhost:8000}"

# Prompt rather than defaulting to any particular address — this repo is
# public, and the admin account differs between local and deployed anyway.
EMAIL="${STUDY_HELPER_EMAIL:-}"
if [ -z "$EMAIL" ]; then
  printf 'Admin email: ' >&2
  read -r EMAIL
fi

printf 'Password for %s: ' "$EMAIL" >&2
read -rs PASSWORD
printf '\n' >&2

RESPONSE=$(curl -s -X POST "$API/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' "$EMAIL" "$PASSWORD")")

TOKEN=$(printf '%s' "$RESPONSE" | python3 -c '
import json,sys
d=json.load(sys.stdin)
if "access_token" not in d:
    sys.exit("Login failed: " + str(d.get("detail","unknown error")))
print(d["access_token"])
') || exit 1

if [ "${1:-}" = "--list" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "$API/api/auth/invites" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
if not rows: print("No invite codes yet."); raise SystemExit
print(f"{"CODE":12} {"USED":7} {"ACTIVE":7} {"EXPIRES":12} NOTE")
for i in rows:
    exp=(i["expires_at"] or "never")[:10]
    print(f"{i["code"]:12} {str(i["uses"])+"/"+str(i["max_uses"]):7} {str(i["is_active"]):7} {exp:12} {i["note"] or ""}")
'
  exit 0
fi

NOTE="${1:-}"; USES="${2:-1}"; DAYS="${3:-}"

BODY=$(python3 -c '
import json,sys
note,uses,days=sys.argv[1],int(sys.argv[2]),sys.argv[3]
d={"max_uses":uses}
if note: d["note"]=note
if days: d["expires_in_days"]=int(days)
print(json.dumps(d))
' "$NOTE" "$USES" "$DAYS")

curl -s -X POST "$API/api/auth/invites" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "$BODY" | python3 -c '
import json,sys
d=json.load(sys.stdin)
if "code" not in d: sys.exit("Failed: " + str(d.get("detail", d)))
print()
print("  Invite code:", d["code"])
print("  Uses:       ", f"{d["uses"]}/{d["max_uses"]}")
print("  Expires:    ", (d["expires_at"] or "never")[:10])
if d["note"]: print("  For:        ", d["note"])
print()
'
