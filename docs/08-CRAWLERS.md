# 08 · Crawlers

## Principios

1. **Ser un buen ciudadano de la web** — Respetar `robots.txt`, rate limits y ToS.
2. **Fail gracefully** — Un crawler que falla no debe tirar el sistema.
3. **Idempotente** — Correr dos veces el mismo crawler no duplica datos.
4. **Observable** — Cada run genera métricas: cuántos items, cuántos errores, duración.

---

## Estructura

```
crawler/
├── base/
│   ├── base_crawler.py      # Clase base con retry, rate limiting, logging
│   └── http_client.py       # httpx client configurado
├── jobs/
│   ├── indeed.py
│   ├── greenhouse.py
│   └── lever.py
├── profiles/
│   └── linkedin_public.py
├── trends/
│   ├── google_trends.py
│   ├── reddit.py
│   └── hackernews.py
├── config.py                # Configuración de fuentes, rate limits
└── runner.py                # Entry point para Celery tasks
```

---

## Clase base

```python
# crawler/base/base_crawler.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
import logging
import random
import httpx

logger = logging.getLogger(__name__)

@dataclass
class CrawlResult:
    source: str
    items_found: int
    items_new: int
    items_duplicated: int
    errors: int
    duration_seconds: float

class BaseCrawler(ABC):
    
    def __init__(self, rate_limit_rps: float = 0.5):
        self.rate_limit_rps = rate_limit_rps  # requests per second
        self._last_request_time = 0.0
    
    def _wait_rate_limit(self) -> None:
        """Espera el tiempo necesario para respetar el rate limit."""
        min_interval = 1.0 / self.rate_limit_rps
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed + random.uniform(0, 0.5)  # jitter
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _get(self, url: str, **kwargs) -> httpx.Response:
        """GET con rate limiting y retry automático."""
        self._wait_rate_limit()
        # retry logic implementado en http_client
        return self.client.get(url, **kwargs)
    
    @abstractmethod
    def crawl(self) -> CrawlResult:
        """Implementación específica de cada fuente."""
        ...
    
    @abstractmethod
    def parse(self, raw: str) -> list[dict]:
        """Parsea el HTML/JSON crudo y devuelve items normalizados."""
        ...
```

---

## Job Crawlers

### Indeed Crawler

```python
# crawler/jobs/indeed.py

INDEED_SEARCH_URL = "https://www.indeed.com/jobs"

ROLES_TO_CRAWL = [
    ("AI Engineer", "Argentina"),
    ("AI Engineer", "Mexico"),
    ("AI Engineer", "Spain"),
    ("Analytics Engineer", "Argentina"),
    ("Data Engineer", "Argentina"),
    ("ML Engineer", "Argentina"),
    ("LangChain developer", "Remote"),
]

class IndeedCrawler(BaseCrawler):
    
    def __init__(self):
        super().__init__(rate_limit_rps=0.2)  # 1 req cada 5 segundos
    
    def crawl(self) -> CrawlResult:
        total_new = 0
        for role, location in ROLES_TO_CRAWL:
            jobs = self._crawl_role(role, location)
            new = self._upsert_jobs(jobs)
            total_new += new
        return CrawlResult(...)
    
    def _crawl_role(self, role: str, location: str) -> list[dict]:
        jobs = []
        for page in range(0, 500, 10):  # máximo 50 páginas
            params = {"q": role, "l": location, "start": page}
            response = self._get(INDEED_SEARCH_URL, params=params)
            page_jobs = self.parse(response.text)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
        return jobs
```

### Greenhouse Crawler

Greenhouse tiene una API JSON pública limpia, sin scraping necesario.

```python
# crawler/jobs/greenhouse.py

GREENHOUSE_COMPANIES = [
    "mercadolibre", "despegar", "uala", "lemon", 
    "bitso", "satellogic", "auth0", "globant",
]

class GreenhouseCrawler(BaseCrawler):
    
    def __init__(self):
        super().__init__(rate_limit_rps=1.0)  # API pública, más permisiva
    
    def crawl(self) -> CrawlResult:
        for company in GREENHOUSE_COMPANIES:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            response = self._get(url, params={"content": "true"})
            jobs = response.json().get("jobs", [])
            self._process_jobs(jobs, company)
```

---

## Profile Crawler (LinkedIn público)

