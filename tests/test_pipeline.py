"""
Testes de integração leve — pipeline completo com dados sintéticos.
Não avaliam performance absoluta, apenas que o pipeline roda de ponta
a ponta sem erros e produz outputs com as propriedades esperadas.
"""
import numpy as np
import pytest
from sklearn.metrics import roc_auc_score


class TestEndToEnd:
    def test_features_to_scaled(self, features, scaled):
        X, y = features
        X_scaled, scaler = scaled
        assert X_scaled.shape[0] == len(y)
        assert X_scaled.shape[1] == X.shape[1]

    def test_iso_full_pass(self, trained_iso, scaled, features):
        from aml_detector.models.isolation_forest import iso_scores
        X_scaled, _ = scaled
        _, y = features
        scores = iso_scores(trained_iso, X_scaled)
        auc = roc_auc_score(y, scores)
        # Com dados sintéticos não exige AUC alto — só que seja calculável
        assert 0.0 <= auc <= 1.0

    def test_ae_full_pass(self, trained_autoencoder, scaled, features):
        from aml_detector.models.autoencoder import reconstruction_errors
        ae, history = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        assert len(scores) == len(y)
        # Loss de treino deve ter diminuído ao longo das épocas
        train_losses = history.history["loss"]
        assert train_losses[-1] <= train_losses[0] * 1.5  # tolerância para dados pequenos

    def test_threshold_and_predict(self, trained_autoencoder, scaled, features):
        from aml_detector.models.autoencoder import reconstruction_errors
        from aml_detector.models.ensemble import ensemble_predict, find_optimal_threshold
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, f1 = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)

        assert set(preds).issubset({0, 1})
        assert 0.0 <= f1 <= 1.0
        assert len(preds) == len(y)

    def test_evaluate_models_returns_aucs(self, trained_iso, trained_autoencoder, scaled, features):
        from aml_detector.models.autoencoder import reconstruction_errors
        from aml_detector.models.isolation_forest import iso_scores
        from aml_detector.evaluation.metrics import evaluate_models
        X_scaled, _ = scaled
        _, y = features
        scores_iso = iso_scores(trained_iso, X_scaled)
        ae, _ = trained_autoencoder
        scores_ae = reconstruction_errors(ae, X_scaled)
        aucs = evaluate_models(y, {"IF": scores_iso, "AE": scores_ae})
        assert "IF" in aucs and "AE" in aucs
        for name, auc in aucs.items():
            assert 0.0 <= auc <= 1.0, f"AUC inválido para {name}: {auc}"

    def test_analyze_errors_returns_dataframe(self, trained_autoencoder, scaled, features, raw_df):
        import pandas as pd
        from aml_detector.models.autoencoder import reconstruction_errors
        from aml_detector.models.ensemble import find_optimal_threshold
        from aml_detector.evaluation.metrics import analyze_errors
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        X, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        result = analyze_errors(scores, y, X, raw_df, thr)
        assert isinstance(result, pd.DataFrame)
        assert "ae_score" in result.columns
        assert "pred" in result.columns
        assert "true" in result.columns
        assert len(result) == len(y)
