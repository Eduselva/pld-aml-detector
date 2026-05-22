import numpy as np
import pytest

from aml_detector.config import AUTOENCODER_LATENT_DIM, FEATURE_COLS
from aml_detector.models.autoencoder import (
    build_autoencoder,
    per_feature_errors,
    reconstruction_errors,
)
from aml_detector.models.ensemble import ensemble_predict, find_optimal_threshold
from aml_detector.models.isolation_forest import iso_scores, train_isolation_forest


class TestBuildAutoencoder:
    def test_output_shape_matches_input(self, scaled):
        X_scaled, _ = scaled
        ae = build_autoencoder(X_scaled.shape[1])
        out = ae.predict(X_scaled[:10], verbose=0)
        assert out.shape == X_scaled[:10].shape

    def test_has_latent_layer(self, scaled):
        X_scaled, _ = scaled
        ae = build_autoencoder(X_scaled.shape[1])
        layer_names = [l.name for l in ae.layers]
        assert "latent" in layer_names

    def test_input_output_same_dim(self, scaled):
        X_scaled, _ = scaled
        input_dim = X_scaled.shape[1]
        ae = build_autoencoder(input_dim)
        assert ae.input_shape == (None, input_dim)
        assert ae.output_shape == (None, input_dim)

    def test_latent_dim_is_bottleneck(self, scaled):
        X_scaled, _ = scaled
        ae = build_autoencoder(X_scaled.shape[1])
        latent_layer = ae.get_layer("latent")
        assert latent_layer.units == AUTOENCODER_LATENT_DIM

    def test_custom_dims(self):
        ae = build_autoencoder(input_dim=10, encoder_layers=[8, 4], latent_dim=2)
        assert ae.input_shape == (None, 10)
        assert ae.output_shape == (None, 10)


class TestReconstructionErrors:
    def test_shape(self, trained_autoencoder, scaled):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        errors = reconstruction_errors(ae, X_scaled)
        assert errors.shape == (len(X_scaled),)

    def test_non_negative(self, trained_autoencoder, scaled):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        errors = reconstruction_errors(ae, X_scaled)
        assert (errors >= 0).all()

    def test_per_feature_shape(self, trained_autoencoder, scaled):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        feat_err = per_feature_errors(ae, X_scaled)
        assert feat_err.shape == X_scaled.shape

    def test_per_feature_non_negative(self, trained_autoencoder, scaled):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        feat_err = per_feature_errors(ae, X_scaled)
        assert (feat_err >= 0).all()

    def test_fraud_separation_direction(self, trained_autoencoder, scaled, features):
        """Após treino em normais, fraudes devem ter erro médio >= normais."""
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        errors = reconstruction_errors(ae, X_scaled)
        # Com apenas 3 épocas sintéticas não exige separação perfeita,
        # mas o erro das fraudes não deve ser muito menor que o das normais
        mean_fraud = errors[y == 1].mean()
        mean_normal = errors[y == 0].mean()
        assert mean_fraud >= mean_normal * 0.5


class TestIsolationForest:
    def test_returns_model(self, trained_iso):
        from sklearn.ensemble import IsolationForest
        assert isinstance(trained_iso, IsolationForest)

    def test_scores_shape(self, trained_iso, scaled):
        X_scaled, _ = scaled
        scores = iso_scores(trained_iso, X_scaled)
        assert scores.shape == (len(X_scaled),)

    def test_scores_finite(self, trained_iso, scaled):
        X_scaled, _ = scaled
        scores = iso_scores(trained_iso, X_scaled)
        assert np.isfinite(scores).all()

    def test_predict_binary(self, trained_iso, scaled):
        X_scaled, _ = scaled
        labels = trained_iso.predict(X_scaled)
        assert set(labels).issubset({-1, 1})


class TestEnsemble:
    def test_find_threshold_is_float(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, f1 = find_optimal_threshold(scores, y)
        assert isinstance(thr, float)
        assert isinstance(f1, float)

    def test_threshold_within_score_range(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        assert scores.min() <= thr <= scores.max()

    def test_f1_bounded(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        _, f1 = find_optimal_threshold(scores, y)
        assert 0.0 <= f1 <= 1.0

    def test_ensemble_predict_binary(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, low_value_result=None)
        assert set(preds).issubset({0, 1})

    def test_ensemble_predict_shape(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, low_value_result=None)
        assert preds.shape == scores.shape
