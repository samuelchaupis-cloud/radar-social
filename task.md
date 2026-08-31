# Tareas Fase 1: Setup y Tooling Base

- [x] Inicializar directorio `radar-social`.
- [x] Configurar `pyproject.toml` con `uv` y dependencias base (`httpx`, `selectolax`, `pydantic`, `sqlalchemy`, `alembic`, `structlog`, `tenacity`).
- [x] Configurar linter y formatter (`ruff`), type checker (`mypy`) y testing (`pytest`).
- [x] Generar script de validación estricta `.agents/pre_commit_gate.sh`.
- [x] Generar reglas de código `.agents/code_rules.md` (Conventional Commits ES, 0 tests rotos).
- [x] Escribir `README.md` con Pitch de Impacto Cívico y Setup.
- [ ] Implementar estructura de directorios (`src/`, `tests/`, `config/`).
- [ ] Configurar logs base (JSON estruturado con `structlog`).
- [ ] Crear el primer test unitario dummy para asegurar que el pipeline funcione.
