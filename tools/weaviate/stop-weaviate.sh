#!/bin/bash
# Stop Weaviate server

echo "🛑 Stopping Weaviate server..."

if ! lsof -Pi :8082 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "   Weaviate is not running on port 8082"
    exit 0
fi

PID=$(lsof -ti:8082)
if [ -n "$PID" ]; then
    echo "   Killing process $PID"
    kill $PID
    sleep 2

    # Force kill if still running
    if lsof -Pi :8082 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "   Force killing..."
        kill -9 $PID
    fi

    echo "✅ Weaviate stopped"
else
    echo "   No process found"
fi
