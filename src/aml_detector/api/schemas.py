from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    CASH_OUT = "CASH_OUT"
    CASH_IN = "CASH_IN"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    DEBIT = "DEBIT"


class TransactionInput(BaseModel):
    step: int = Field(..., ge=1, description="Hora da simulação (1 step = 1 hora)")
    type: TransactionType
    amount: float = Field(..., ge=0, description="Valor da transação")
    nameOrig: str = Field(..., description="ID da conta de origem")
    oldbalanceOrg: float = Field(..., ge=0)
    newbalanceOrig: float = Field(..., ge=0)
    nameDest: str = Field(..., description="ID da conta de destino")
    oldbalanceDest: float = Field(..., ge=0)
    newbalanceDest: float = Field(..., ge=0)

    model_config = {"json_schema_extra": {
        "example": {
            "step": 1,
            "type": "TRANSFER",
            "amount": 250000.0,
            "nameOrig": "C123456789",
            "oldbalanceOrg": 250000.0,
            "newbalanceOrig": 0.0,
            "nameDest": "C987654321",
            "oldbalanceDest": 0.0,
            "newbalanceDest": 250000.0,
        }
    }}


class PredictionResult(BaseModel):
    is_fraud: bool
    risk_score: float = Field(..., description="Erro de reconstrução do Autoencoder (MSE)")
    threshold: float = Field(..., description="Threshold usado para classificação")
    confidence: float = Field(..., description="Distância normalizada do threshold [0-1]")
    model: Literal["autoencoder"] = "autoencoder"


class BatchInput(BaseModel):
    transactions: list[TransactionInput] = Field(..., min_length=1, max_length=1000)


class BatchResult(BaseModel):
    results: list[PredictionResult]
    total: int
    flagged: int
    flag_rate: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_loaded: bool
    model_version: str | None = None


class ModelInfoResponse(BaseModel):
    model_version: str
    threshold: float
    feature_count: int
    features: list[str]
    metrics: dict[str, float]
