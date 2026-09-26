#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Load environment variables from .env file
if [ -f "{{CATALYST_ROOT}}/.env" ]; then
    set -a
    source "{{CATALYST_ROOT}}/.env"
    set +a
fi

# API Keys - must be set in .env file
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY}"
export FIREWORKS_API_KEY="${FIREWORKS_API_KEY}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export GROQ_API_KEY="${GROQ_API_KEY}"
export FAL_API_KEY="${FAL_API_KEY}"

# OpenTelemetry configuration
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_TRACES_EXPORTER="otlp"
export BIFROST_OTEL_ENABLED="true"

cd {{CATALYST_ROOT}}/tools/gateways/bifrost-cli
if [ -x node_modules/@maximhq/bifrost/bifrost-http ]; then
  nohup node_modules/@maximhq/bifrost/bifrost-http -port 8083 -app-dir {{CATALYST_ROOT}}/tools/gateways/bifrost-data > /tmp/bifrost.log 2>&1 &
else
  nohup node node_modules/@maximhq/bifrost/bin.js -port 8083 -app-dir {{CATALYST_ROOT}}/tools/gateways/bifrost-data > /tmp/bifrost.log 2>&1 &
fi

sleep 3
echo "Bifrost started on port 8083"
tail -15 /tmp/bifrost.log | grep -E "started|error|open_router"
