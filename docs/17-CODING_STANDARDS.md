# 17 · Coding Standards

## Python (Backend)

### Estilo y formato

- **Formatter**: `ruff format` (equivalente a black)
- **Linter**: `ruff check` (equivalente a flake8 + isort + pyupgrade)
- **Type checking**: `mypy --strict`
- **Line length**: 100 caracteres

```bash
# Formatear y verificar
ruff format .
ruff check . --fix
mypy .
```

### Type hints

Obligatorio en todo el código:

```python
# ✅ Correcto
async def analyze_cv(
    cv_text: str,
    target_role: str,
    db: AsyncSession,
) -> CVAnalysisResult:
    ...

# ❌ Incorrecto
async def analyze_cv(cv_text, target_role, db):
    ...
```

### Modelos Pydantic

```python
# ✅ Usar modelos para todas las estructuras de datos
class SkillMatch(BaseModel):
    keyword: str
    weight: float = Field(ge=0.0, le=1.0)
    found_in_sections: list[str] = Field(default_factory=list)
    match_type: Literal["exact", "alias", "semantic"]

# ❌ Nunca usar dicts crudos para datos estructurados
def analyze(data: dict) -> dict:  # No
    ...
```

### Async/await

```python
# ✅ Async en todos los endpoints y operaciones de I/O
@router.post("/analyze/cv")
async def analyze_cv(request: CVAnalysisRequest, db: AsyncSession = Depends(get_db)):
    result = await cv_analyzer.analyze(request.cv_text, request.target_role, db)
    return result

# ✅ Operaciones paralelas cuando no dependen entre sí
skills, market_data = await asyncio.gather(
    extract_skills(cv_text),
    get_market_data(target_role),
)

# ❌ Usar time.sleep() en código async
import time
time.sleep(1)  # Bloquea el event loop — usar asyncio.sleep(1)
```

### Manejo de errores

```python
# ✅ Errores específicos con contexto
class ATSAnalysisError(Exception):
    def __init__(self, message: str, cv_hash: str):
        super().__init__(message)
        self.cv_hash = cv_hash

# ✅ HTTP exceptions descriptivas
@router.post("/analyze/cv")
async def analyze_cv(request: CVAnalysisRequest):
    if len(request.cv_text) < 100:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CV_TOO_SHORT",
                "message": "El CV debe tener al menos 100 caracteres",
            }
        )

# ❌ Bare except
try:
    result = await analyze(cv)
except:          # No — captura hasta SystemExit
    pass
```

### Estructura de módulos

```python
# Orden de imports
# 1. Standard library
import asyncio
from datetime import datetime
from typing import Literal

# 2. Third party
import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local
from app.core.config import settings
from app.db.models import JobPosting
from app.schemas.analysis import CVAnalysisRequest
```

---

## TypeScript / Next.js (Frontend)

### Estilo

- **Formatter**: Prettier (config en `.prettierrc`)
- **Linter**: ESLint con config Next.js
- **Type checking**: TypeScript strict mode

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true
  }
}
```

### Componentes

```tsx
// ✅ Tipado explícito de props
interface SkillBadgeProps {
  skill: string;
  frequency: number;
  trend: 'rising' | 'stable' | 'declining';
  onClick?: () => void;
}

export function SkillBadge({ skill, frequency, trend, onClick }: SkillBadgeProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-full px-3 py-1 text-sm font-medium',
        trend === 'rising' && 'bg-green-100 text-green-800',
        trend === 'declining' && 'bg-red-100 text-red-800',
        trend === 'stable' && 'bg-gray-100 text-gray-800',
      )}
    >
      {skill} · {frequency}%
    </button>
  );
}
```

### Data fetching

```tsx
// ✅ React Query para todos los fetches
export function useSkillsRadar(role: string, country: string) {
  return useQuery({
    queryKey: ['skills', role, country],
    queryFn: () => api.market.getSkills(role, country),
    staleTime: 1000 * 60 * 5,  // 5 minutos
  });
}

// ✅ Mutations con estado de loading
export function useAnalyzeCV() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: CVAnalysisRequest) => api.analyze.cv(request),
    onSuccess: (data) => {
      queryClient.setQueryData(['cv-analysis', data.analysis_id], data);
    },
  });
}
```

---

## Convenciones de nombres

### Python

```python
# Variables y funciones: snake_case
ats_score = 72
target_role = "ai_engineer"

def calculate_ats_score(cv_text: str, role: str) -> int: ...

# Clases: PascalCase
class CVAnalysisEngine: ...
class WeightedKeyword: ...

# Constantes: UPPER_SNAKE_CASE
MAX_CV_SIZE_BYTES = 5 * 1024 * 1024
SUPPORTED_ROLES = frozenset({"ai_engineer", "data_engineer"})

# Archivos: snake_case
# app/engine/ats_scorer.py
# app/api/routes/analyze.py
```

### TypeScript

```typescript
// Variables y funciones: camelCase
const atsScore = 72;
function calculateAtsScore(cvText: string): number { ... }

// Tipos e interfaces: PascalCase
interface CVAnalysisResult { ... }
type TrendDirection = 'rising' | 'stable' | 'declining';

// Constantes: UPPER_SNAKE_CASE
const MAX_FILE_SIZE_MB = 5;

// Archivos de componentes: PascalCase
// SkillBadge.tsx, CVAnalyzer.tsx

// Hooks: camelCase con prefijo use
// useSkillsRadar.ts, useCVAnalysis.ts
```

### Base de datos

```sql
-- Tablas: snake_case plural
job_postings, skill_demand, profile_analyses

-- Columnas: snake_case
created_at, role_category, ats_score

-- Índices: idx_{tabla}_{columna(s)}
idx_job_postings_role, idx_skill_demand_role_period

-- Constraints: {tipo}_{tabla}_{columna}
pk_job_postings, fk_skill_demand_skill_id, uq_job_postings_source_external_id
```

---

## Git

### Conventional Commits

```
feat: add CV analyzer endpoint
fix: correct ATS score calculation for missing critical keywords
docs: update API spec with new pagination format
refactor: extract skills matching logic into separate module
test: add integration tests for /analyze/cv endpoint
chore: upgrade LangChain to 0.2.x
perf: add pgvector index for embedding similarity search
```

### Branching

```
main                  → producción (protegida, requiere PR)
develop               → rama de integración
feature/cv-analyzer   → features nuevas
fix/ats-score-calc    → bug fixes
chore/upgrade-deps    → tareas de mantenimiento
```

### Pull Requests

- Cada PR hace exactamente una cosa
- Tests que demuestran que el cambio funciona
- Descripción con "qué" y "por qué" (no "cómo")
- Self-review antes de pedir review

---

## Lo que NO hacer

```python
# ❌ SQL con f-strings (SQL injection)
query = f"SELECT * FROM users WHERE email = '{email}'"

# ❌ Secretos en código
ANTHROPIC_API_KEY = "sk-ant-xxxxx"

# ❌ print() para debugging en código de producción
print(f"Debug: {cv_text[:100]}")

# ❌ Funciones de más de 50 líneas sin refactor
# Si una función crece mucho, dividirla en funciones más pequeñas

# ❌ Magic numbers
if score > 75:   # ← ¿Qué significa 75?
    ...
# ✅ Constante con nombre
ATS_GOOD_SCORE_THRESHOLD = 75
if score > ATS_GOOD_SCORE_THRESHOLD:
    ...
```
