import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    RocCurveDisplay,
    precision_recall_curve,
    auc,
)

from aml_detector.config import OUTPUTS_DIR


def evaluate_models(y_true: np.ndarray, scores: dict[str, np.ndarray]) -> dict[str, float]:
    results = {}
    for name, score in scores.items():
        auc_score = roc_auc_score(y_true, score)
        results[name] = auc_score
        print(f"AUC-ROC  {name:<30}: {auc_score:.4f}")
    return results


def plot_roc_comparison(y_true: np.ndarray, scores: dict[str, np.ndarray], save: bool = True):
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = ["steelblue", "tomato", "seagreen", "darkorange"]

    for (name, score), color in zip(scores.items(), colors):
        auc_val = roc_auc_score(y_true, score)
        RocCurveDisplay.from_predictions(
            y_true, score, name=f"{name}  (AUC={auc_val:.3f})", ax=ax, color=color
        )

    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_title("ROC — Comparação dos Modelos")
    plt.tight_layout()

    if save:
        path = OUTPUTS_DIR / "roc_comparison.png"
        fig.savefig(path, dpi=150)
        print(f"ROC salvo em {path}")
    return fig


def plot_score_distributions(y_true: np.ndarray, scores: dict[str, np.ndarray], save: bool = True):
    n = len(scores)
    fig, axes = plt.subplots(1, n, figsize=(7 * n, 5))
    if n == 1:
        axes = [axes]

    for ax, (name, score) in zip(axes, scores.items()):
        ax.hist(score[y_true == 0], bins=80, alpha=0.6, label="Normal", color="steelblue", density=True)
        ax.hist(score[y_true == 1], bins=80, alpha=0.7, label="Fraude", color="tomato", density=True)
        ax.set_title(name)
        ax.set_xlabel("Score")
        ax.legend()

    fig.suptitle("Distribuição dos Scores de Anomalia", fontsize=13)
    plt.tight_layout()

    if save:
        path = OUTPUTS_DIR / "score_distributions.png"
        fig.savefig(path, dpi=150)
        print(f"Distribuições salvas em {path}")
    return fig


def plot_pr_and_f1(y_true: np.ndarray, ae_scores: np.ndarray, best_threshold: float, save: bool = True):
    precision, recall, thresholds = precision_recall_curve(y_true, ae_scores)
    pr_auc = auc(recall, precision)

    f1_scores = 2 * (precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-9)
    best_idx = f1_scores.argmax()
    best_f1 = f1_scores[best_idx]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(recall, precision, color="tomato", lw=1.5, label=f"AUC-PR = {pr_auc:.3f}")
    axes[0].axvline(
        recall[best_idx], color="gray", linestyle="--", lw=0.8,
        label=f"Recall ótimo = {recall[best_idx]:.2f}"
    )
    axes[0].set_xlabel("Recall")
    axes[0].set_ylabel("Precision")
    axes[0].set_title("Autoencoder — Curva Precision-Recall")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(thresholds, f1_scores, color="steelblue", lw=1.5)
    axes[1].axvline(
        best_threshold, color="tomato", linestyle="--", lw=1,
        label=f"Threshold ótimo = {best_threshold:.4f}\nF1 = {best_f1:.3f}"
    )
    axes[1].set_xlabel("Threshold (MSE)")
    axes[1].set_ylabel("F1-score")
    axes[1].set_title("F1 por threshold — Autoencoder")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    plt.tight_layout()

    if save:
        path = OUTPUTS_DIR / "pr_f1_curve.png"
        fig.savefig(path, dpi=150)
        print(f"Curva PR/F1 salva em {path}")
    return fig


def print_classification_reports(y_true: np.ndarray, predictions: dict[str, np.ndarray]):
    for name, pred in predictions.items():
        print(f"── {name} ──")
        print(classification_report(y_true, pred, target_names=["Normal", "Fraude"]))


def analyze_errors(
    ae_scores: np.ndarray,
    y_true: np.ndarray,
    df_features,
    df_original: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    results = pd.DataFrame({
        "ae_score": ae_scores,
        "pred": (ae_scores > threshold).astype(int),
        "true": y_true.values if hasattr(y_true, "values") else y_true,
    }, index=df_features.index)

    results = results.join(df_features)
    results["type"] = df_original["type"]

    tp = results[(results["true"] == 1) & (results["pred"] == 1)]
    fn = results[(results["true"] == 1) & (results["pred"] == 0)]

    print(f"Fraudes detectadas (TP): {len(tp):,}")
    print(f"Fraudes perdidas   (FN): {len(fn):,}")

    feat_cols = ["log_amount", "diff_orig", "balance_error", "full_drain", "orig_zeroed"]
    comparison = pd.DataFrame({
        "TP (detectadas)": tp[feat_cols].mean(),
        "FN (perdidas)": fn[feat_cols].mean(),
    })
    print("\nFeatures médias: detectadas vs perdidas")
    print(comparison.round(4))

    return results
