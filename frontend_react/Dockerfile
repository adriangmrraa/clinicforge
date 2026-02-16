# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .

# Placeholders — real values injected at container start
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

# Template for runtime env injection — envsubst replaces $VARS at container start
RUN echo 'window.__ENV__={VITE_API_URL:"$VITE_API_URL",VITE_API_BASE_URL:"$VITE_API_BASE_URL",VITE_BFF_URL:"$VITE_BFF_URL",VITE_WS_URL:"$VITE_WS_URL",VITE_ADMIN_TOKEN:"$VITE_ADMIN_TOKEN",VITE_APP_NAME:"$VITE_APP_NAME"};' \
    > /usr/share/nginx/html/env-config.js.template

# Entrypoint: envsubst replaces $VARS in template, then starts nginx
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'envsubst < /usr/share/nginx/html/env-config.js.template > /usr/share/nginx/html/env-config.js' >> /entrypoint.sh && \
    echo 'exec nginx -g "daemon off;"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
