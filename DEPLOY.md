# Deployment Guide

## Quick Start

### Local Development
```bash
# Frontend only (Vercel recommended for dev)
cd frontend && npm run dev

# Full stack with Docker
docker compose up
```

### Production Deploy
```bash
# Option A: One-liner on your server
curl -fsSL https://raw.githubusercontent.com/akhileshdasari2004/hackthon1/main/scripts/deploy.sh | bash

# Option B: Manual
git clone https://github.com/akhileshdasari2004/hackthon1.git /opt/agira
cd /opt/agira
cp .env.production .env
# Edit .env and set API_KEY
./scripts/start.sh all
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Users                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS

┌──────────────────────▼──────────────────────────────────────┐
│              Frontend (Next.js on Vercel)                    │
│         http://your-domain.com OR localhost:3000             │
│                                                              │
│  API Routes:                                                 │
│    POST /api/analyze  → creates job, returns job_id          │
│    GET  /api/analyze  → poll job status                      │
│    GET  /api/report   → fetch full report                    │
│    GET  /api/history  → past jobs                            │
│    GET  /api/health   → health check                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ File system (shared volume)
                       │ or HTTP (cross-container)

┌──────────────────────▼──────────────────────────────────────┐
│           Python Backend (Docker container)                  │
│              agira-backend container                          │
│                                                              │
│  job_runner.py:                                              │
│    1. Creates job directory in /data/jobs/<uuid>/            │
│    2. Copies repo to temp dir                                │
│    3. Runs Orchestrator (11-node DAG)                        │
│    4. Writes result.json                                     │
│                                                              │
│  Sandbox execution:                                          │
│    - Dev: subprocess.run() with timeout                      │
│    - Prod: Docker container (--network=none, --read-only)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Options

### Option 1: Vercel + Self-hosted Backend (Recommended)

**Frontend → Vercel** (zero-config)
```bash
cd frontend
vercel deploy
```

**Backend → Railway/Render/Fly.io**
1. Create `Dockerfile` (already exists)
2. Set environment variables (see `.env.production`)
3. Deploy the Docker image
4. Update `NEXT_PUBLIC_API_BASE` in Vercel to point to your backend URL

### Option 2: Fully Self-hosted (Docker Compose)

```bash
git clone https://github.com/akhileshdasari2004/hackthon1.git
cd hackthon1

# Create data directories
mkdir -p .agira-jobs .agira-memory

# Create .env
cp .env.production .env
nano .env  # SET API_KEY!

# Start
docker compose up -d

# Verify
curl http://localhost:3000/api/health
```

### Option 3: Kubernetes

```bash
# Build images
docker build -t agira/backend:latest .
docker build -t agira/frontend:latest ./frontend

# Push to registry
docker push agira/backend:latest
docker push agira/frontend:latest

# Deploy using helm (see k8s/ directory for values)
helm install agira ./k8s/helm -f ./k8s/production-values.yaml
```

---

## Environment Variables

### Backend (`.env`)
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | **YES** | — | API authentication key (generate: `openssl rand -hex 32`) |
| `AGIRA_JOBS_DIR` | No | `/data/jobs` | Job state files |
| `AGIRA_MEMORY_PATH` | No | `/data/memory_store.json` | Cross-run memory |
| `GH_TOKEN` | No | — | GitHub PAT for PR creation |
| `AGIRA_SANDBOX_MODE` | No | `subprocess` | `subprocess` or `docker` |
| `AGIRA_MAX_CONCURRENT_JOBS` | No | `4` | Max parallel jobs |
| `SENTRY_DSN` | No | — | Sentry error tracking |

### Frontend (Vercel)
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | **YES** | — | Must match backend |
| `NEXT_PUBLIC_API_BASE` | No | same-origin | Backend URL for API calls |

---

## Security Configuration

### 1. Generate API Key
```bash
openssl rand -hex 32
# Example: 3f7a9b2c1d4e6f8a3b5c7d9e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a
```

### 2. Firewall Rules
```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Block all other inbound (if running exposed)
ufw default deny incoming

# Allow SSH (restrict to your IP)
ufw allow from YOUR_IP to any port 22
```

### 3. Production Sandbox (Docker)
The sandbox runs with:
- `--network=none` — no network access
- `--read-only` root filesystem
- `--memory=256m` — memory limit
- `--cpu-quota=50000` — CPU limit (0.5 cores)
- `--cap-drop=ALL` — no Linux capabilities
- `--security-opt=no-new-privileges` — no privilege escalation
- Runs as non-root user (uid 1000)

---

## Health Checks

```bash
# Frontend
curl http://localhost:3000/api/health
# {"status":"ok","service":"agira-frontend","timestamp":"..."}

# Backend (inside container)
docker exec agira-backend python3 scripts/health_check.py
# {"status":"ok","service":"agira-backend","version":"0.1.0",...}
```

---

## CI/CD

GitHub Actions automatically:
- Runs pytest (Python tests)
- Runs TypeScript check + ESLint
- Runs security scans (Trivy, Semgrep)
- Builds and pushes Docker images on merge to main

To enable deployments, add these repository secrets:
- `PRODUCTION_HOST` — server hostname
- `PRODUCTION_USER` — SSH username

---

## Monitoring

### Logs
```bash
# View all logs
docker compose logs -f

# Backend only
docker compose logs -f agira-backend

# Frontend only
docker compose logs -f agira-frontend

# Job runner output
tail -f .agira-jobs/*/status.json
```

### Metrics (Prometheus format — future)
```bash
curl http://localhost:3000/api/metrics  # planned
```

---

## Troubleshooting

### Frontend 500 error
```bash
docker compose logs agira-frontend
# Check: API_KEY matches between frontend env and backend .env
```

### Jobs stuck in "running"
```bash
# Check job status
cat .agira-jobs/<job_id>/status.json

# Kill stuck job
docker compose restart agira-backend
```

### Out of disk space
```bash
# Clean old jobs (keep last 7 days)
find .agira-jobs -mtime +7 -type d -exec rm -rf {} \;

# Or set TTL in .env: AGIRA_JOB_TTL_DAYS=7
```

### Docker build fails
```bash
docker build --no-cache -t agira/backend:test .
```