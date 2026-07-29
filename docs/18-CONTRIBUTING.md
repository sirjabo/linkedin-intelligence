# 18 · Contributing

## Cómo contribuir

Este repositorio es el core del portfolio de AI Engineering de Joaco. Las contribuciones externas son bienvenidas pero deben alinearse con la visión del proyecto.

### Tipos de contribuciones aceptadas

- Bug fixes
- Mejoras de performance
- Nuevas fuentes de datos
- Mejoras de documentación
- Tests adicionales

### Antes de empezar

1. **Abrí un issue** describiendo el cambio antes de hacer el PR.
2. Para cambios grandes, esperá confirmación antes de invertir tiempo.
3. Revisá [DECISIONS.md](./19-DECISIONS.md) para entender las decisiones arquitectónicas tomadas.

---

## Setup del entorno

```bash
# 1. Fork del repo
gh repo fork sirjabo/linkedin-intelligence

# 2. Clonar tu fork
git clone https://github.com/TU_USUARIO/linkedin-intelligence
cd linkedin-intelligence

# 3. Configurar el repo original como upstream
git remote add upstream https://github.com/sirjabo/linkedin-intelligence

# 4. Instalar pre-commit hooks
pip install pre-commit
pre-commit install

# 5. Levantar el entorno de desarrollo
cp .env.example .env
docker compose up -d
cd backend && pip install -r requirements-dev.txt
alembic upgrade head
```

---

## Flujo de trabajo

```bash
# 1. Sincronizar con upstream
git fetch upstream
git checkout main
git merge upstream/main

# 2. Crear rama para tu cambio
git checkout -b fix/ats-score-calculation

# 3. Hacer los cambios + tests
# ...

# 4. Verificar que todo pasa
ruff check . && mypy . && pytest

# 5. Commit con conventional commits
git commit -m "fix: correct ATS score when critical keywords are missing"

# 6. Push y crear PR
git push origin fix/ats-score-calculation
gh pr create
```

---

## Checklist para PRs

Antes de abrir un PR, verificar:

- [ ] Tests agregados o actualizados para los cambios
- [ ] `pytest` pasa al 100%
- [ ] `ruff check .` sin errores
- [ ] `mypy .` sin errores
- [ ] Documentación actualizada si el cambio lo requiere
- [ ] DECISIONS.md actualizado si se tomó una decisión arquitectónica

---

## Reportar bugs

Usar el template de issue en `.github/ISSUE_TEMPLATE/bug_report.md`.

Incluir siempre:
- Qué estabas haciendo
- Qué esperabas que pasara
- Qué pasó realmente
- Versión (output de `GET /health`)