```python
# crawler/profiles/linkedin_public.py

class LinkedInPublicCrawler(BaseCrawler):
    """
    Solo accede a perfiles 100% públicos de LinkedIn.
    No usa login. Rate limit muy conservador.
    Solo extrae metadata agregada, no PII.
    """
    
    def __init__(self):
        # Muy conservador: 1 request cada 10-15 segundos
        super().__init__(rate_limit_rps=0.08)
        self._playwright = None
    
    def crawl_public_profiles(self, role: str, limit: int = 100) -> CrawlResult:
        """
        Busca perfiles públicos que aparecen en búsquedas de LinkedIn sin login.
        Solo extrae: título, skills, resumen de experiencia (sin nombres).
        """
        ...
    
    def _extract_skills_only(self, profile_html: str) -> list[str]:
        """
        Extrae SOLO las skills del perfil, sin datos personales identificables.
        El almacenamiento es siempre agregado, nunca individual.
        """
        ...
```

**Política de privacidad del crawler**:
- No almacenar nombres completos, emails ni teléfonos de terceros
- Almacenar solo skills, título y seniority de forma agregada
- Nunca usar autenticación para acceder a más datos
- Si LinkedIn agrega CAPTCHA → detener el crawler, no evadir

---

## Trends Crawlers

### Google Trends

```python
# crawler/trends/google_trends.py
from pytrends.request import TrendReq

TRACKED_KEYWORDS = [
    "LangChain", "LangGraph", "AI Agent", "RAG AI", "MCP Claude",
    "FastAPI Python", "pgvector", "n8n automation",
    "AI Engineer", "Analytics Engineer", "Prompt Engineering",
]

class GoogleTrendsCrawler(BaseCrawler):
    
    def crawl(self) -> CrawlResult:
        pytrends = TrendReq(hl='es-AR', tz=360)
        
        # Procesar en batches de 5 (límite de pytrends)
        for batch in self._batch(TRACKED_KEYWORDS, 5):
            pytrends.build_payload(batch, timeframe='now 7-d', geo='AR')
            data = pytrends.interest_over_time()
            self._store_trends(data)
```

### Hacker News

```python
# crawler/trends/hackernews.py

HN_API = "https://hacker-news.firebaseio.com/v0"

class HackerNewsCrawler(BaseCrawler):
    """
    Busca en los top stories de HN menciones de tecnologías AI.
    Usa la API oficial de HN (pública, sin auth).
    """
    
    def crawl_top_stories(self, limit: int = 200) -> CrawlResult:
        response = self._get(f"{HN_API}/topstories.json")
        story_ids = response.json()[:limit]
        
        for story_id in story_ids:
            story = self._get(f"{HN_API}/item/{story_id}.json").json()
            keywords_found = self._extract_tech_keywords(story.get("title", ""))
            if keywords_found:
                self._store_signal(story_id, keywords_found)
```

---

## Configuración y scheduling

```python
# crawler/config.py

CRAWLER_SCHEDULE = {
    "indeed":           {"cron": "0 */6 * * *",   "enabled": True},
    "greenhouse":       {"cron": "0 8 * * *",     "enabled": True},
    "lever":            {"cron": "0 8 * * *",     "enabled": True},
    "linkedin_public":  {"cron": "0 2 * * *",     "enabled": True},   # Solo nocturno
    "google_trends":    {"cron": "0 0 * * 1",     "enabled": True},   # Semanal
    "hackernews":       {"cron": "0 */12 * * *",  "enabled": True},
    "reddit":           {"cron": "0 6 * * *",     "enabled": True},
}

RATE_LIMITS = {
    "indeed":           0.2,   # 1 req / 5s
    "greenhouse":       1.0,   # 1 req / 1s
    "lever":            1.0,
    "linkedin_public":  0.08,  # 1 req / 12s
    "google_trends":    0.1,
    "hackernews":       2.0,   # API oficial, generosa
    "reddit":           0.5,
}
```

---

## Manejo de errores

| Error | Acción |
|-------|--------|
| HTTP 429 | Esperar `Retry-After` header + backoff exponencial |
| HTTP 403 | Log + skip (posible bloqueo) |
| HTTP 5xx | Retry 3 veces con backoff, luego fail |
| Timeout | Retry 2 veces, luego fail |
| Parse error | Log el item fallido, continuar con el siguiente |
| DB error | Rollback del batch, alert |

---

## Observabilidad

Cada crawler registra:
```python
{
    "crawler": "indeed",
    "run_id": "uuid",
    "started_at": "2025-07-28T02:00:00Z",
    "finished_at": "2025-07-28T02:47:23Z",
    "duration_seconds": 2843,
    "items_found": 1820,
    "items_new": 234,
    "items_duplicated": 1586,
    "errors": 3,
    "error_rate_pct": 0.16
}
```

Métricas exportadas a Prometheus:
- `crawler_items_total{source, status}`
- `crawler_duration_seconds{source}`
- `crawler_errors_total{source, error_type}`
