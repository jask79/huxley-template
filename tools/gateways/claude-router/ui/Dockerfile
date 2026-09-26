FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Note: Running as root in dev mode for volume mount compatibility
# For production, build the static assets and serve with a dedicated server as non-root

# Expose Vite dev server port
EXPOSE 5173

# Set Vite to use polling for file watching in Docker
ENV CHOKIDAR_USEPOLLING=true
ENV WATCHPACK_POLLING=true

# Start Vite dev server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
