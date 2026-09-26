#!/bin/bash
# Huxley — Community Skills Installer
# Clones community skill repos and creates symlinks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/.claude/skills"
COMMUNITY_DIR="$SKILLS_DIR/community"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Huxley — Community Skills Installer${NC}"
echo ""

mkdir -p "$COMMUNITY_DIR"

# ─── Community Repos ───────────────────────────────────────────────────────────

declare -A REPOS=(
    ["addyosmani-web-quality"]="https://github.com/addyosmani/web-quality-skills.git"
    ["andreev-danila-skills"]="https://github.com/andreev-danila/skills.git"
    ["anthropic"]="https://github.com/anthropics/skills.git"
    ["avdlee-swiftui"]="https://github.com/AvdLee/SwiftUI-Agent-Skill.git"
    ["better-auth"]="https://github.com/better-auth/skills.git"
    ["cloudflare-skills"]="https://github.com/cloudflare/skills.git"
    ["dimillian-skills"]="https://github.com/dimillian/skills.git"
    ["expo"]="https://github.com/expo/skills.git"
    ["kv0906-cc-skills"]="https://github.com/kv0906/cc-skills.git"
    ["pluginagentmarketplace-rn"]="https://github.com/pluginagentmarketplace/custom-plugin-react-native.git"
    ["remotion"]="https://github.com/remotion-dev/skills.git"
    ["vercel-labs"]="https://github.com/vercel-labs/agent-skills.git"
    ["wondelai-skills"]="https://github.com/wondelai/skills.git"
)

echo -e "${YELLOW}Cloning community skill repos...${NC}"
for dir in "${!REPOS[@]}"; do
    target="$COMMUNITY_DIR/$dir"
    if [[ -d "$target" ]]; then
        echo "  [skip] $dir (already exists)"
    else
        echo "  [clone] $dir"
        git clone --depth 1 "${REPOS[$dir]}" "$target" 2>/dev/null || {
            echo "  [FAIL] Could not clone $dir — skipping"
            continue
        }
    fi
done

# ─── Community Symlinks ───────────────────────────────────────────────────────

echo ""
echo -e "${YELLOW}Creating community skill symlinks...${NC}"

create_link() {
    local name="$1"
    local target="$2"
    local link="$SKILLS_DIR/$name"

    if [[ -e "$link" ]] || [[ -L "$link" ]]; then
        return  # already exists
    fi

    if [[ -d "$SKILLS_DIR/$target" ]]; then
        ln -s "$target" "$link"
        echo "  [link] $name -> $target"
    else
        echo "  [skip] $name (target not found: $target)"
    fi
}

# Addy Osmani
create_link "addyosmani-core-web-vitals" "community/addyosmani-web-quality/skills/core-web-vitals"
create_link "addyosmani-seo" "community/addyosmani-web-quality/skills/seo"

# Andreev Danila
create_link "reanimated-skia-performance" "community/andreev-danila-skills/skills/reanimated-skia-performance"

# Anthropic
create_link "frontend-design" "community/anthropic/skills/frontend-design"
create_link "mcp-builder" "community/anthropic/skills/mcp-builder"
create_link "skill-creator" "community/anthropic/skills/skill-creator"

# Better Auth
create_link "auth-best-practices" "community/better-auth/better-auth/best-practices"
create_link "auth-create" "community/better-auth/better-auth/create-auth"

# Cloudflare
create_link "cloudflare-web-perf" "community/cloudflare-skills/skills/web-perf"

# Dimillian
create_link "swift-concurrency-expert" "community/dimillian-skills/swift-concurrency-expert"
create_link "swiftui-liquid-glass" "community/dimillian-skills/swiftui-liquid-glass"
create_link "swiftui-performance-audit" "community/dimillian-skills/swiftui-performance-audit"
create_link "swiftui-ui-patterns" "community/dimillian-skills/swiftui-ui-patterns"
create_link "swiftui-view-refactor" "community/dimillian-skills/swiftui-view-refactor"

# Expo
create_link "building-native-ui" "community/expo/plugins/expo-app-design/skills/building-native-ui"
create_link "native-data-fetching" "community/expo/plugins/expo-app-design/skills/native-data-fetching"
create_link "upgrading-expo" "community/expo/plugins/upgrading-expo/skills/upgrading-expo"

# KV0906
create_link "premium-frontend-design" "community/kv0906-cc-skills/advanced-frontend-skill"

# Plugin Agent Marketplace
create_link "react-native-animations" "community/pluginagentmarketplace-rn/skills/react-native-animations"

# Remotion
create_link "remotion-video" "community/remotion/skills/remotion"

# Vercel Labs
create_link "composition-patterns" "community/vercel-labs/skills/composition-patterns"
create_link "react-best-practices" "community/vercel-labs/skills/react-best-practices"
create_link "web-design-guidelines" "community/vercel-labs/skills/web-design-guidelines"

# Wondelai
create_link "cro-methodology" "community/wondelai-skills/cro-methodology"
create_link "top-design" "community/wondelai-skills/top-design"

# ─── .agents Symlinks (from bushido/han and others) ───────────────────────────
# These symlinks point to ../../.agents/skills/ which is populated by
# `npx skills find <query>` and similar tooling. They are too numerous to
# enumerate here — install individual skills with:
#   npx skills find <topic>

echo ""
echo -e "${GREEN}Done! Community skills installed.${NC}"
echo "Run 'npx skills find <topic>' to discover and install additional skills."
