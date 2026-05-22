import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status

from aml_detector.api.model_store import store
from aml_detector.api.schemas import (
    BatchInput,
    BatchResult,
    HealthResponse,
    ModelInfoResponse,
    PredictionResult,
    TransactionInput,
)
from aml_detector.config import FEATURE_COLS
from aml_detector.features.engineering import build_features
from aml_detector.models.autoencoder import reconstruction_errors

router = APIRouter()


def _transaction_to_df(tx: TransactionInput) -> pd.DataFrame:
    """Converte um TransactionInput em DataFrame compatível com build_features."""
    return pd.DataFrame([{
        "step": tx.step,
        "type": tx.type.value,
        "amount": tx.amount,
        "nameOrig": tx.nameOrig,
        "oldbalanceOrg": tx.oldbalanceOrg,
        "newbalanceOrig": tx.newbalanceOrig,
        "nameDest": tx.nameDest,
        "oldbalanceDest": tx.oldbalanceDest,
        "newbalanceDest": tx.newbalanceDest,
        "isFraud": 0,          # placeholder — não usado em inferência
        "isFlaggedFraud": 0,
    }])


def _score_to_result(score: float, threshold: float) -> PredictionResult:
    is_fraud = score > threshold
    # Distância normalizada ao threshold — 0.5 = exatamente no threshold
    confidence = float(np.clip(score / (2 * threshold + 1e-9), 0.0, 1.0))
    return PredictionResult(
        is_fraud=is_fraud,
        risk_score=round(float(score), 6),
        threshold=round(threshold, 6),
        confidence=round(confidence, 4),
    )


def _predict_df(df: pd.DataFrame) -> np.ndarray:
    """Roda o pipeline completo e retorna scores MSE."""
    if not store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo não carregado. Treine e salve os artefatos primeiro.",
        )
    X, _ = build_features(df)
    X_scaled = store.scaler.transform(X)
    return reconstruction_errors(store.autoencoder, X_scaled)


@router.get("/health", response_model=HealthResponse, tags=["Sistema"])
def health():
    return HealthResponse(
        status="ok" if store.is_ready else "degraded",
        model_loaded=store.is_ready,
        model_version=store.version if store.is_ready else None,
    )


@router.get("/model/info", response_model=ModelInfoResponse, tags=["Sistema"])
def model_info():
    if not store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo não carregado.",
        )
    return ModelInfoResponse(
        model_version=store.version,
        threshold=store.threshold,
        feature_count=len(FEATURE_COLS),
        features=FEATURE_COLS,
        metrics=store.metrics,
    )


@router.post("/predict", response_model=PredictionResult, tags=["Predição"])
def predict(transaction: TransactionInput):
    df = _transaction_to_df(transaction)
    scores = _predict_df(df)
    return _score_to_result(scores[0], store.threshold)


@router.post("/predict/batch", response_model=BatchResult, tags=["Predição"])
def predict_batch(payload: BatchInput):
    rows = []
    for tx in payload.transactions:
        rows.append({
            "step": tx.step,
            "type": tx.type.value,
            "amount": tx.amount,
            "nameOrig": tx.nameOrig,
            "oldbalanceOrg": tx.oldbalanceOrg,
            "newbalanceOrig": tx.newbalanceOrig,
            "nameDest": tx.nameDest,
            "oldbalanceDest": tx.oldbalanceDest,
            "newbalanceDest": tx.newbalanceDest,
            "isFraud": 0,
            "isFlaggedFraud": 0,
        })
    df = pd.DataFrame(rows)
    scores = _predict_df(df)

    results = [_score_to_result(s, store.threshold) for s in scores]
    flagged = sum(r.is_fraud for r in results)
    return BatchResult(
        results=results,
        total=len(results),
        flagged=flagged,
        flag_rate=round(flagged / len(results), 4),
    )
