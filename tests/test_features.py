import numpy as np
import pandas as pd
import pytest

from aml_detector.config import FEATURE_COLS
from aml_detector.features.engineering import build_features, scale_features


class TestBuildFeatures:
    def test_output_columns_match_config(self, raw_df):
        X, _ = build_features(raw_df)
        assert list(X.columns) == FEATURE_COLS

    def test_column_count(self, raw_df):
        X, _ = build_features(raw_df)
        assert X.shape[1] == len(FEATURE_COLS)

    def test_row_count_preserved(self, raw_df):
        X, y = build_features(raw_df)
        assert len(X) == len(raw_df)
        assert len(y) == len(raw_df)

    def test_no_nulls(self, features):
        X, _ = features
        assert X.isnull().sum().sum() == 0

    def test_no_infinities(self, features):
        X, _ = features
        assert np.isfinite(X.values).all()

    def test_full_drain_bounded(self, features):
        X, _ = features
        assert X["full_drain"].between(0, 1).all()

    def test_balance_retention_bounded(self, features):
        X, _ = features
        assert X["balance_retention_orig"].between(0, 1).all()

    def test_velocity_positive(self, features):
        X, _ = features
        assert (X["velocity_orig"] >= 1).all()
        assert (X["velocity_dest"] >= 1).all()

    def test_binary_flags(self, features):
        X, _ = features
        binary_cols = [
            "is_fraud_type", "is_transfer", "is_cashout",
            "dest_is_customer", "orig_to_customer",
            "dest_had_zero", "dest_zeroed_after",
            "orig_zeroed", "off_hours",
        ]
        for col in binary_cols:
            assert set(X[col].unique()).issubset({0, 1}), f"{col} não é binário"

    def test_fraud_type_only_transfer_cashout(self, raw_df, features):
        X, _ = features
        mask_fraud_type = X["is_fraud_type"] == 1
        types = raw_df.loc[X.index, "type"]
        assert types[mask_fraud_type].isin({"TRANSFER", "CASH_OUT"}).all()

    def test_label_values(self, features):
        _, y = features
        assert set(y.unique()).issubset({0, 1})

    def test_fraud_count_preserved(self, raw_df, features):
        _, y = features
        assert y.sum() == raw_df["isFraud"].sum()

    def test_hour_of_day_range(self, features):
        X, _ = features
        assert X["hour_of_day"].between(0, 23).all()

    def test_log_amount_non_negative(self, features):
        X, _ = features
        assert (X["log_amount"] >= 0).all()

    def test_missing_columns_raise(self):
        """Pipeline deve falhar claramente se faltar coluna obrigatória."""
        df_incomplete = pd.DataFrame({"step": [1], "amount": [100]})
        with pytest.raises(KeyError):
            build_features(df_incomplete)


class TestScaleFeatures:
    def test_output_shape(self, features):
        X, _ = features
        X_scaled, _ = scale_features(X)
        assert X_scaled.shape == X.shape

    def test_returns_ndarray(self, features):
        X, _ = features
        X_scaled, _ = scale_features(X)
        assert isinstance(X_scaled, np.ndarray)

    def test_no_nulls_after_scaling(self, scaled):
        X_scaled, _ = scaled
        assert np.isfinite(X_scaled).all()

    def test_approximately_zero_mean(self, scaled):
        X_scaled, _ = scaled
        col_means = X_scaled.mean(axis=0)
        assert np.abs(col_means).max() < 0.1

    def test_scaler_transforms_new_data(self, features):
        X, _ = features
        X_scaled, scaler = scale_features(X)
        X_new = scaler.transform(X)
        np.testing.assert_array_almost_equal(X_scaled, X_new)

    def test_with_test_split(self, features):
        X, _ = features
        half = len(X) // 2
        X_train, X_test = X.iloc[:half], X.iloc[half:]
        X_tr_scaled, X_te_scaled, scaler = scale_features(X_train, X_test)
        assert X_tr_scaled.shape == X_train.shape
        assert X_te_scaled.shape == X_test.shape
