from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import admin, altcha, auth, files


def cli() -> None:
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


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

app.include_router(admin.router)
app.include_router(altcha.router)
app.include_router(auth.router)
app.include_router(files.router)
