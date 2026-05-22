from contextlib import asynccontextmanager

from fastapi import FastAPI

from aml_detector.api.model_store import store
from aml_detector.api.routes import router
from aml_detector.models.persistence import artifacts_exist


@asynccontextmanager
async def lifespan(app: FastAPI):
    if artifacts_exist():
        store.load()
    else:
        print(
            "Artefatos não encontrados em models/. "
            "Execute scripts/train.py --data <csv> para treinar."
        )
    yield


app = FastAPI(
    title="AML Detector API",
    description=(
        "Detecção de lavagem de dinheiro em tempo real.\n\n"
        "Pipeline: Autoencoder não supervisionado treinado no PaySim.\n"
        "Transações com erro de reconstrução (MSE) acima do threshold são flagradas."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
