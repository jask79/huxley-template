#!/bin/bash
# Huxley Template — First-Time Setup
# Replaces {{PLACEHOLDER}} tokens with your personal values

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CATALYST_ROOT="$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONFIG_FILE="$CATALYST_ROOT/.catalyst-config"
AGENTS_MD_LIMIT=10000   # characters; AGENTS.md must stay under this for agent-CLI compatibility

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Huxley Framework — First-Time Setup ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ─── Answer validation ──────────────────────────────────────────────────────
# Every answer below is substituted verbatim into JSON, YAML, Python, shell and
# Markdown files across the whole tree. The sed escaping further down protects
# sed's own syntax only — it cannot protect the *destination* format, so a
# double quote, backslash, newline or control character would still corrupt the
# file it lands in (an orchestrator name of  Atlas "Prime"  produces an invalid
# .claude-context/index.json). Values are therefore constrained at the prompt:
# anything outside the charsets below is rejected and asked again, and the same
# rules are re-checked against a saved .catalyst-config in --apply mode.
#
# NAME_RE covers your name, the orchestrator name, the assistant name and the
# example brand. Deliberately no quotes, backslashes, braces or control chars.
NAME_RE=$'^[A-Za-z0-9 ._\'-]{1,40}$'
NAME_HINT="letters, digits, space, apostrophe, hyphen, period or underscore (max 40 characters)"

# A plausible address, and never one carrying a quote or a backslash.
EMAIL_RE='^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}$'
EMAIL_HINT="an address like you@example.com (no quotes or backslashes)"

# GitHub's own rule: 1–39 alphanumerics or hyphens, not starting or ending
# with a hyphen.
GITHUB_USER_RE='^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$'
GITHUB_USER_HINT="1–39 letters, digits or hyphens; cannot start or end with a hyphen"

# Telegram bot usernames are [A-Za-z0-9_]; the value is substituted into JSON
# and YAML alongside the names, so it gets the same treatment.
BOT_USERNAME_RE='^[A-Za-z0-9_]{1,64}$'
BOT_USERNAME_HINT="letters, digits and underscores only, without the @"

# Telegram chat IDs are integers; group and channel ids are negative.
TELEGRAM_CHAT_ID_RE='^-?[0-9]{1,20}$'
TELEGRAM_CHAT_ID_HINT="digits only, optionally with a leading minus"

# A host label as it appears in SSH configs, tmux session names and log paths.
MACHINE_HOST_RE='^[A-Za-z0-9.-]{1,64}$'
MACHINE_HOST_HINT="letters, digits, periods and hyphens (max 64 characters)"

# Declared up front so both the interactive path (which fills them through
# ask/ask_optional) and the --apply path (which sources them) end up with the
# same set of names defined under 'set -u'.
USER_NAME=""
ORCHESTRATOR_NAME=""
ASSISTANT_NAME=""
USER_EMAIL=""
GITHUB_USER=""
BOT_USERNAME=""
TELEGRAM_CHAT_ID=""
MACHINE_HOST=""
EXAMPLE_BRAND=""

# ask <var-name> <prompt> <regex> <hint> [default]
# Reads an answer and re-prompts until it matches <regex>. An empty answer
# takes <default>; with no default an empty answer is refused. Input ending
# (Ctrl-D, or a redirected stdin that ran out) stops the script instead of
# looping forever.
ask() {
    local __var="$1" __prompt="$2" __re="$3" __hint="$4" __default="${5-}"
    local __ans
    while : ; do
        if ! IFS= read -r -p "$__prompt" __ans; then
            echo "" >&2
            echo -e "${RED}Input ended before this question was answered — nothing was changed.${NC}" >&2
            exit 1
        fi
        if [[ -z "$__ans" && -n "$__default" ]]; then
            __ans="$__default"
        fi
        if [[ -z "$__ans" ]]; then
            echo -e "${RED}This answer is required.${NC}"
            continue
        fi
        if [[ "$__ans" =~ $__re ]]; then
            printf -v "$__var" '%s' "$__ans"
            return 0
        fi
        echo -e "${RED}Not accepted — use $__hint.${NC}"
    done
}

