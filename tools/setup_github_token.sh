#!/bin/bash
# GitHub Token Setup for Huxley
#
# Stores a GitHub personal access token in the macOS Keychain
# (service "github-token", account "huxley") — never in a shell profile,
# never on a command line, never echoed.
#
# "Never on a command line" is literal here, and it takes work: both helpers
# this script calls would otherwise expose the token in the process table.
#   - curl gets the Authorization header through its stdin (-H @-), so its
#     argv is just "-H @-".
#   - security(1)'s -w option takes the password as an argument, so the whole
#     add-generic-password command is fed to security's batch-mode stdin (-i)
#     instead; its argv is just "-i".
# printf is a shell builtin in both pipelines, so it forks no process whose
# arguments could carry the token either, and tracing is switched off before
# the prompt so `bash -x` cannot leak it.
#
# Keeping the token out of argv is not enough on its own: curl also reads
# ~/.curlrc (or $CURL_HOME/.curlrc) before it looks at its own arguments, and
# a `trace`/`trace-ascii`/`dump-header` line there would write the whole
# Authorization header to a file, while `insecure` would drop certificate
# verification. So curl is invoked with -q, which disables that config file
# entirely — and -q only has that effect as the FIRST argument, which is why
# it leads the invocation below. (-q covers the config file, so there is no
# need to fake CURL_HOME/XDG paths as well.)
#
# Usage: ./tools/setup_github_token.sh        (prompts; input is hidden)
#
# Read it back later with:
#   security find-generic-password -s github-token -a huxley -w
# or export it for tools that expect the env var:
#   export GITHUB_TOKEN="$(security find-generic-password -s github-token -a huxley -w)"

set -euo pipefail

# From the prompt on, the token lives in a shell variable; xtrace would print
# every expansion of it. Turn tracing off even if the caller asked for it.
set +x

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This helper uses the macOS Keychain (security(1)) and only runs on macOS." >&2
    exit 1
fi

if [[ $# -gt 0 ]]; then
    echo "Do not pass the token as an argument — it would land in your shell" >&2
    echo "history and the process table. Run with no arguments; you'll be" >&2
    echo "prompted and the input stays hidden." >&2
    exit 1
fi

printf "Paste your GitHub token (input hidden): "
TOKEN=""
if ! IFS= read -rs TOKEN; then
    # read reports failure both at end-of-input (Ctrl-D, or a redirected stdin
    # that ran out) and when the last line had no trailing newline. Only the
    # first case is an error; without this branch 'set -e' would kill the
    # script with no message and no newline.
    if [[ -z "$TOKEN" ]]; then
        echo "" >&2
        echo "Input ended before a token was entered — nothing stored." >&2
        exit 1
    fi
fi
echo ""

if [[ -z "$TOKEN" ]]; then
    echo "No token entered — nothing stored." >&2
    exit 1
fi

# GitHub tokens are ASCII word characters (ghp_..., gho_..., github_pat_...).
# Anything else — whitespace, a quote, a backslash, a stray newline from a
# sloppy paste — would change the meaning of the header line or the security
# command line rather than travelling as part of the token, so refuse it here.
if [[ ! "$TOKEN" =~ ^[A-Za-z0-9_-]{8,255}$ ]]; then
    echo "That does not look like a GitHub token: expected 8-255 characters of" >&2
    echo "letters, digits, underscore or hyphen. Nothing stored. (If your paste" >&2
    echo "picked up a space or a line break, copy the token again.)" >&2
    exit 1
fi

CURL_ERR="$(mktemp "${TMPDIR:-/tmp}/github-token-curl.XXXXXX")"
chmod 600 "$CURL_ERR"
trap 'rm -f "$CURL_ERR"' EXIT

echo "Verifying token against api.github.com..."
set +e
# -q MUST stay first: it is what stops curl reading ~/.curlrc, and curl only
# honours it in that position (see the header note).
HTTP_CODE="$(printf 'Authorization: Bearer %s\n' "$TOKEN" \
    | curl -q -sS -o /dev/null -w '%{http_code}' \
        --connect-timeout 10 --max-time 30 \
        -H @- https://api.github.com/user 2>"$CURL_ERR")"
CURL_STATUS=$?
set -e

# A failed request and a rejected token are different problems with different
# fixes, so they get different messages.
if (( CURL_STATUS != 0 )); then
    echo "Could not reach api.github.com (curl exit $CURL_STATUS) — nothing stored." >&2
    echo "This is a network or TLS problem, not a verdict on your token:" >&2
    sed 's/^/  /' "$CURL_ERR" >&2
    echo "Check your connection (or your proxy) and run this again." >&2
    exit 1
fi

case "$HTTP_CODE" in
    200)
        ;;
    401)
        echo "GitHub rejected the token (HTTP 401) — nothing stored." >&2
        echo "Check that you pasted it whole and that it has not expired or been revoked." >&2
        exit 1
        ;;
    403)
        # A 403 is NOT the same verdict as a 401. GitHub also returns it when
        # you are rate limited (or when a fine-grained token authenticates but
        # is not allowed to read /user), so "expired or revoked" would be a
        # misdiagnosis of a perfectly good credential.
        echo "GitHub refused the request (HTTP 403) — nothing stored." >&2
        echo "Unlike a 401, this is not necessarily a verdict on the token: 403 is" >&2
        echo "also what you get when you are rate limited, or when the token is" >&2
        echo "valid but not permitted to read /user." >&2
        echo "Wait a minute and run this again; if it repeats, check the token's" >&2
        echo "permissions on github.com." >&2
        exit 1
        ;;
    *)
        echo "Unexpected reply from api.github.com (HTTP $HTTP_CODE) — nothing stored." >&2
        echo "Try again in a moment; if it persists, check GitHub's status page." >&2
        exit 1
        ;;
esac

# -U updates the item in place if it already exists. The command goes through
# security's batch stdin so the token is never in its argv.
if ! printf 'add-generic-password -U -s github-token -a huxley -w %s\n' "$TOKEN" | security -i; then
    echo "security(1) failed to write the Keychain item — nothing stored." >&2
    exit 1
fi

# security -i can exit 0 even when its sub-command failed, so read the item
# back and compare instead of trusting the exit status. The value is compared
# inside the shell and never printed.
STORED="$(security find-generic-password -s github-token -a huxley -w 2>/dev/null || true)"
if [[ "$STORED" != "$TOKEN" ]]; then
    echo "The Keychain item does not match the token just entered." >&2
    echo "Add it by hand in Keychain Access: a new application-password item" >&2
    echo "with service 'github-token' and account 'huxley'." >&2
    exit 1
fi

echo "Token stored in the Keychain (service: github-token, account: huxley)."
echo "Note: the check above only proves the token authenticates. It says nothing"
echo "about which repositories or scopes it can reach — this script deliberately"
echo "does not require broader permissions just to pass setup."
echo ""
echo "To use it in the current shell:"
echo '  export GITHUB_TOKEN="$(security find-generic-password -s github-token -a huxley -w)"'
