import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from aml_detector.config import FEATURE_COLS


# Tipos de transação onde fraude existe (TRANSFER e CASH_OUT)
_FRAUD_TYPES = {"TRANSFER", "CASH_OUT"}


def _add_base_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Features do notebook original."""
    fe["diff_orig"] = fe["oldbalanceOrg"] - fe["newbalanceOrig"]
    fe["diff_dest"] = fe["newbalanceDest"] - fe["oldbalanceDest"]
    fe["balance_error"] = np.abs(fe["diff_orig"] - fe["amount"])
    fe["orig_zeroed"] = ((fe["oldbalanceOrg"] > 0) & (fe["newbalanceOrig"] == 0)).astype(int)
    fe["full_drain"] = (fe["amount"] / (fe["oldbalanceOrg"] + 1e-9)).clip(0, 1)
    fe["log_amount"] = np.log1p(fe["amount"])
    fe["type_enc"] = fe["type"].map(
        {"CASH_OUT": 0, "CASH_IN": 1, "DEBIT": 2, "PAYMENT": 3, "TRANSFER": 4}
    ).fillna(-1).astype(int)
    return fe


def _add_type_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Flags de tipo de transação — apenas TRANSFER e CASH_OUT têm fraude."""
    fe["is_fraud_type"] = fe["type"].isin(_FRAUD_TYPES).astype(int)
    fe["is_transfer"] = (fe["type"] == "TRANSFER").astype(int)
    fe["is_cashout"] = (fe["type"] == "CASH_OUT").astype(int)
    return fe


def _add_account_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Flags baseadas nos IDs de conta (C = cliente, M = merchant)."""
    fe["dest_is_customer"] = fe["nameDest"].str.startswith("C").astype(int)
    # Merchants nunca são origem de fraude; cliente→cliente é padrão suspeito
    fe["orig_to_customer"] = (
        fe["nameOrig"].str.startswith("C") & fe["nameDest"].str.startswith("C")
    ).astype(int)
    return fe


def _add_balance_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Features de balanço mais granulares."""
    # Destino tinha saldo zero antes — receptor "limpo" é padrão de layering
    fe["dest_had_zero"] = (fe["oldbalanceDest"] == 0).astype(int)
    # Destino ficou com saldo zero depois (saque imediato)
    fe["dest_zeroed_after"] = (fe["newbalanceDest"] == 0).astype(int)
    # Quanto do saldo de destino a transação representa
    fe["amount_ratio_dest"] = (
        fe["amount"] / (fe["oldbalanceDest"] + 1e-9)
    ).clip(0, 100)
    # Saldo restante na origem como fração do original
    fe["balance_retention_orig"] = (
        fe["newbalanceOrig"] / (fe["oldbalanceOrg"] + 1e-9)
    ).clip(0, 1)
    # Inconsistência contábil normalizada pelo valor da transação
    fe["balance_error_ratio"] = (
        fe["balance_error"] / (fe["amount"] + 1e-9)
    ).clip(0, 10)
    return fe


def _add_velocity_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Velocidade de transações por conta na mesma hora (step)."""
    orig_vel = (
        fe.groupby(["nameOrig", "step"])["amount"]
        .transform("count")
        .rename("velocity_orig")
    )
    dest_vel = (
        fe.groupby(["nameDest", "step"])["amount"]
        .transform("count")
        .rename("velocity_dest")
    )
    orig_vol = (
        fe.groupby(["nameOrig", "step"])["amount"]
        .transform("sum")
        .rename("volume_orig")
    )
    fe["velocity_orig"] = orig_vel
    fe["velocity_dest"] = dest_vel
    fe["log_volume_orig"] = np.log1p(orig_vol)
    return fe


def _add_temporal_features(fe: pd.DataFrame) -> pd.DataFrame:
    """Features temporais derivadas do step (1 step = 1 hora)."""
    fe["hour_of_day"] = fe["step"] % 24
    fe["day_of_sim"] = fe["step"] // 24
    # Transações fora do horário comercial (antes das 8h ou após 20h)
    fe["off_hours"] = (
        (fe["hour_of_day"] < 8) | (fe["hour_of_day"] >= 20)
    ).astype(int)
    return fe


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    fe = df.copy()
    fe = _add_base_features(fe)
    fe = _add_type_features(fe)
    fe = _add_account_features(fe)
    fe = _add_balance_features(fe)
    fe = _add_velocity_features(fe)
    fe = _add_temporal_features(fe)
    return fe[FEATURE_COLS].fillna(0), fe["isFraud"]


def scale_features(X_train: pd.DataFrame, X_test: pd.DataFrame | None = None):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    if X_test is not None:
        return X_train_scaled, scaler.transform(X_test), scaler
    return X_train_scaled, scaler
