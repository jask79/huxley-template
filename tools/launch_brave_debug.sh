#!/bin/bash
# Launch Google Chrome with remote debugging enabled

echo "🚀 Launching Chrome with remote debugging..."
echo ""
echo "⚠️  Note: This will close any existing Chrome windows first"
echo ""

# Close existing Chrome instances
pkill -x "Google Chrome" 2>/dev/null
sleep 2

# Launch Chrome with debugging port
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --disable-web-security \
  --disable-features=IsolateOrigins,site-per-process \
  > /dev/null 2>&1 &

echo "✅ Chrome launched with remote debugging on port 9222"
echo ""
echo "📌 Next steps:"
echo "   1. Navigate to your Supabase project dashboard"
echo "   2. Go to Settings → API"
echo "   3. Run: python3 {{CATALYST_ROOT}}/tools/extract_supabase_credentials.py"
