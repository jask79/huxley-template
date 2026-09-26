#!/bin/bash
# Check what local servers are running on macOS

echo "🔍 Active Local Servers on Your Mac"
echo "======================================"
echo ""

lsof -iTCP -sTCP:LISTEN -n -P | awk 'NR>1 {printf "%-20s %-30s %s\n", $1, $9, $2}' | sort -u | \
while read program port pid; do
    echo "📡 $program on $port (PID: $pid)"
done

echo ""
echo "💡 Quick Reference:"
echo "   localhost = 127.0.0.1 (your computer)"
echo "   Port = the 'door' number after the colon"
echo "   * = listening on all network interfaces"
