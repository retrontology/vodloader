FROM nginx:1.27.0-bookworm

COPY nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:80 || exit 1