# ask_optional <var-name> <prompt> <regex> <hint>
# Same, but an empty answer is accepted and leaves the variable empty.
ask_optional() {
    local __var="$1" __prompt="$2" __re="$3" __hint="$4"
    local __ans
    while : ; do
        if ! IFS= read -r -p "$__prompt" __ans; then
            echo "" >&2
            echo -e "${RED}Input ended before this question was answered — nothing was changed.${NC}" >&2
            exit 1
        fi
        if [[ -z "$__ans" ]]; then
            printf -v "$__var" '%s' ""
            return 0
        fi
        if [[ "$__ans" =~ $__re ]]; then
            printf -v "$__var" '%s' "$__ans"
            return 0
        fi
        echo -e "${RED}Not accepted — use $__hint. Press Enter to skip.${NC}"
    done
}

# Suggested machine label, narrowed to the host charset so the suggestion
# itself always passes validation.
DEFAULT_HOST="$( { hostname -s 2>/dev/null || true; } | tr -cd 'A-Za-z0-9.-' )"
DEFAULT_HOST="${DEFAULT_HOST:-localhost}"

# .catalyst-config is written by this script as KEY=<printf %q value> lines.
# Before sourcing it back, verify every line is exactly that shape: a known
# key, then a value in one of the three forms printf %q emits (bare-safe
# characters, backslash escapes, $'...'; plain '...' also accepted). A file
# carrying anything else — a hand-edit, corruption, an old unescaped format —
# is refused instead of executed.
CONFIG_KEYS='USER_NAME|ORCHESTRATOR_NAME|ASSISTANT_NAME|USER_EMAIL|GITHUB_USER|BOT_USERNAME|TELEGRAM_CHAT_ID|MACHINE_HOST|USER_LOGIN|CLAUDE_PROJECT_SLUG|EXAMPLE_BRAND'
Q="'"
CONFIG_VALUE_RE="(\\\$${Q}([^${Q}\\\\]|\\\\.)*${Q}|${Q}[^${Q}]*${Q}|([A-Za-z0-9,._+:@%/=~#-]|\\\\.)*)"
config_file_ok() {
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" == '#'* ]] && continue
        [[ "$line" =~ ^($CONFIG_KEYS)=$CONFIG_VALUE_RE$ ]] || return 1
    done < "$1"
    return 0
}

# Check for --apply mode (re-apply saved config)
if [[ "${1:-}" == "--apply" ]]; then
    if [[ -f "$CONFIG_FILE" ]]; then
        if ! config_file_ok "$CONFIG_FILE"; then
            echo -e "${RED}.catalyst-config contains a line this script did not write.${NC}"
            echo -e "${RED}Refusing to apply it. Re-run ./setup.sh (no --apply) to regenerate it.${NC}"
            exit 1
        fi
        echo -e "${GREEN}Re-applying saved configuration from .catalyst-config${NC}"
        # shellcheck source=/dev/null
        source "$CONFIG_FILE"
    else
        echo -e "${RED}No .catalyst-config found. Run setup.sh without --apply first.${NC}"
        exit 1
    fi
