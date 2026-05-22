"""
Testes de contrato — invariantes que o pipeline nunca pode violar,
independente de dados sintéticos ou reais.
"""
import numpy as np
import pytest

from aml_detector.features.engineering import build_features, scale_features
from aml_detector.models.autoencoder import reconstruction_errors
from aml_detector.models.ensemble import ensemble_predict, find_optimal_threshold
from aml_detector.models.isolation_forest import iso_scores


class TestDataContract:
    """O dataset de entrada deve satisfazer estas propriedades."""

    REQUIRED_COLUMNS = {
        "step", "type", "amount",
        "nameOrig", "oldbalanceOrg", "newbalanceOrig",
        "nameDest", "oldbalanceDest", "newbalanceDest",
        "isFraud",
    }

    def test_required_columns_present(self, raw_df):
        missing = self.REQUIRED_COLUMNS - set(raw_df.columns)
        assert not missing, f"Colunas faltando: {missing}"

    def test_amount_non_negative(self, raw_df):
        assert (raw_df["amount"] >= 0).all()

    def test_balances_non_negative(self, raw_df):
        for col in ["oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]:
            assert (raw_df[col] >= 0).all(), f"{col} tem valores negativos"

    def test_label_is_binary(self, raw_df):
        assert set(raw_df["isFraud"].unique()).issubset({0, 1})

    def test_type_values_known(self, raw_df):
        known = {"CASH_OUT", "CASH_IN", "DEBIT", "PAYMENT", "TRANSFER"}
        unknown = set(raw_df["type"].unique()) - known
        assert not unknown, f"Tipos desconhecidos: {unknown}"

    def test_fraud_only_in_transfer_cashout(self, raw_df):
        fraud_types = raw_df[raw_df["isFraud"] == 1]["type"].unique()
        assert set(fraud_types).issubset({"TRANSFER", "CASH_OUT"})

    def test_step_positive(self, raw_df):
        assert (raw_df["step"] >= 1).all()


class TestFeatureContract:
    """O vetor de features deve satisfazer estas propriedades após engineering."""

    def test_no_nan(self, features):
        X, _ = features
        assert not X.isnull().values.any()

    def test_no_inf(self, features):
        X, _ = features
        assert np.isfinite(X.values).all()

    def test_scaled_no_nan(self, scaled):
        X_scaled, _ = scaled
        assert np.isfinite(X_scaled).all()

    def test_full_drain_in_unit_interval(self, features):
        X, _ = features
        assert X["full_drain"].between(0, 1).all()

    def test_balance_retention_in_unit_interval(self, features):
        X, _ = features
        assert X["balance_retention_orig"].between(0, 1).all()

    def test_amount_ratio_dest_non_negative(self, features):
        X, _ = features
        assert (X["amount_ratio_dest"] >= 0).all()

    def test_velocities_at_least_one(self, features):
        X, _ = features
        assert (X["velocity_orig"] >= 1).all()
        assert (X["velocity_dest"] >= 1).all()

    def test_binary_features_are_binary(self, features):
        X, _ = features
        for col in ["is_fraud_type", "is_transfer", "is_cashout",
                    "dest_is_customer", "orig_to_customer",
                    "dest_had_zero", "dest_zeroed_after", "orig_zeroed", "off_hours"]:
            vals = set(X[col].unique())
            assert vals.issubset({0, 1}), f"{col} contém valores fora de {{0,1}}: {vals}"

    def test_fraud_type_consistent_with_type_enc(self, raw_df, features):
        """is_fraud_type=1 deve corresponder apenas a TRANSFER e CASH_OUT."""
        X, _ = features
        fraud_mask = X["is_fraud_type"] == 1
        types_flagged = raw_df.loc[X.index[fraud_mask], "type"]
        assert types_flagged.isin({"TRANSFER", "CASH_OUT"}).all()


class TestPipelineContract:
    """Invariantes de ponta a ponta."""

    def test_iso_scores_finite(self, trained_iso, scaled):
        X_scaled, _ = scaled
        scores = iso_scores(trained_iso, X_scaled)
        assert np.isfinite(scores).all()

    def test_ae_scores_non_negative(self, trained_autoencoder, scaled):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        scores = reconstruction_errors(ae, X_scaled)
        assert (scores >= 0).all()

    def test_predictions_are_binary(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)
        unique_vals = set(preds)
        assert unique_vals.issubset({0, 1}), f"Predições não-binárias: {unique_vals}"

    def test_predictions_same_length_as_input(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)
        assert len(preds) == len(X_scaled)

    def test_threshold_above_zero(self, trained_autoencoder, scaled, features):
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        assert thr > 0

    def test_some_frauds_detected(self, trained_autoencoder, scaled, features):
        """Com dados que têm fraudes reais, pelo menos alguma deve ser detectada."""
        ae, _ = trained_autoencoder
        X_scaled, _ = scaled
        _, y = features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)
        tp = ((preds == 1) & (y == 1)).sum()
        assert tp > 0, "Nenhuma fraude detectada — modelo pode estar degenerado"
