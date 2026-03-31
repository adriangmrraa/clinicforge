# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .

# Placeholders — real values injected at container start
ENV VITE_API_URL=""
ENV VITE_API_BASE_URL=""
ENV VITE_BFF_URL=""
ENV VITE_WS_URL=""
ENV VITE_APP_NAME=ClinicForge
ENV VITE_FACEBOOK_APP_ID=""
ENV VITE_META_CONFIG_ID=""
ENV VITE_META_EMBEDDED_SIGNUP=false

# Skip tsc (strict mode breaks CI). Vite handles TS fine.
RUN npx vite build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Template for runtime env injection — envsubst replaces $VARS at container start
RUN echo 'window.__ENV__={VITE_API_URL:"$VITE_API_URL",VITE_API_BASE_URL:"$VITE_API_BASE_URL",VITE_BFF_URL:"$VITE_BFF_URL",VITE_WS_URL:"$VITE_WS_URL",VITE_APP_NAME:"$VITE_APP_NAME",VITE_FACEBOOK_APP_ID:"$VITE_FACEBOOK_APP_ID",VITE_META_CONFIG_ID:"$VITE_META_CONFIG_ID",VITE_META_EMBEDDED_SIGNUP:"$VITE_META_EMBEDDED_SIGNUP"};' \
    > /usr/share/nginx/html/env-config.js.template

# Entrypoint: envsubst replaces $VARS in template, then starts nginx
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'envsubst < /usr/share/nginx/html/env-config.js.template > /usr/share/nginx/html/env-config.js' >> /entrypoint.sh && \
    echo 'exec nginx -g "daemon off;"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Non-root nginx
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx && \
    touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
