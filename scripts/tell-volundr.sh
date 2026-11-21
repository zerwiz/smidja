#!/usr/bin/env bash
# tell-volundr.sh — the arm holder's road to Völundr: one message into his own
# conversation ("arm"), and his answer printed. The viewer must be up (:8437 by default).
#   scripts/tell-volundr.sh "run the nightly scout on <project>"
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: tell-volundr.sh \"<message>\"" >&2; exit 2; }
url="${SMIDJA_VIEWER:-http://127.0.0.1:8437}"
session="${VOLUNDR_SESSION:-arm}"
body=$(python3 -c 'import json,sys; print(json.dumps({"sessionId": sys.argv[1], "content": "[arm] " + sys.argv[2]}))' "$session" "$*")
curl -fsS --max-time "${VOLUNDR_TIMEOUT:-600}" -H 'content-type: application/json' -d "$body" "$url/api/chat/message" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("message") or {}).get("content") or d)'
