# 14 · Deployment

## Estrategia por fase

| Fase | Plataforma | Justificación |
|------|-----------|---------------|
| MVP (Fase 1) | Railway | Simple, barato, ideal para hobby/MVP |
| Beta (Fase 2-3) | Railway Pro | Más recursos, custom domains, PostgreSQL managed |
| Producción (Fase 4+) | AWS ECS + RDS | Escalabilidad, SLA, confiabilidad enterprise |

---

## Desarrollo local

### Requisitos
- Docker Desktop >= 24
- Python 3.11+
- Node.js 20+
- Git

### Setup completo

```bash
# 1. Clonar y configurar
git clone https://github.com/sirjabo/linkedin-intelligence
cd linkedin-intelligence
cp .env.example .env
# Editar .env con tus API keys

# 2. Levantar infraestructura
docker compose up -d

# 3. Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd ../frontend
npm install
npm run dev

# 5. Verificar
curl http://localhost:8000/health  # {"status": "ok"}
open http://localhost:3000
```

### Docker Compose (desarrollo)

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: linkedin_intelligence
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./backend
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/linkedin_intelligence
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --reload --host 0.0.0.0

  worker:
    build: ./backend
    depends_on: [postgres, redis]
    command: celery -A app.worker worker --loglevel=info

  beat:
    build: ./backend
    depends_on: [postgres, redis]
    command: celery -A app.worker beat --loglevel=info

  flower:
    image: mher/flower
    depends_on: [redis]
    ports:
      - "5555:5555"   # Dashboard de Celery

volumes:
  postgres_data:
```

---

## Railway (MVP)

### Servicios en Railway

```
linkedin-intelligence (proyecto)
├── api          → FastAPI (Python)
├── worker       → Celery Worker
├── beat         → Celery Beat scheduler
├── postgres     → PostgreSQL 16 (managed)
├── redis        → Redis 7 (managed)
└── frontend     → Next.js (Vercel o Railway)
```

### Deploy a Railway

```bash
# Instalar Railway CLI
npm install -g @railway/cli
railway login

# Vincular al proyecto
railway link

# Deploy
railway up

# Variables de entorno
railway variables set ANTHROPIC_API_KEY=xxx
railway variables set OPENAI_API_KEY=xxx
```

### railway.toml

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

---

## CI/CD con GitHub Actions

### Pipeline de CI

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: pip install -r backend/requirements-dev.txt
      
      - name: Lint
        run: |
          cd backend
          ruff check .
          mypy .
      
      - name: Test
        run: |
          cd backend
          pytest --cov=app --cov-report=xml tests/
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci && npm run type-check && npm test
```

### Pipeline de CD

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]  # Solo si CI pasa
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Railway
        uses: bervProject/railway-deploy@v1
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: api
```

---

## Dockerfile (backend)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Variables de entorno por ambiente

```bash
# .env.example (valores de ejemplo, nunca reales)

# App
ENVIRONMENT=development           # development | staging | production
SECRET_KEY=change-me-in-production-minimum-32-chars
DEBUG=true

# Database
POSTGRES_USER=linkedin_user
POSTGRES_PASSWORD=change-me
POSTGRES_DB=linkedin_intelligence
DATABASE_URL=postgresql+asyncpg://linkedin_user:change-me@localhost:5432/linkedin_intelligence

# Redis
REDIS_URL=redis://localhost:6379

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Crawlers
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
GITHUB_TOKEN=

# Opcional
SENTRY_DSN=
LANGCHAIN_API_KEY=    # Para LangSmith tracing
LANGCHAIN_TRACING_V2=true
```

---

## Checklist pre-deploy a producción

- [ ] Variables de entorno configuradas (no defaults de desarrollo)
- [ ] `ENVIRONMENT=production` 
- [ ] `DEBUG=false`
- [ ] Migraciones de DB aplicadas
- [ ] Health check endpoint respondiendo
- [ ] Tests en CI pasando al 100%
- [ ] Rate limiting configurado
- [ ] Backup de DB funcionando
- [ ] Monitoring activo (Sentry, Prometheus)
- [ ] DNS y SSL configurados
