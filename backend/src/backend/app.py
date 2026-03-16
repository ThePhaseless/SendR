from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db
from backend.routers import auth, files

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="SendR API",
    description="WeTransfer-like file sharing service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["content-type", "authorization"],
)

app.include_router(auth.router)
app.include_router(files.router)

# Serve Angular frontend static files in production
if STATIC_DIR.is_dir():
    _resolved_static = STATIC_DIR.resolve()
    app.mount("/assets", StaticFiles(directory=str(_resolved_static / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(_request: Request, full_path: str):  # noqa: ARG001
        file_path = (STATIC_DIR / full_path).resolve()
        # Prevent path traversal by ensuring resolved path stays under STATIC_DIR
        if not str(file_path).startswith(str(_resolved_static)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_resolved_static / "index.html"))
