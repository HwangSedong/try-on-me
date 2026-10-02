#!/bin/bash
set -euo pipefail

APP=/home/ubuntu/apps/try-on-me
RELEASE=$1
NGINX_CONTAINER=travel-memory-map-nginx-1
DOMAIN=fit.sedong.dev
PUBLIC_IP=52.79.115.211

if [[ ! -d "$RELEASE/backend" || ! -d "$RELEASE/frontend-dist" || ! -d "$RELEASE/pydeps" ]]; then
  echo "release is missing backend, frontend-dist, or pydeps" >&2
  exit 1
fi

if [[ ! -f "$APP/shared/.env" ]]; then
  echo "missing $APP/shared/.env" >&2
  exit 1
fi

previous=$(readlink -f "$APP/current" || true)
ln -sfn "$RELEASE" "$APP/current"
sudo cp "$RELEASE/deploy/try-on-me.service" /etc/systemd/system/try-on-me.service
sudo systemctl daemon-reload
sudo systemctl enable try-on-me
sudo systemctl restart try-on-me

healthy=0
for _ in 1 2 3 4 5 6 7 8; do
  if curl -fsS "http://172.18.0.1:8010/api/health" >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done

if [[ "$healthy" -ne 1 ]]; then
  echo "new release failed health check" >&2
  if [[ -n "$previous" && -d "$previous" ]]; then
    ln -sfn "$previous" "$APP/current"
    sudo systemctl restart try-on-me || true
  fi
  exit 1
fi

apply_nginx() {
  local source=$1
  sudo docker cp "$source" "$NGINX_CONTAINER:/etc/nginx/conf.d/fit.sedong.dev.conf"
  if ! sudo docker exec "$NGINX_CONTAINER" nginx -t; then
    sudo docker exec "$NGINX_CONTAINER" rm -f /etc/nginx/conf.d/fit.sedong.dev.conf
    echo "nginx config test failed; left the running config unchanged" >&2
    exit 1
  fi
  sudo docker exec "$NGINX_CONTAINER" nginx -s reload
}

cert="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
apply_nginx "$RELEASE/deploy/nginx-http.conf"

if [[ ! -f "$cert" ]] && getent hosts "$DOMAIN" | awk '{print $1}' | grep -qx "$PUBLIC_IP"; then
  if command -v certbot >/dev/null; then
    sudo certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || true
  fi
fi

if [[ -f "$cert" ]]; then
  apply_nginx "$RELEASE/deploy/nginx-https.conf"
fi

mkdir -p "$APP/releases"
# Keep the live release and one previous release. Removing older copies stays a small delete.
find "$APP/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | awk 'NR>2 {print $2}' | while read -r old; do
  if [[ "$old" != "$RELEASE" && "$old" != "$previous" ]]; then
    rm -rf "$old"
  fi
done

echo "active $(basename "$RELEASE")"
