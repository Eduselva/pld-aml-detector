import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from aml_detector.config import RANDOM_SEED
from aml_detector.models.isolation_forest import train_isolation_forest


def find_optimal_threshold(scores: np.ndarray, y_true: np.ndarray) -> tuple[float, float]:
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    f1_scores = 2 * (precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-9)
    best_idx = f1_scores.argmax()
    return float(thresholds[best_idx]), float(f1_scores[best_idx])


def find_thresholds_by_type(
    scores: np.ndarray,
    y_true: np.ndarray,
    types: pd.Series,
) -> tuple[dict[str, float], float]:
    """Find optimal threshold per transaction type.

    Returns a dict mapping type -> threshold and a global_threshold fallback
    for types that have no fraud examples.
    """
    global_threshold, _ = find_optimal_threshold(scores, y_true)

    thresholds_by_type: dict[str, float] = {}
    for tx_type in types.unique():
        mask = (types == tx_type).values
        y_type = y_true[mask]
        if y_type.sum() == 0:
            continue
        thr, _ = find_optimal_threshold(scores[mask], y_type)
        thresholds_by_type[tx_type] = thr

    return thresholds_by_type, global_threshold


def predict_with_type_thresholds(
    scores: np.ndarray,
    types: pd.Series,
    thresholds_by_type: dict[str, float],
    global_threshold: float,
) -> np.ndarray:
    """Apply per-type threshold to each transaction.

    Falls back to global_threshold for transaction types not present in
    thresholds_by_type.
    """
    preds = np.zeros(len(scores), dtype=int)
    type_values = types.values if hasattr(types, "values") else np.array(types)
    for i, (score, tx_type) in enumerate(zip(scores, type_values)):
        thr = thresholds_by_type.get(tx_type, global_threshold)
        preds[i] = int(score > thr)
    return preds


def train_low_value_iso(
    X_scaled: np.ndarray,
    X_df: pd.DataFrame,
    y: np.ndarray,
) -> tuple[IsolationForest | None, np.ndarray | None]:
    low_value_mask = X_df["log_amount"] < X_df["log_amount"].quantile(0.72)
    n_fraud_low = y[low_value_mask].sum()

    if n_fraud_low == 0:
        return None, None

    contamination = float(y[low_value_mask].mean())
    iso_low = IsolationForest(
        n_estimators=300,
        contamination=contamination,
        max_features=0.8,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    X_low = X_scaled[low_value_mask]
    iso_low.fit(X_low[y[low_value_mask] == 0])
    scores_low = -iso_low.decision_function(X_low)
    return iso_low, (low_value_mask, scores_low)


def ensemble_predict(
    ae_scores: np.ndarray,
    ae_threshold: float,
    low_value_result: tuple | None,
) -> np.ndarray:
    final_pred = (ae_scores > ae_threshold).astype(int).copy()

    if low_value_result is not None:
        low_value_mask, scores_low = low_value_result
        contamination = scores_low.mean()
        thr_low = np.percentile(scores_low, (1 - contamination) * 100)
        pred_low = (scores_low > thr_low).astype(int)
        low_idx = np.where(low_value_mask)[0]
        final_pred[low_idx] = np.maximum(final_pred[low_idx], pred_low)

    return final_pred
