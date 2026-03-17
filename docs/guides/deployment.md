# Production Deployment Guide

Step-by-step guide to deploy Pulsar AI on a production server.

---

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **OS** | Ubuntu 22.04+ / any Linux with Docker |
| **GPU** | NVIDIA with CUDA 12+ drivers (for training) |
| **RAM** | 32 GB recommended |
| **Disk** | 100+ GB SSD |
| **Docker** | Docker Engine 24+ with Compose V2 |
| **NVIDIA Container Toolkit** | Required for GPU access in containers |

---

## 1. Clone and configure

```bash
git clone https://github.com/VasilyKolbenev/PulsarAI.git
cd PulsarAI
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: set a strong random secret for JWT auth
PULSAR_JWT_SECRET=$(openssl rand -hex 32)

# Server
PULSAR_HOST=0.0.0.0
PULSAR_PORT=8888

# Optional: PostgreSQL instead of SQLite
# PULSAR_DB_URL=postgresql://pulsar:password@postgres:5432/pulsar

# Optional: Redis for distributed job queue
# PULSAR_REDIS_URL=redis://redis:6379/0

# Optional: S3 for artifact storage
# PULSAR_S3_BUCKET=pulsar-artifacts
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...

# Optional: OpenAI for Co-pilot features
# OPENAI_API_KEY=sk-...
```

---

## 2. Generate SSL certificates

For production, use Let's Encrypt. For internal deployment:

```bash
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=pulsar.local"
```

---

## 3. Launch with Docker Compose

```bash
# Basic (SQLite + local storage)
docker compose up -d app nginx

# Full stack (PostgreSQL + Redis)
docker compose up -d
```

Verify:

```bash
docker compose ps          # all services "Up"
curl -k https://localhost  # should return HTML
```

---

## 4. Create admin user

```bash
# Via API
curl -k -X POST https://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@company.com", "password": "secure-password", "name": "Admin"}'
```

Or open `https://<server-ip>` in a browser and use the registration form.

---

## 5. Backups

### SQLite (default)

```bash
# Manual backup
bash scripts/backup_db.sh

# Cron: daily at 2 AM
echo "0 2 * * * cd /opt/pulsar-ai && bash scripts/backup_db.sh" | crontab -
```

Backups are saved to `backups/` with 7-day retention.

### PostgreSQL

```bash
pg_dump -U pulsar pulsar > backup_$(date +%Y%m%d).sql
```

---

## 6. Monitoring

Prometheus metrics are available at `/metrics`:

```bash
curl -k https://localhost/metrics
```

Exposes: request counts, training jobs, CPU/memory/GPU utilization.

Add to your Prometheus `scrape_configs`:

```yaml
- job_name: pulsar-ai
  scheme: https
  tls_config:
    insecure_skip_verify: true
  static_configs:
    - targets: ['pulsar-server:443']
```

---

## 7. Updates

```bash
cd /opt/pulsar-ai
git pull origin main
docker compose build app
docker compose up -d app
```

---

## Architecture overview

```
Client (browser)
    |
    v
[Nginx :443] -- SSL termination, static caching
    |
    v
[Pulsar App :8888] -- FastAPI + React SPA
    |
    +-- SQLite / PostgreSQL (experiments, users, metrics)
    +-- Local FS / S3 (model artifacts, datasets)
    +-- Local threads / Redis (job queue)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| GPU not detected in container | Install `nvidia-container-toolkit`, add `runtime: nvidia` |
| Port 443 already in use | Change nginx port in `docker-compose.yml` |
| JWT errors after restart | Ensure `PULSAR_JWT_SECRET` is set in `.env` |
| Database locked (SQLite) | Normal under high load; switch to PostgreSQL |
| Training OOM | Reduce batch size or use QLoRA (4-bit) |
