# Production Deployment Guide

## Architecture

```
Internet
  │
  ▼
Cloudflare (DNS + DDoS protection)
  │
  ▼
Nginx Proxy Manager (SSL termination + reverse proxy)
  │
  ▼
Docker: Django + Gunicorn (port 8000)
  │
  ▼
Docker: PostgreSQL (internal)
```

## Server Setup

### 1. Install Docker & Docker Compose

```bash
curl -fsSL https://get.docker.com | bash
usermod -aG docker $USER
```

### 2. Install Nginx Proxy Manager

```bash
docker run -d \
  --name=nginx-proxy-manager \
  --restart unless-stopped \
  -p 80:80 \
  -p 81:81 \
  -p 443:443 \
  -v /opt/npm/data:/data \
  -v /opt/npm/letsencrypt:/etc/letsencrypt \
  jc21/nginx-proxy-manager:latest
```

Access NPM at `http://YOUR_SERVER_IP:81` (default: admin@example.com / changeme).

### 3. Deploy the App

```bash
# Clone repo
git clone https://github.com/osokuka/leasemanagment.git
cd leasemanagment

# Configure env
cp .env.production .env
# Edit .env — set POSTGRES_PASSWORD and SECRET_KEY

# Connect to NPM network
docker network connect npm_default nginx-proxy-manager 2>/dev/null || true

# Build & start
docker compose -f docker-compose.production.yml up -d --build

# Seed default users (first time only)
docker compose -f docker-compose.production.yml exec web python seed.py
```

### 4. Configure Nginx Proxy Manager

In NPM web UI (`:81`):

1. **Proxy Hosts** → Add Proxy Host
   - **Domain Names**: `bibaj-management.com`, `www.bibaj-management.com`, `bm.prosolutions-ks.com`
   - **Forward Hostname/IP**: `bldg_mgm_web` (Docker service name)
   - **Forward Port**: `8000`
   - **SSL**: Request new certificate (Let's Encrypt)
   - **Force SSL**: ✓
   - **HTTP/2**: ✓
   - **Websockets Support**: ✓
   - **Block Common Exploits**: ✓

2. **Access Lists** (optional): Restrict admin endpoints

### 5. Cloudflare DNS

Add A records pointing to your server IP:
- `bibaj-management.com` → your_server_ip
- `www.bibaj-management.com` → your_server_ip
- `bm.prosolutions-ks.com` → your_server_ip

## Maintenance

```bash
# View logs
docker compose -f docker-compose.production.yml logs -f web

# Run migrations
docker compose -f docker-compose.production.yml exec web python manage.py migrate

# Collect static files
docker compose -f docker-compose.production.yml exec web python manage.py collectstatic --noinput

# Update app
git pull
docker compose -f docker-compose.production.yml up -d --build

# Backup database
docker compose -f docker-compose.production.yml exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%F).sql

# Restore database
cat backup.sql | docker compose -f docker-compose.production.yml exec -T db psql -U $POSTGRES_USER $POSTGRES_DB
```