else
    # Interactive prompts
    echo -e "${YELLOW}This script will personalize your Huxley installation.${NC}"
    echo -e "${YELLOW}Your choices are saved to .catalyst-config for future updates.${NC}"
    echo ""
    echo -e "${YELLOW}Names go straight into JSON, YAML and source files, so they are${NC}"
    echo -e "${YELLOW}limited to $NAME_HINT.${NC}"
    echo ""

    ask USER_NAME "Your name (e.g., Alex): " "$NAME_RE" "$NAME_HINT"

    ask ORCHESTRATOR_NAME "Orchestrator name — your AI chief-of-staff (e.g., Atlas): " \
        "$NAME_RE" "$NAME_HINT"

    ask ASSISTANT_NAME "Assistant name for SOUL.md (default: $ORCHESTRATOR_NAME): " \
        "$NAME_RE" "$NAME_HINT" "$ORCHESTRATOR_NAME"

    ask_optional USER_EMAIL "Your email (optional, for tool configs): " \
        "$EMAIL_RE" "$EMAIL_HINT"

    ask_optional GITHUB_USER "GitHub username (optional): " \
        "$GITHUB_USER_RE" "$GITHUB_USER_HINT"

    echo ""
    echo -e "${BLUE}Telegram Integration (optional — press Enter to skip)${NC}"
    echo "If your orchestrator has a Telegram bot, enter its username."
    echo "This is used to auto-create capsule groups and notifications."
    ask_optional BOT_USERNAME "Bot username (e.g. MyOrchestratorBot, without @): " \
        "$BOT_USERNAME_RE" "$BOT_USERNAME_HINT"

    ask_optional TELEGRAM_CHAT_ID "Telegram chat ID (optional, your personal chat with the bot): " \
        "$TELEGRAM_CHAT_ID_RE" "$TELEGRAM_CHAT_ID_HINT"

    echo ""
    ask MACHINE_HOST "Machine host label (default: $DEFAULT_HOST): " \
        "$MACHINE_HOST_RE" "$MACHINE_HOST_HINT" "$DEFAULT_HOST"

    echo ""
    echo "Three shipped media tools send an HTTP-Referer header for API attribution;"
    echo "this value becomes that header's hostname (cosmetic only — Keychain"
    echo "credentials always live under the fixed account name 'huxley')."
    echo "Letters, digits and underscores are kept; anything else is dropped."
    ask EXAMPLE_BRAND "Example brand name (default: ExampleBrand): " \
        "$NAME_RE" "$NAME_HINT" "ExampleBrand"

    # Derived values
    USER_LOGIN="$(whoami)"
    CLAUDE_PROJECT_SLUG="${CATALYST_ROOT//\//-}"

    # Save config. Every value is serialized with printf %q so a crafted
    # answer can never execute when the file is sourced back on --apply, and
    # quotes, spaces and backslashes round-trip exactly.
    {
        printf 'USER_NAME=%q\n'            "$USER_NAME"
        printf 'ORCHESTRATOR_NAME=%q\n'    "$ORCHESTRATOR_NAME"
        printf 'ASSISTANT_NAME=%q\n'       "$ASSISTANT_NAME"
        printf 'USER_EMAIL=%q\n'           "$USER_EMAIL"
        printf 'GITHUB_USER=%q\n'          "$GITHUB_USER"
        printf 'BOT_USERNAME=%q\n'         "$BOT_USERNAME"
        printf 'TELEGRAM_CHAT_ID=%q\n'     "$TELEGRAM_CHAT_ID"
        printf 'MACHINE_HOST=%q\n'         "$MACHINE_HOST"
        printf 'USER_LOGIN=%q\n'           "$USER_LOGIN"
        printf 'CLAUDE_PROJECT_SLUG=%q\n'  "$CLAUDE_PROJECT_SLUG"
        printf 'EXAMPLE_BRAND=%q\n'        "$EXAMPLE_BRAND"
    } > "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo -e "${GREEN}Configuration saved to .catalyst-config${NC}"
fi

# ASSISTANT_NAME was added after the earliest template builds, so a saved
# config from one of those has no line for it. Substituting an empty value
# would silently erase every {{ASSISTANT_NAME}} placeholder, so fall back to
# the orchestrator name — exactly what the interactive prompt defaults to.
ASSISTANT_NAME="${ASSISTANT_NAME:-$ORCHESTRATOR_NAME}"

