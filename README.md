# 📡 radar-social

**Radar Social** es una plataforma OSINT cívica diseñada para democratizar el acceso y análisis de datos de contratación pública (SEACE) y financiamiento político (ONPE). Su objetivo es proporcionar transparencia mediante la monitorización, extracción y análisis estructurado de datos que son críticos para la vigilancia ciudadana.

## 🚀 Impacto Cívico
- **Transparencia Activa**: Automatización en la recolección de resoluciones, contratos y declaraciones.
- **Trazabilidad**: Relacionar actores políticos y proveedores del estado mediante análisis de grafos y datos estructurados.
- **Alertas Tempranas**: Detección de patrones anómalos o sospechosos en adjudicaciones.

## 🛠️ Setup Local (UV)

El proyecto utiliza `uv` para la gestión ultrarrápida de dependencias de Python.

```bash
# 1. Clonar el repositorio
git clone <url-repo>
cd radar-social

# 2. Sincronizar dependencias y crear el entorno virtual
uv sync --all-extras

# 3. Activar el entorno virtual
# En Windows:
.venv\Scripts\activate
# En Linux/Mac:
source .venv/bin/activate
```

## 💻 Comandos CLI y Daemon

| Comando | Descripción |
|---------|-------------|
| `uv run ruff check src/` | Ejecuta el linter sobre el código base |
| `uv run mypy src/` | Realiza el análisis estático de tipos |
| `uv run pytest tests/` | Ejecuta la suite de pruebas unitarias |
| `bash .agents/pre_commit_gate.sh` | Ejecuta el pre-flight gate antes de un commit |

*Próximamente: Comandos del CLI y Daemon para ingesta y análisis.*
