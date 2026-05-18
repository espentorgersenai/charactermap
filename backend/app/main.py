import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = structlog.get_logger()

app = FastAPI(title="Character Map API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8201", "https://charactermap.torgersen.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