# Optional/derived values may be missing from an older saved config —
# default them so 'set -u' never trips in --apply mode.
USER_EMAIL="${USER_EMAIL:-}"
GITHUB_USER="${GITHUB_USER:-}"
BOT_USERNAME="${BOT_USERNAME:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
USER_LOGIN="${USER_LOGIN:-$(whoami)}"
CLAUDE_PROJECT_SLUG="${CLAUDE_PROJECT_SLUG:-${CATALYST_ROOT//\//-}}"
MACHINE_HOST="${MACHINE_HOST:-$DEFAULT_HOST}"
EXAMPLE_BRAND="${EXAMPLE_BRAND:-ExampleBrand}"

# Re-check every value against the rules the prompts enforce. In --apply mode
# this is the only check there is: .catalyst-config may predate a rule, may
# have been hand-edited into a shape config_file_ok still accepts (a $'...'
# value can hold a quote or a newline), or may simply be missing a required
# key. A bad value is refused here rather than written into JSON and YAML.
# Offending values are named by key, never echoed.
CONFIG_INVALID=0
check_value() {   # <key> <regex> <hint> <required|optional>
    local key="$1" re="$2" hint="$3" mode="$4" val
    val="${!key:-}"
    if [[ -z "$val" ]]; then
        if [[ "$mode" == "required" ]]; then
            echo -e "${RED}  $key is missing or empty (required).${NC}" >&2
            CONFIG_INVALID=1
        fi
        return 0
    fi
    if [[ ! "$val" =~ $re ]]; then
        echo -e "${RED}  $key is not acceptable — use $hint.${NC}" >&2
        CONFIG_INVALID=1
    fi
}

check_value USER_NAME         "$NAME_RE"              "$NAME_HINT"              required
check_value ORCHESTRATOR_NAME "$NAME_RE"              "$NAME_HINT"              required
check_value ASSISTANT_NAME    "$NAME_RE"              "$NAME_HINT"              required
check_value MACHINE_HOST      "$MACHINE_HOST_RE"      "$MACHINE_HOST_HINT"      required
check_value EXAMPLE_BRAND     "$NAME_RE"              "$NAME_HINT"              required
check_value USER_EMAIL        "$EMAIL_RE"             "$EMAIL_HINT"             optional
check_value GITHUB_USER       "$GITHUB_USER_RE"       "$GITHUB_USER_HINT"       optional
check_value BOT_USERNAME      "$BOT_USERNAME_RE"      "$BOT_USERNAME_HINT"      optional
check_value TELEGRAM_CHAT_ID  "$TELEGRAM_CHAT_ID_RE"  "$TELEGRAM_CHAT_ID_HINT"  optional

if (( CONFIG_INVALID )); then
    echo -e "${RED}.catalyst-config holds values this script will not substitute.${NC}" >&2
    echo -e "${RED}Nothing was changed. Re-run ./setup.sh (no --apply) to answer again.${NC}" >&2
    exit 1
fi

# The example brand becomes the hostname of the HTTP-Referer attribution
# header a few media tools send (https://<brand>.example), so narrow it
# further to [A-Za-z0-9_].
SANITIZED_BRAND="$(printf '%s' "$EXAMPLE_BRAND" | tr -cd 'A-Za-z0-9_')"
if [[ "$SANITIZED_BRAND" != "$EXAMPLE_BRAND" ]]; then
    echo -e "${YELLOW}Example brand '$EXAMPLE_BRAND' has characters outside [A-Za-z0-9_]; using '${SANITIZED_BRAND:-ExampleBrand}'.${NC}"
fi
EXAMPLE_BRAND="${SANITIZED_BRAND:-ExampleBrand}"

# ORCHESTRATOR_NAME_UPPER: the orchestrator name upper-cased with every
# non-alphanumeric character replaced by '_' (used for env-var and constant
# names). Always re-derived from ORCHESTRATOR_NAME, so older saved configs
# need no extra key.
ORCHESTRATOR_NAME_UPPER="$(printf '%s' "$ORCHESTRATOR_NAME" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')"

