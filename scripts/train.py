"""
Pipeline completo de treinamento AML.

Uso:
    python scripts/train.py --data /path/to/PS_log.csv
    python scripts/train.py --data /path/to/PS_log.csv --no-graph --no-shap
"""
import argparse
import warnings

import numpy as np
import tensorflow as tf

warnings.filterwarnings("ignore")

from aml_detector.config import RANDOM_SEED
from aml_detector.data.loader import load_paysim
from aml_detector.features.engineering import build_features, scale_features
from aml_detector.models.isolation_forest import train_isolation_forest, iso_scores
from aml_detector.models.autoencoder import train_autoencoder, reconstruction_errors
from aml_detector.models.ensemble import find_optimal_threshold, train_low_value_iso, ensemble_predict
from aml_detector.evaluation.metrics import (
    evaluate_models,
    plot_roc_comparison,
    plot_score_distributions,
    plot_pr_and_f1,
    print_classification_reports,
    analyze_errors,
)
from aml_detector.explainability.shap_explain import (
    explain_isolation_forest,
    plot_iso_shap_summary,
    explain_autoencoder,
    plot_ae_shap_summary,
    plot_ae_shap_delta,
)
from aml_detector.graph.analysis import build_graph, compute_graph_metrics, plot_ego_networks, export_pyvis

np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)


def parse_args():
    parser = argparse.ArgumentParser(description="AML Anomaly Detection — treinamento completo")
    parser.add_argument("--data", required=True, help="Caminho para o CSV do PaySim")
    parser.add_argument("--no-shap", action="store_true", help="Pula o cálculo de SHAP")
    parser.add_argument("--no-graph", action="store_true", help="Pula a análise de grafo")
    parser.add_argument("--no-pyvis", action="store_true", help="Pula a exportação do grafo interativo")
    return parser.parse_args()


def main():
    args = parse_args()

    # ── 1. Dados ──────────────────────────────────────────────────────────
    print("\n=== 1. Carregando dados ===")
    df = load_paysim(args.data)

    # ── 2. Features ───────────────────────────────────────────────────────
    print("\n=== 2. Feature Engineering ===")
    X, y = build_features(df)
    X_scaled, scaler = scale_features(X)
    print(f"Features: {list(X.columns)}")
    print(f"Shape: {X.shape}")

    # ── 3. Isolation Forest ───────────────────────────────────────────────
    print("\n=== 3. Isolation Forest ===")
    iso = train_isolation_forest(X_scaled)
    scores_iso = iso_scores(iso, X_scaled)
    labels_iso = iso.predict(X_scaled)

    # ── 4. Autoencoder ────────────────────────────────────────────────────
    print("\n=== 4. Autoencoder ===")
    ae, history = train_autoencoder(X_scaled, y)
    scores_ae = reconstruction_errors(ae, X_scaled)

    # ── 5. Avaliação ──────────────────────────────────────────────────────
    print("\n=== 5. Avaliação ===")
    evaluate_models(y, {"Isolation Forest": scores_iso, "Autoencoder (MSE)": scores_ae})

    plot_roc_comparison(y, {"Isolation Forest": scores_iso, "Autoencoder (MSE)": scores_ae})
    plot_score_distributions(y, {"Isolation Forest": scores_iso, "Autoencoder (MSE)": scores_ae})

    best_thr, best_f1 = find_optimal_threshold(scores_ae, y)
    print(f"\nThreshold ótimo (F1): {best_thr:.4f}  →  F1={best_f1:.3f}")
    plot_pr_and_f1(y, scores_ae, best_thr)

    y_pred_iso = (labels_iso == -1).astype(int)
    y_pred_ae = (scores_ae > best_thr).astype(int)

    # ── 6. Ensemble ───────────────────────────────────────────────────────
    print("\n=== 6. Ensemble ===")
    _, low_value_result = train_low_value_iso(X_scaled, X, y.values)
    y_pred_ensemble = ensemble_predict(scores_ae, best_thr, low_value_result)

    print_classification_reports(y, {
        "Isolation Forest": y_pred_iso,
        "Autoencoder": y_pred_ae,
        "Ensemble": y_pred_ensemble,
    })
    analyze_errors(scores_ae, y, X, df, best_thr)

    # ── 7. SHAP ───────────────────────────────────────────────────────────
    if not args.no_shap:
        print("\n=== 7. SHAP ===")
        _, iso_sv = explain_isolation_forest(iso, X_scaled)
        plot_iso_shap_summary(iso_sv, X_scaled)

        _, ae_sv, eval_idx, top_idx = explain_autoencoder(ae, X_scaled, scores_ae, y)
        plot_ae_shap_summary(ae_sv, X_scaled, eval_idx)
        plot_ae_shap_delta(ae_sv, eval_idx, top_idx)

    # ── 8. Graph ──────────────────────────────────────────────────────────
    if not args.no_graph:
        print("\n=== 8. Graph Analysis ===")
        G = build_graph(df, scores_ae)
        df_metrics = compute_graph_metrics(G)
        plot_ego_networks(G, df_metrics)
        if not args.no_pyvis:
            export_pyvis(G, df_metrics)

    print("\n✓ Pipeline concluído. Outputs em outputs/")


if __name__ == "__main__":
    main()
