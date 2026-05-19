import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

from aml_detector.config import FEATURE_COLS


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    fe = df.copy()

    fe["diff_orig"] = fe["oldbalanceOrg"] - fe["newbalanceOrig"]
    fe["diff_dest"] = fe["newbalanceDest"] - fe["oldbalanceDest"]
    fe["balance_error"] = np.abs(fe["diff_orig"] - fe["amount"])
    fe["orig_zeroed"] = ((fe["oldbalanceOrg"] > 0) & (fe["newbalanceOrig"] == 0)).astype(int)
    fe["full_drain"] = (fe["amount"] / (fe["oldbalanceOrg"] + 1e-9)).clip(0, 1)
    fe["log_amount"] = np.log1p(fe["amount"])

    le = LabelEncoder()
    fe["type_enc"] = le.fit_transform(fe["type"])

    return fe[FEATURE_COLS].fillna(0), fe["isFraud"]


def scale_features(X_train: pd.DataFrame, X_test: pd.DataFrame | None = None):
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    if X_test is not None:
        return X_train_scaled, scaler.transform(X_test), scaler
    return X_train_scaled, scaler
