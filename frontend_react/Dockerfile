# Stage 1: Build
FROM node:22-alpine as builder
WORKDIR /app
COPY package*.json ./
# Relaxed install (ignoring peer deps conflicts if any persist)
RUN npm install --legacy-peer-deps
COPY . .

# Build arguments for environment variables
ARG VITE_API_URL
ARG VITE_API_BASE_URL
ARG VITE_BFF_URL
ARG VITE_WS_URL
ARG VITE_ADMIN_TOKEN
ARG VITE_APP_NAME=Dentalogic

# Map ARGs to ENVs so they are available to the build process
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_BFF_URL=$VITE_BFF_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_ADMIN_TOKEN=$VITE_ADMIN_TOKEN
ENV VITE_APP_NAME=$VITE_APP_NAME

# Skip type checking during build for stability if needed, 
# but here package.json has tsc && vite build
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
