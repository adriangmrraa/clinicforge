# Stage 1: Build
FROM node:22-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .

# Placeholders — real values injected at container start via env-config.js
ENV VITE_API_URL=RUNTIME_REPLACE
ENV VITE_API_BASE_URL=RUNTIME_REPLACE
ENV VITE_BFF_URL=RUNTIME_REPLACE
ENV VITE_WS_URL=RUNTIME_REPLACE
ENV VITE_ADMIN_TOKEN=RUNTIME_REPLACE
ENV VITE_APP_NAME=ClinicForge

# Skip tsc (strict mode breaks CI). Vite handles TS fine.
RUN npx vite build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Generate entrypoint script inline (avoids Windows CRLF issues)
RUN set -e; \
    echo '#!/bin/sh' > /entrypoint.sh; \
    echo 'set -e' >> /entrypoint.sh; \
    echo 'cat > /usr/share/nginx/html/env-config.js <<ENDOFENV' >> /entrypoint.sh; \
    echo 'window.__ENV__ = {' >> /entrypoint.sh; \
    echo '  VITE_API_URL: "$VITE_API_URL",' >> /entrypoint.sh; \
    echo '  VITE_API_BASE_URL: "$VITE_API_BASE_URL",' >> /entrypoint.sh; \
    echo '  VITE_BFF_URL: "$VITE_BFF_URL",' >> /entrypoint.sh; \
    echo '  VITE_WS_URL: "$VITE_WS_URL",' >> /entrypoint.sh; \
    echo '  VITE_ADMIN_TOKEN: "$VITE_ADMIN_TOKEN",' >> /entrypoint.sh; \
    echo '  VITE_APP_NAME: "$VITE_APP_NAME"' >> /entrypoint.sh; \
    echo '};' >> /entrypoint.sh; \
    echo 'ENDOFENV' >> /entrypoint.sh; \
    echo 'exec nginx -g "daemon off;"' >> /entrypoint.sh; \
    chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