# ORCHESTRATOR_NAME_LOWER: lower-cased with every character outside [a-z0-9_-]
# removed. It lands in shell aliases, SSH host names, tmux session names,
# keychain service names and file paths, so it must stay a safe slug. Falls
# back to "orchestrator" if nothing survives sanitizing.
ORCHESTRATOR_NAME_LOWER="$(printf '%s' "$ORCHESTRATOR_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
ORCHESTRATOR_NAME_LOWER="${ORCHESTRATOR_NAME_LOWER:-orchestrator}"

echo ""
echo -e "${BLUE}Applying personalization...${NC}"

# Escape a value for the right-hand side of a sed "s|...|...|g" expression
# (backslash, ampersand and the '|' delimiter are special there). The values
# themselves were already constrained above, so this only guards sed syntax.
sed_escape() { printf '%s' "$1" | sed -e 's/[\&|]/\\&/g'; }

# GNU sed wants -i with no argument; BSD/macOS sed wants -i ''.
if sed --version >/dev/null 2>&1; then
    SED_INPLACE=(sed -i)
else
    SED_INPLACE=(sed -i '')
fi

# Build the sed program. Every token always substitutes: optional prompts
# fall back to a neutral placeholder, because a skipped prompt must never
# ship an unsubstituted brace placeholder into URLs or runtime defaults.
# {{BRAND}} is a cosmetic safety net: it appears as the hostname of the
# HTTP-Referer attribution header a few media tools send. It is NEVER a
# credential namespace — every shipped tool reads and writes macOS Keychain
# items under the fixed account name "huxley".
SED_ARGS=(
    -e "s|{{CATALYST_ROOT}}|$(sed_escape "$CATALYST_ROOT")|g"
    -e "s|{{HOME_DIR}}|$(sed_escape "$HOME")|g"
    -e "s|{{USER_NAME}}|$(sed_escape "$USER_NAME")|g"
    -e "s|{{ORCHESTRATOR_NAME_UPPER}}|$(sed_escape "$ORCHESTRATOR_NAME_UPPER")|g"
    -e "s|{{ORCHESTRATOR_NAME_LOWER}}|$(sed_escape "$ORCHESTRATOR_NAME_LOWER")|g"
    -e "s|{{ORCHESTRATOR_NAME}}|$(sed_escape "$ORCHESTRATOR_NAME")|g"
    -e "s|{{ASSISTANT_NAME}}|$(sed_escape "$ASSISTANT_NAME")|g"
    -e "s|{{USER_LOGIN}}|$(sed_escape "$USER_LOGIN")|g"
    -e "s|{{CLAUDE_PROJECT_SLUG}}|$(sed_escape "$CLAUDE_PROJECT_SLUG")|g"
    -e "s|{{MACHINE_HOST}}|$(sed_escape "$MACHINE_HOST")|g"
    -e "s|{{BRAND}}|$(sed_escape "$EXAMPLE_BRAND")|g"
    -e "s|{{USER_EMAIL}}|$(sed_escape "${USER_EMAIL:-you@example.com}")|g"
    -e "s|{{GITHUB_USER}}|$(sed_escape "${GITHUB_USER:-your-github-user}")|g"
    -e "s|{{TELEGRAM_BOT}}|$(sed_escape "${BOT_USERNAME:-YourBotUsername}")|g"
    -e "s|{{TELEGRAM_CHAT_ID}}|$(sed_escape "$TELEGRAM_CHAT_ID")|g"
)

# Only files carrying one of these tokens are rewritten. Other {{TOKENS}}
# (CAPSULE_SLUG, PROJECT_NAME, ...) are downstream placeholders inside
# templates/ and are left alone on purpose.
TOKEN_RE='\{\{(CATALYST_ROOT|HOME_DIR|USER_NAME|ORCHESTRATOR_NAME|ORCHESTRATOR_NAME_UPPER|ORCHESTRATOR_NAME_LOWER|ASSISTANT_NAME|USER_EMAIL|USER_LOGIN|GITHUB_USER|CLAUDE_PROJECT_SLUG|MACHINE_HOST|TELEGRAM_BOT|TELEGRAM_CHAT_ID|BRAND)\}\}'

