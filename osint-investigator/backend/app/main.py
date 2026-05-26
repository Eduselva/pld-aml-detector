import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando banco de dados...")
    await init_db()
    logger.info("Banco de dados pronto.")
    yield
    logger.info("Encerrando aplicação.")


app = FastAPI(
    title="OSINT Investigator API",
    description="Ferramenta de investigação OSINT para analistas de crimes financeiros",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import router  # noqa: E402
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "osint-investigator"}
