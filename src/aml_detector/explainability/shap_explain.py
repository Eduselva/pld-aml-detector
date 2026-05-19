import numpy as np
import matplotlib.pyplot as plt
import shap
import keras

from aml_detector.config import FEATURE_COLS, OUTPUTS_DIR, RANDOM_SEED


def explain_isolation_forest(iso, X_scaled: np.ndarray, n_samples: int = 5000):
    print("Calculando SHAP values — Isolation Forest...")
    explainer = shap.TreeExplainer(iso)
    shap_values = explainer.shap_values(X_scaled[:n_samples])
    print("✓ Calculado")
    return explainer, shap_values


def plot_iso_shap_summary(shap_values: np.ndarray, X_scaled: np.ndarray, n_samples: int = 5000, save: bool = True):
    fig = plt.figure(figsize=(9, 5))
    shap.summary_plot(
        shap_values, X_scaled[:n_samples], feature_names=FEATURE_COLS,
        plot_type="bar", show=False, color="#4A7BB5"
    )
    plt.title("Isolation Forest — Importância Global (SHAP)", pad=10)
    plt.tight_layout()
    if save:
        path = OUTPUTS_DIR / "shap_iso_summary.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"SHAP IF summary salvo em {path}")
    return fig


def plot_iso_shap_beeswarm(shap_values: np.ndarray, X_scaled: np.ndarray, n_samples: int = 5000, save: bool = True):
    fig = plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_values, X_scaled[:n_samples], feature_names=FEATURE_COLS, show=False)
    plt.title("Isolation Forest — Beeswarm SHAP", pad=10)
    plt.tight_layout()
    if save:
        path = OUTPUTS_DIR / "shap_iso_beeswarm.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"SHAP IF beeswarm salvo em {path}")
    return fig


def build_ae_score_model(ae: keras.Model) -> keras.Model:
    inp = ae.input
    decoded = ae.output
    mse_output = keras.layers.Lambda(
        lambda tensors: keras.ops.mean(
            keras.ops.square(tensors[0] - tensors[1]), axis=1, keepdims=True
        )
    )([inp, decoded])
    return keras.Model(inputs=inp, outputs=mse_output)


def explain_autoencoder(
    ae: keras.Model,
    X_scaled: np.ndarray,
    ae_scores: np.ndarray,
    y,
    n_top: int = 300,
    n_background: int = 200,
    n_random: int = 200,
):
    print("Calculando SHAP values — Autoencoder (GradientExplainer)...")
    score_model = build_ae_score_model(ae)

    rng = np.random.default_rng(RANDOM_SEED)
    bg_idx = rng.choice(np.where(y == 0)[0], size=n_background, replace=False)
    background = X_scaled[bg_idx]

    top_idx = np.argsort(ae_scores)[-n_top:][::-1]
    rand_idx = rng.choice(len(X_scaled), size=n_random, replace=False)
    eval_idx = np.unique(np.concatenate([top_idx, rand_idx]))

    explainer = shap.GradientExplainer(score_model, background)
    shap_raw = explainer.shap_values(X_scaled[eval_idx])
    shap_values = (shap_raw[0] if isinstance(shap_raw, list) else shap_raw).squeeze()
    print("✓ Calculado")
    return explainer, shap_values, eval_idx, top_idx


def plot_ae_shap_summary(shap_values: np.ndarray, X_scaled: np.ndarray, eval_idx: np.ndarray, save: bool = True):
    fig = plt.figure(figsize=(9, 5))
    shap.summary_plot(
        shap_values, X_scaled[eval_idx], feature_names=FEATURE_COLS,
        plot_type="bar", show=False, color="#C0392B"
    )
    plt.title("Autoencoder — Importância das Features para Erro de Reconstrução", pad=10)
    plt.tight_layout()
    if save:
        path = OUTPUTS_DIR / "shap_ae_summary.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"SHAP AE summary salvo em {path}")
    return fig


def plot_ae_shap_delta(
    shap_values: np.ndarray,
    eval_idx: np.ndarray,
    top_idx: np.ndarray,
    save: bool = True,
):
    top_mask = np.isin(eval_idx, top_idx)
    mean_top = np.abs(shap_values[top_mask]).mean(axis=0)
    mean_norm = np.abs(shap_values[~top_mask]).mean(axis=0)
    delta = mean_top - mean_norm

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#C0392B" if d > 0 else "#2980B9" for d in delta]
    ax.barh(FEATURE_COLS, delta, color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ |SHAP| médio  (suspeitas − normais)")
    ax.set_title("Autoencoder — Features que mais diferenciam suspeitas de normais")
    plt.tight_layout()
    if save:
        path = OUTPUTS_DIR / "shap_ae_delta.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"SHAP AE delta salvo em {path}")
    return fig
