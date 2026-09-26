FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies including @maximhq/bifrost
RUN npm install

# Copy bifrost data directory structure
COPY . .

# Expose Bifrost port
EXPOSE 8083

# Set environment variables
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp
ENV BIFROST_OTEL_ENABLED=true

# Start Bifrost
CMD ["node_modules/@maximhq/bifrost/bifrost-http", "-port", "8083", "-app-dir", "/app/bifrost-data"]
