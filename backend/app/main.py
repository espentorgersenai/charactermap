import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.resolve import router as resolve_router
from app.routes.jobs import router as jobs_router
from app.routes.artifacts import router as artifacts_router

log = structlog.get_logger()

app = FastAPI(title="Character Map API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8201", "https://charactermap.torgersen.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resolve_router)
app.include_router(jobs_router)
app.include_router(artifacts_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