# Walk every regular file in the tree and replace placeholders.
# Notes:
#  - find descends into hidden dirs (.claude, .claude-context, .github);
#    only .git, node_modules, virtualenvs and __pycache__ are excluded, and
#    they are -prune'd so their contents are never even traversed.
#  - No extension filter: extensionless shebang scripts, Dockerfiles, LICENSE
#    and any source type are all covered; 'grep -I' skips binaries.
#  - This script and the saved config are the only files left untouched.
#  - The list is materialized first so a find failure aborts the run; inside a
#    process substitution its exit status would be invisible.
FILE_LIST="$(mktemp "${TMPDIR:-/tmp}/huxley-setup-files.XXXXXX")"
trap 'rm -f "$FILE_LIST"' EXIT
if ! find "$CATALYST_ROOT" \
    -type d \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name __pycache__ \) -prune \
    -o -type f \
       ! -path "$CATALYST_ROOT/setup.sh" \
       ! -name ".catalyst-config" \
       -print0 > "$FILE_LIST"; then
    echo -e "${RED}Could not walk $CATALYST_ROOT — nothing was substituted.${NC}" >&2
    exit 1
fi

COUNT=0
while IFS= read -r -d '' file; do
    if grep -IqE "$TOKEN_RE" "$file" 2>/dev/null; then
        "${SED_INPLACE[@]}" "${SED_ARGS[@]}" "$file"
        COUNT=$((COUNT + 1))
        echo "  Updated: ${file#"$CATALYST_ROOT"/}"
    fi
done < "$FILE_LIST"
echo -e "${GREEN}Updated $COUNT file(s)${NC}"

# AGENTS.md carries the portable identity for non-Claude agent CLIs, several of
# which truncate or ignore it past 10,000 characters. Warn if the substituted
# file crossed the line (long names or a long "Personalize Me" section).
AGENTS_MD="$CATALYST_ROOT/AGENTS.md"
if [[ -f "$AGENTS_MD" ]]; then
    AGENTS_CHARS="$(LC_ALL=en_US.UTF-8 wc -m < "$AGENTS_MD" 2>/dev/null | tr -d '[:space:]' || true)"
    [[ -n "$AGENTS_CHARS" ]] || AGENTS_CHARS="$(wc -c < "$AGENTS_MD" | tr -d '[:space:]')"
    if (( AGENTS_CHARS > AGENTS_MD_LIMIT )); then
        echo -e "${YELLOW}WARNING: AGENTS.md is $AGENTS_CHARS characters (limit $AGENTS_MD_LIMIT).${NC}"
        echo -e "${YELLOW}         Trim the 'Personalize Me' section or shorten a paragraph so agent CLIs read all of it.${NC}"
    else
        echo "  AGENTS.md: $AGENTS_CHARS characters (limit $AGENTS_MD_LIMIT)"
    fi
fi

# Create .env from .env.example if it doesn't exist
if [[ ! -f "$CATALYST_ROOT/.env" ]] && [[ -f "$CATALYST_ROOT/.env.example" ]]; then
    cp "$CATALYST_ROOT/.env.example" "$CATALYST_ROOT/.env"
    chmod 600 "$CATALYST_ROOT/.env"
    echo -e "${GREEN}Created .env from .env.example — fill in your API keys${NC}"
fi

