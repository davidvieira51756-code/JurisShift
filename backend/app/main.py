from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.db.database import get_connection, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="JurisShift API",
    description="Portuguese case-law divergence analysis prototype.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "jurisshift",
    }


@app.get("/api/stats")
def stats():
    with get_connection() as connection:
        case_count = connection.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0]

        issue_count = connection.execute(
            "SELECT COUNT(*) FROM issues"
        ).fetchone()[0]

        stance_count = connection.execute(
            "SELECT COUNT(*) FROM stances"
        ).fetchone()[0]

    return {
        "cases": case_count,
        "issues": issue_count,
        "stances": stance_count,
    }