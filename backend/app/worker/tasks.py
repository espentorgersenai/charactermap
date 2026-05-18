import asyncio
import structlog
from app.worker.pipeline import run_pipeline

log = structlog.get_logger()


def generate_character_map_task(job_id: str) -> None:
    """RQ entry point. Wraps the async pipeline in asyncio.run()."""
    log.info("task_started", job_id=job_id)
    asyncio.run(run_pipeline(job_id))
    log.info("task_finished", job_id=job_id)
