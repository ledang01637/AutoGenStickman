#!/bin/bash
set -e

echo "=== Pulling latest code ==="
git pull origin main

echo "=== Copying certs ==="
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/certs/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/certs/

echo "=== Building (no cache) ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod build --no-cache

echo "=== Running migrations (BEFORE deploy) ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api alembic upgrade head

echo "=== Deploying ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --remove-orphans --force-recreate

echo "=== Cleaning up ==="
docker image prune -f

echo "=== Done ==="
docker compose -f docker-compose.prod.yml --env-file .env.prod ps