from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.codex_bridge import CodexBridge
from app.jobs import JobStore
from app.routers import analyses, assistant, debugging, health
from app.settings import settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.jobs = JobStore(settings)
    application.state.codex = CodexBridge(settings.codex_executable, Path(settings.codex_home)) if settings.codex_enabled else None
    try:
        yield
    finally:
        application.state.jobs.close()
        if application.state.codex:
            application.state.codex.close()


app = FastAPI(
    title="Codandy API",
    version="0.1.0",
    description="Static repository analysis and grounded codebase exploration.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(debugging.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(analyses.router, prefix="/api")
