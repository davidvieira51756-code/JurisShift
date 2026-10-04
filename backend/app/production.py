from pathlib import Path

from fastapi.staticfiles import StaticFiles

from backend.app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


if not FRONTEND_DIST.is_dir():
    raise RuntimeError(
        "Frontend build não encontrado em frontend/dist. "
        "Execute o build do frontend antes de iniciar a aplicação de produção."
    )


app.mount(
    "/",
    StaticFiles(
        directory=str(FRONTEND_DIST),
        html=True,
    ),
    name="frontend",
)
