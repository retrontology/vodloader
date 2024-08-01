FROM nginx:1.27.0-bookworm

RUN apt update
RUN apt install certbot python3-certbot-nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN certbot --nginx -d example.com -d www.example.com

HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:80 || exit 1
