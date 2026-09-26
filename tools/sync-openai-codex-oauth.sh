#!/bin/bash
# Load OPENAI_API_KEY from local OpenClaw/Codex OAuth profiles.
# Intended to be sourced by gateway startup scripts.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "sync-openai-codex-oauth: jq is required" >&2
  return 1 2>/dev/null || exit 1
fi

now_ms=$(( $(date +%s) * 1000 ))
min_valid_ms=$(( now_ms + 60000 ))

best_expires=0
best_token=""
best_source=""

decode_jwt_exp_ms() {
  local jwt="$1"
  local payload
  payload="$(printf '%s' "$jwt" | cut -d'.' -f2)"
  [ -n "$payload" ] || return 1

  payload="${payload//-/+}"
  payload="${payload//_/\//}"
  while [ $(( ${#payload} % 4 )) -ne 0 ]; do
    payload="${payload}="
  done

  local exp
  exp="$(printf '%s' "$payload" | base64 -d 2>/dev/null | jq -r '.exp // 0' 2>/dev/null || echo 0)"
  [[ "$exp" =~ ^[0-9]+$ ]] || return 1
  echo $(( exp * 1000 ))
}

load_from_codex_auth() {
  local file="$HOME/.codex/auth.json"
  [ -f "$file" ] || return 0

  # Trigger refresh if possible.
  codex login status >/dev/null 2>&1 || true

  local token expires_int
  token="$(jq -r '.tokens.access_token // empty' "$file" 2>/dev/null || true)"
  [ -n "$token" ] || return 0

  expires_int="$(decode_jwt_exp_ms "$token" || echo 0)"
  if [[ "$expires_int" =~ ^[0-9]+$ ]] && [ "$expires_int" -gt "$best_expires" ]; then
    best_expires="$expires_int"
    best_token="$token"
    best_source="$file"
  fi
}

load_from_file() {
  local file="$1"
  while IFS=$'\t' read -r expires token; do
    [ -z "$token" ] && continue
    local expires_int
    expires_int="${expires%.*}"
    [[ "$expires_int" =~ ^[0-9]+$ ]] || continue

    if [ "$expires_int" -gt "$best_expires" ]; then
      best_expires="$expires_int"
      best_token="$token"
      best_source="$file"
    fi
  done < <(
    jq -r '
      .profiles // {}
      | to_entries[]
      | select(
          .value.provider == "openai-codex"
          and .value.type == "oauth"
          and ((.value.access // "") | type == "string")
        )
      | "\((.value.expires // 0)|tonumber)\t\(.value.access)"
    ' "$file" 2>/dev/null || true
  )
}

load_from_codex_auth

for root in "$HOME/.openclaw" "$HOME/.openclaw-{{ORCHESTRATOR_NAME_LOWER}}"; do
  [ -d "$root" ] || continue
  while IFS= read -r file; do
    load_from_file "$file"
  done < <(find "$root" -type f -path "*/agent/auth-profiles.json" 2>/dev/null)
done

if [ -z "$best_token" ]; then
  echo "sync-openai-codex-oauth: no openai-codex OAuth token found" >&2
  return 1 2>/dev/null || exit 1
fi

if [ "$best_expires" -lt "$min_valid_ms" ]; then
  echo "sync-openai-codex-oauth: token found but expired/near expiry" >&2
  echo "sync-openai-codex-oauth: refresh via codex/openclaw login, then retry" >&2
  return 1 2>/dev/null || exit 1
fi

export OPENAI_API_KEY="$best_token"
export OPENAI_CODEX_OAUTH_SOURCE="$best_source"
export OPENAI_CODEX_OAUTH_EXPIRES_MS="$best_expires"

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "OPENAI_API_KEY loaded from OAuth profile."
  echo "source: $OPENAI_CODEX_OAUTH_SOURCE"
fi
