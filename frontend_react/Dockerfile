# Stage 1: Build
FROM node:22-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .

# Build with placeholder values — real values are injected at runtime
ENV VITE_API_URL=__VITE_API_URL_PLACEHOLDER__
ENV VITE_API_BASE_URL=__VITE_API_BASE_URL_PLACEHOLDER__
ENV VITE_BFF_URL=__VITE_BFF_URL_PLACEHOLDER__
ENV VITE_WS_URL=__VITE_WS_URL_PLACEHOLDER__
ENV VITE_ADMIN_TOKEN=__VITE_ADMIN_TOKEN_PLACEHOLDER__
ENV VITE_APP_NAME=ClinicForge

RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
