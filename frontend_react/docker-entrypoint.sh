#!/bin/sh
# Runtime environment injection for Vite SPA
# Writes VITE_* env vars to window.__ENV__ so the app can read them at runtime
echo "🔍 Checking runtime environment variables..."
[ -z "$VITE_API_URL" ] && echo "⚠️ VITE_API_URL is missing" || echo "✅ VITE_API_URL is present"
[ -z "$VITE_ADMIN_TOKEN" ] && echo "⚠️ VITE_ADMIN_TOKEN is missing" || echo "✅ VITE_ADMIN_TOKEN is present"

cat <<EOF > /usr/share/nginx/html/env-config.js
window.__ENV__ = {
  VITE_API_URL: "${VITE_API_URL:-}",
  VITE_API_BASE_URL: "${VITE_API_BASE_URL:-}",
  VITE_BFF_URL: "${VITE_BFF_URL:-}",
  VITE_WS_URL: "${VITE_WS_URL:-}",
  VITE_ADMIN_TOKEN: "${VITE_ADMIN_TOKEN:-}",
  VITE_APP_NAME: "${VITE_APP_NAME:-ClinicForge}"
};
EOF

echo "✅ env-config.js generated with runtime environment variables"
exec nginx -g 'daemon off;'
