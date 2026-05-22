import numpy as np
from sklearn.ensemble import IsolationForest

from aml_detector.config import (
    CONTAMINATION,
    ISO_MAX_SAMPLES,
    ISO_N_ESTIMATORS,
    RANDOM_SEED,
)


def train_isolation_forest(X_scaled: np.ndarray, contamination: float = CONTAMINATION) -> IsolationForest:
    print("Treinando Isolation Forest...")
    iso = IsolationForest(
        n_estimators=ISO_N_ESTIMATORS,
        contamination=contamination,
        max_samples=ISO_MAX_SAMPLES,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    iso.fit(X_scaled)
    labels = iso.predict(X_scaled)
    n_anom = (labels == -1).sum()
    print(f"Anomalias detectadas: {n_anom:,}  ({n_anom / len(X_scaled) * 100:.2f}%)")
    return iso


def iso_scores(iso: IsolationForest, X_scaled: np.ndarray) -> np.ndarray:
    return -iso.decision_function(X_scaled)


def iso_labels(iso: IsolationForest, X_scaled: np.ndarray) -> np.ndarray:
    return iso.predict(X_scaled)
