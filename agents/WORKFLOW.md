# Workflow de los agentes de IA

## Los tres roles

```
ChatGPT              Claude Code           Cursor
─────────            ───────────           ──────
Product &            Arquitecto &          Programador
Estrategia           Coordinador           

• Define qué         • Lee docs/           • Lee tasks/ y docs/
  construir          • Divide en tasks     • Implementa código
• Diseña UX          • Crea sprints        • Escribe tests
• Escribe docs       • Supervisa          • No toma decisiones
• Prioriza           • Actualiza docs        arquitectónicas
  backlog            • Hace commits        • Solo código
```

---

## El ciclo de trabajo

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
    ChatGPT ────────►  docs/ (fuente de verdad)              │
    define y         │                                         │
    documenta        │  00-VISION.md, 01-PRD.md, 02-ROADMAP  │
                    │  03-ARCHITECTURE.md, ...                │
                    │  20-BACKLOG.md                          │
                    └───────────────────┬─────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │                                         │
    Claude Code ────►  tasks/ (work orders)                  │
    divide y         │                                         │
    planifica        │  sprint-001.md                         │
                    │  sprint-002.md                          │
                    │  ...                                    │
                    └───────────────────┬─────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │                                         │
    Cursor ─────────►  backend/ / frontend/ (código)         │
    implementa       │                                         │
                    └─────────────────────────────────────────┘
```

---

## Flujo detallado por caso de uso

### Caso 1: Nueva feature

```
1. Joaco describe la feature a ChatGPT
   │
2. ChatGPT:
   ├── Agrega la feature a docs/01-PRD.md
   ├── Agrega items a docs/20-BACKLOG.md
   ├── (Si hay implicaciones arquitectónicas) actualiza docs/03-ARCHITECTURE.md
   └── Crea tasks/sprint-XXX.md con las tareas concretas
   │
3. Joaco trae el sprint a Claude Code:
   "Implementá el sprint tasks/sprint-001.md"
   │
4. Claude Code:
   ├── Lee los docs relevantes
   ├── Crea la estructura de archivos
   ├── Implementa el código siguiendo el diseño
   ├── Escribe los tests
   ├── Actualiza docs si encontró algo que no estaba documentado
   └── Hace commit y push
   │
5. Joaco verifica en staging que funciona
   │
6. Si hay ajustes → vuelve a Claude Code con feedback específico
```

### Caso 2: Bug reportado

```
1. Joaco describe el bug
   │
2. Claude Code:
   ├── Lee los docs relevantes para entender el comportamiento esperado
   ├── Reproduce el bug
   ├── Identifica la causa raíz
   ├── Fix + test que prueba el fix
   └── Commit: "fix: [descripción del bug]"
   │
3. Si el bug revela un problema de diseño → 
   Claude Code documenta la decisión en docs/19-DECISIONS.md
   y avisa a Joaco para discutir con ChatGPT
```

### Caso 3: Refactor o decisión técnica

```
1. Claude Code o Cursor encuentran un problema de diseño
   │
2. Lo escalan a Joaco con contexto:
   - Cuál es el problema
   - Qué opciones hay
   - Cuál recomiendan
   │
3. Joaco lo discute con ChatGPT para perspectiva de producto
   │
4. Se toma la decisión y se documenta en docs/19-DECISIONS.md
   │
5. Claude Code implementa el cambio
```

---

## Convención de archivos de sprint

```markdown
# Sprint 001 — [Objetivo del sprint]

**Período**: 2025-07-28 a 2025-08-03
**Objetivo**: Tener Docker Compose funcionando + primer crawler de Indeed

## Status: 🔄 En progreso

## Tareas

### Infra
- [x] **B-001** Docker Compose con PostgreSQL + pgvector + Redis
  - Archivos: `docker-compose.yml`, `docker-compose.override.yml`
  - ✅ Completado: 2025-07-29

### Backend
- [ ] **B-002** FastAPI skeleton + health check
  - Archivos a crear: `backend/app/main.py`, `backend/app/api/health.py`
  - Referencia: `docs/03-ARCHITECTURE.md#backend`
  - Tamaño: S

## Blockers
- (ninguno)

## Notas
- Agregar Redis a docker-compose fue necesario más temprano de lo planeado
```

---

## Reglas de comunicación entre agentes

1. **El código no es la fuente de verdad — los docs sí.**
   Si el código y los docs difieren, el código está mal.

2. **Claude Code no toma decisiones de producto.**
   Si hay ambigüedad sobre qué construir, escala a Joaco.

3. **Cursor no toma decisiones de arquitectura.**
   Si hay ambigüedad sobre cómo construir, escala a Claude Code.

4. **ChatGPT no escribe código.**
   Define qué y por qué. Claude Code y Cursor definen cómo.

5. **Cada cambio importante se documenta.**
   Si no está en `docs/`, no existe para los otros agentes.

---

## Contexto persistente del proyecto

Este proyecto vive en GitHub como fuente de verdad. Los agentes no tienen memoria persistente entre sesiones, pero el repositorio sí.

**Cada vez que empezás una nueva sesión**, el agente debe:
1. Leer `README.md` para el contexto general
2. Leer `agents/[NOMBRE].md` para su rol específico
3. Leer `tasks/sprint-activo.md` para saber qué está en progreso

---

## Historial de versiones de este workflow

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0 | 2025-07 | Versión inicial con 3 agentes |