# Python virtualenv for the shipped tools. Docs, LaunchAgents and the hook
# runner reference .venv/bin/python3, so create it here and install the
# shared tool requirements. Failures are non-fatal: the command to finish
# the job by hand is printed instead.
#
# Re-runs must be able to recover, so existence of the directory is never the
# test: a .venv without bin/python3 is a half-made one (interrupted run, a
# python3 -m venv that died partway) and is removed and rebuilt, a create that
# fails leaves nothing behind, and a requirements install is retried until it
# succeeds once — recorded by the marker file, not guessed.
VENV_DIR="$CATALYST_ROOT/.venv"
VENV_MARKER="$VENV_DIR/.huxley-requirements-installed"
REQUIREMENTS="$CATALYST_ROOT/tools/requirements.txt"

if [[ -d "$VENV_DIR" && ! -x "$VENV_DIR/bin/python3" ]]; then
    echo -e "${YELLOW}Removing an incomplete .venv (no bin/python3) so it can be rebuilt.${NC}"
    rm -rf "$VENV_DIR"
fi

install_requirements() {
    [[ -f "$REQUIREMENTS" ]] || return 0
    [[ -f "$VENV_MARKER" ]] && return 0
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
    if "$VENV_DIR/bin/pip" install --quiet -r "$REQUIREMENTS"; then
        : > "$VENV_MARKER"
        echo -e "${GREEN}Installed tools/requirements.txt into .venv${NC}"
    else
        echo -e "${YELLOW}.venv is ready, but pip install failed (offline?).${NC}"
        echo -e "${YELLOW}Re-run ./setup.sh --apply to retry, or finish now with:${NC}"
        echo -e "${YELLOW}  .venv/bin/pip install -r tools/requirements.txt${NC}"
    fi
}

if [[ -x "$VENV_DIR/bin/python3" ]]; then
    install_requirements
elif command -v python3 >/dev/null 2>&1; then
    echo -e "${BLUE}Creating Python virtualenv (.venv) for the shipped tools...${NC}"
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1 && [[ -x "$VENV_DIR/bin/python3" ]]; then
        echo -e "${GREEN}Created .venv${NC}"
        install_requirements
    else
        rm -rf "$VENV_DIR"
        echo -e "${YELLOW}Could not create .venv. Finish later with:${NC}"
        echo -e "${YELLOW}  python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt${NC}"
    fi
else
    echo -e "${YELLOW}python3 not found — install it, then run:${NC}"
    echo -e "${YELLOW}  python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt${NC}"
fi

# Materialize example configs (global/config/foo.example.yaml -> foo.yaml).
# Runs after tokenization so the copies carry your substituted values, and
# never overwrites a config you have already customized. The ".example."
# removal is applied to the basename only: a checkout living under a path
# that itself contains ".example." must not be rewritten.
for example in "$CATALYST_ROOT"/global/config/*.example.*; do
    [[ -e "$example" ]] || continue
    example_dir="$(dirname "$example")"
    example_base="$(basename "$example")"
    real="$example_dir/${example_base/.example./.}"
    if [[ ! -e "$real" ]]; then
        cp "$example" "$real"
        echo -e "${GREEN}Created ${real#"$CATALYST_ROOT"/} from ${example#"$CATALYST_ROOT"/}${NC}"
    fi
done

# Create the runtime directories the shipped tools and LaunchAgents expect.
# logs/, registry/, monitoring/ and tmp/ are gitignored and pruned from the
# template, but launchd refuses to start a job whose log directory is missing
# and several tools write registry/monitoring state on first run.
mkdir -p "$CATALYST_ROOT"/{memory,capsules,Incubator,logs,registry,monitoring,tmp}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Fill in API keys in .env"
echo "  2. (Optional) Run ./setup-skills.sh to install community skills"
echo "  3. Open Claude Code: claude"
echo ""
echo "Note: Claude Code permissions start in 'default' mode — Claude asks"
echo "before running commands or editing files. Once you're comfortable, you"
echo "can opt into autonomous operation by setting \"defaultMode\": \"auto\""
echo "in .claude/settings.json."
echo ""
echo -e "Your orchestrator is named ${BLUE}$ORCHESTRATOR_NAME${NC}."
echo -e "Welcome to Huxley, ${BLUE}$USER_NAME${NC}."
