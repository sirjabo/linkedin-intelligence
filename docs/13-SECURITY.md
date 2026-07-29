# 13 · Seguridad

## Principios

1. **Privacy by design** — Minimizar la recolección de datos personales.
2. **Zero trust** — Validar siempre, nunca asumir.
3. **Least privilege** — Cada componente accede solo a lo que necesita.
4. **Defense in depth** — Múltiples capas de protección.

---

## Autenticación y autorización

### JWT

```python
# Tokens JWT con expiración corta
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Payload mínimo (no incluir datos sensibles en el JWT)
JWT_PAYLOAD = {
    "sub": "user_uuid",
    "plan": "free",
    "exp": expiration_timestamp,
}
```

### Rate limiting

```python
# Por IP (usuarios no autenticados)
RATE_LIMIT_ANONYMOUS = "30/minute"

# Por usuario autenticado
RATE_LIMIT_FREE = "60/minute"
RATE_LIMIT_PRO = "200/minute"

# Por endpoint sensible
RATE_LIMIT_AUTH = "5/minute"    # Login/register
RATE_LIMIT_ANALYSIS = "10/hour" # Free tier: 10 análisis por hora
```

---

## Manejo de datos de usuario

### Datos que recolectamos (con consentimiento explícito)

| Dato | Propósito | Retención |
|------|-----------|-----------|
| Email | Autenticación, notificaciones | Hasta baja |
| Target role | Personalización | Hasta baja |
| CV text | Análisis ATS | 30 días |
| LinkedIn profile text | Análisis de perfil | 30 días |
| Análisis generados | Historial del usuario | 6 meses |

### Datos que NO recolectamos

- Contraseñas de LinkedIn u otras plataformas
- Tokens de OAuth de terceros (más de 24h)
- Datos financieros
- PII de terceros (nombres, emails de otras personas)

### Datos de terceros (perfiles públicos de LinkedIn)

Solo almacenamos datos **agregados**:
- Skills frecuencia por rol (no por persona)
- Patrones de títulos (no nombres)
- Distribución de experiencias (no individuos)

Nunca: nombre completo + empresa + skills juntos de una persona real.

---

## Seguridad de la API

### Validación de input

```python
# Todos los inputs validados con Pydantic v2
class CVAnalysisRequest(BaseModel):
    cv_text: Annotated[str, Field(min_length=100, max_length=50_000)]
    target_role: Annotated[str, Field(pattern=r'^[a-z_]+$')]
    
    @field_validator('target_role')
    @classmethod
    def validate_role(cls, v):
        allowed = {'ai_engineer', 'data_engineer', 'analytics_engineer', 'ml_engineer'}
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return v
```

### SQL Injection

- ORM (SQLAlchemy) para todas las queries — nunca SQL dinámico con f-strings
- Queries parametrizadas cuando se usa SQL crudo
- Input sanitization en todos los campos de texto libre

### File Upload

```python
ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_FILE_SIZE_MB = 5

async def validate_upload(file: UploadFile):
    # Verificar MIME type (no confiar solo en extensión)
    content = await file.read(1024)
    if not is_pdf(content):
        raise HTTPException(400, "Solo se aceptan archivos PDF")
    
    # Verificar tamaño
    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, "El archivo supera el límite de 5MB")
    
    # Escanear con antivirus (producción)
    # await scan_with_clamav(file)
```

### CORS

```python
CORS_ORIGINS = [
    "https://linkedin-intelligence.com",
    "https://app.linkedin-intelligence.com",
    # En desarrollo:
    "http://localhost:3000",
]
```

---

## Secretos y configuración

```bash
# Nunca hardcodear secretos en el código
# Variables de entorno obligatorias en producción:

SECRET_KEY=          # Mínimo 32 chars, random
DATABASE_URL=        # Incluir password
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Rotación de secretos: cada 90 días en producción
# Uso de AWS Secrets Manager o similar en prod
```

### Pre-commit hook para detectar secretos

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

---

## Seguridad de crawlers

Los crawlers deben:
- Identificarse honestamente con un User-Agent descriptivo
- Respetar `robots.txt` antes de cualquier crawl
- No evadir CAPTCHAs
- No usar credenciales de terceros para acceder a datos privados
- Parar inmediatamente si reciben HTTP 451 (Legal reasons)

```python
USER_AGENT = (
    "LinkedInIntelligence-Bot/1.0 "
    "(+https://linkedin-intelligence.com/bot; "
    "contact: bot@linkedin-intelligence.com)"
)
```

---

## Respuesta a incidentes

### Niveles de severidad

| Nivel | Descripción | Tiempo de respuesta |
|-------|-------------|-------------------|
| P0 — Critical | Breach de datos de usuarios | < 1 hora |
| P1 — High | API down, datos corruptos | < 4 horas |
| P2 — Medium | Feature degradada, datos desactualizados | < 24 horas |
| P3 — Low | Bug no crítico | < 7 días |

### Notificación de breach

Si se detecta una vulneración de datos:
1. Contener el incidente (desactivar el endpoint/servicio afectado)
2. Evaluar alcance (qué datos, cuántos usuarios)
3. Notificar a usuarios afectados en < 72 horas
4. Reportar a autoridad de protección de datos si aplica (GDPR)
5. Post-mortem público en < 30 días

---

## Checklist de seguridad (pre-deploy)

- [ ] Variables de entorno validadas, no hay secretos en código
- [ ] Rate limiting configurado en todos los endpoints
- [ ] CORS restrictivo (solo dominios autorizados)
- [ ] File upload con validación de MIME y tamaño
- [ ] Todas las queries via ORM o queries parametrizadas
- [ ] Headers de seguridad configurados (HSTS, CSP, X-Frame-Options)
- [ ] Logs sin datos sensibles (no loggear passwords ni tokens)
- [ ] Dependencias sin CVE conocidas (`pip audit`, `npm audit`)
- [ ] Backup de base de datos funcionando y probado
