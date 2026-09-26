#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/update_session.sh
# Helper script to quickly update session context

set -euo pipefail

SC="${CATALYST_ROOT:-{{CATALYST_ROOT}}}/global/session_context.md"
DATE="$(date '+%Y-%m-%d %H:%M')"

# Ensure directory exists
if [ ! -f "$SC" ]; then 
    mkdir -p "$(dirname "$SC")"
    touch "$SC"
fi

# Generate fresh session context template
cat > "$SC" <<EOF
# Session Context — $DATE

## Last Session
- **What we worked on:**
  - 

- **Decisions made:**
  - 

- **Artifacts updated:**
  - 

## Next Priorities
- [ ] 
- [ ] 
- [ ] 

## Notes
- 

EOF

echo "✅ Updated session context: $SC"
echo "📝 Edit the file to document your current session"

