#!/bin/bash
# Supabase CLI Helper Functions for Huxley
# Common operations for Backend Dev agent

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load credentials from .env if available
load_credentials() {
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
}

# Initialize Supabase in current capsule
init_supabase_capsule() {
    echo -e "${BLUE}🔧 Initializing Supabase in capsule...${NC}"

    if [ -d "supabase" ]; then
        echo -e "${YELLOW}⚠️  supabase/ directory already exists${NC}"
        read -p "Reinitialize? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi

    supabase init
    echo -e "${GREEN}✅ Supabase initialized${NC}"
}

# Link to Supabase project
link_project() {
    local PROJECT_REF=$1

    if [ -z "$PROJECT_REF" ]; then
        # Try to get from .env
        load_credentials
        PROJECT_REF=${SUPABASE_PROJECT_REF:-}
    fi

    if [ -z "$PROJECT_REF" ]; then
        echo -e "${RED}❌ No project reference provided${NC}"
        echo "Usage: link_project <project-ref>"
        echo "Or set SUPABASE_PROJECT_REF in .env"
        return 1
    fi

    echo -e "${BLUE}🔗 Linking to project: $PROJECT_REF${NC}"
    supabase link --project-ref "$PROJECT_REF"
    echo -e "${GREEN}✅ Project linked${NC}"
}

# Pull remote schema to local
pull_schema() {
    echo -e "${BLUE}⬇️  Pulling remote schema...${NC}"
    supabase db pull
    echo -e "${GREEN}✅ Schema pulled${NC}"
}

# Push local migrations to remote
push_migrations() {
    echo -e "${BLUE}⬆️  Pushing migrations to remote...${NC}"

    # Show what will be pushed
    echo -e "${YELLOW}Migrations to push:${NC}"
    supabase migration list

    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted"
        return
    fi

    supabase db push
    echo -e "${GREEN}✅ Migrations pushed${NC}"
}

# Generate TypeScript types
generate_types() {
    local OUTPUT_FILE=${1:-"types/database.ts"}

    echo -e "${BLUE}📝 Generating TypeScript types...${NC}"

    # Create types directory if it doesn't exist
    mkdir -p "$(dirname "$OUTPUT_FILE")"

    # Check if linked or local
    if [ -f ".branches/_current_branch" ] || [ -f "supabase/.temp/project-ref" ]; then
        echo "Generating from linked project..."
        supabase gen types typescript --linked > "$OUTPUT_FILE"
    else
        echo "Generating from local database..."
        supabase gen types typescript --local > "$OUTPUT_FILE"
    fi

    echo -e "${GREEN}✅ Types generated: $OUTPUT_FILE${NC}"
}

# Show schema diff
show_diff() {
    echo -e "${BLUE}🔍 Checking schema differences...${NC}"
    supabase db diff
}

# Create new migration
new_migration() {
    local MIGRATION_NAME=$1

    if [ -z "$MIGRATION_NAME" ]; then
        echo -e "${RED}❌ Migration name required${NC}"
        echo "Usage: new_migration <name>"
        return 1
    fi

    echo -e "${BLUE}📝 Creating migration: $MIGRATION_NAME${NC}"
    supabase migration new "$MIGRATION_NAME"
    echo -e "${GREEN}✅ Migration created${NC}"
}

# Start local Supabase stack
start_local() {
    echo -e "${BLUE}🚀 Starting local Supabase...${NC}"
    supabase start
    echo -e "${GREEN}✅ Local Supabase running${NC}"
    echo ""
    echo -e "${YELLOW}Access URLs:${NC}"
    supabase status
}

# Stop local Supabase stack
stop_local() {
    echo -e "${BLUE}🛑 Stopping local Supabase...${NC}"
    supabase stop
    echo -e "${GREEN}✅ Local Supabase stopped${NC}"
}

# Reset local database to current migrations
reset_local() {
    echo -e "${YELLOW}⚠️  This will reset your local database${NC}"
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted"
        return
    fi

    echo -e "${BLUE}🔄 Resetting local database...${NC}"
    supabase db reset
    echo -e "${GREEN}✅ Database reset${NC}"
}

# Lint database for issues
lint_database() {
    echo -e "${BLUE}🔍 Linting database...${NC}"
    supabase db lint
}

# Show migration history
show_migrations() {
    echo -e "${BLUE}📜 Migration history:${NC}"
    supabase migration list
}

# Squash migrations
squash_migrations() {
    echo -e "${YELLOW}⚠️  This will combine migrations into a single file${NC}"
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted"
        return
    fi

    echo -e "${BLUE}📦 Squashing migrations...${NC}"
    supabase migration squash
    echo -e "${GREEN}✅ Migrations squashed${NC}"
}

# Export functions
export -f load_credentials
export -f init_supabase_capsule
export -f link_project
export -f pull_schema
export -f push_migrations
export -f generate_types
export -f show_diff
export -f new_migration
export -f start_local
export -f stop_local
export -f reset_local
export -f lint_database
export -f show_migrations
export -f squash_migrations

echo "✅ Supabase helper functions loaded"
echo ""
echo "Available functions:"
echo "  init_supabase_capsule  - Initialize Supabase in current directory"
echo "  link_project <ref>     - Link to Supabase project"
echo "  pull_schema            - Pull remote schema to local"
echo "  push_migrations        - Push local migrations to remote"
echo "  generate_types [file]  - Generate TypeScript types"
echo "  show_diff              - Show schema differences"
echo "  new_migration <name>   - Create new migration"
echo "  start_local            - Start local Supabase stack"
echo "  stop_local             - Stop local Supabase stack"
echo "  reset_local            - Reset local database"
echo "  lint_database          - Lint database for issues"
echo "  show_migrations        - Show migration history"
echo "  squash_migrations      - Combine migrations"
