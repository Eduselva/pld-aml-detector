"""
Testes com dados reais do PaySim.

Execução:
    pytest tests/test_real_data.py --data /caminho/para/PS_log.csv

Todos os testes são marcados com @real_data e são pulados automaticamente
quando --data não é fornecido, sem quebrar o CI.

Thresholds de performance baseados nos resultados do notebook de referência:
    AE  AUC-ROC  >= 0.95   (notebook: ~0.97)
    IF  AUC-ROC  >= 0.70   (notebook: ~0.75)
    AE  F1 fraude >= 0.55  (notebook: ~0.62 com threshold ótimo)
    AE  razão erro fraude/normal >= 50x  (notebook: ~700x)
"""
import numpy as np
import pytest
from sklearn.metrics import classification_report, roc_auc_score

from aml_detector.config import FEATURE_COLS
from aml_detector.models.autoencoder import reconstruction_errors
from aml_detector.models.ensemble import ensemble_predict, find_optimal_threshold
from aml_detector.models.isolation_forest import iso_scores


# ---------------------------------------------------------------------------
# 1. Validação do dataset de entrada
# ---------------------------------------------------------------------------

@pytest.mark.real_data
class TestRealDataSchema:

    REQUIRED_COLS = {
        "step", "type", "amount",
        "nameOrig", "oldbalanceOrg", "newbalanceOrig",
        "nameDest", "oldbalanceDest", "newbalanceDest",
        "isFraud",
    }

    def test_required_columns(self, real_df):
        missing = self.REQUIRED_COLS - set(real_df.columns)
        assert not missing, f"Colunas faltando no CSV real: {missing}"

    def test_row_count_reasonable(self, real_df):
        assert len(real_df) >= 10_000, "Dataset muito pequeno para ser o PaySim completo"

    def test_fraud_rate_in_expected_range(self, real_df):
        rate = real_df["isFraud"].mean()
        # PaySim: 0.13% no full dataset; sample mantém todas as fraudes (~4%)
        assert 0.001 <= rate <= 0.15, f"Taxa de fraude fora do esperado: {rate:.4f}"

    def test_fraud_types_only_transfer_cashout(self, real_df):
        fraud_types = set(real_df[real_df["isFraud"] == 1]["type"].unique())
        assert fraud_types.issubset({"TRANSFER", "CASH_OUT"}), \
            f"Tipos inesperados com fraude: {fraud_types - {'TRANSFER', 'CASH_OUT'}}"

    def test_no_negative_amounts(self, real_df):
        assert (real_df["amount"] >= 0).all(), "Valores negativos encontrados em 'amount'"

    def test_no_negative_balances(self, real_df):
        for col in ["oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]:
            assert (real_df[col] >= 0).all(), f"Saldo negativo em '{col}'"

    def test_type_distribution_present(self, real_df):
        expected = {"CASH_OUT", "TRANSFER"}
        present = set(real_df["type"].unique())
        assert expected.issubset(present), \
            f"Tipos críticos ausentes: {expected - present}"


# ---------------------------------------------------------------------------
# 2. Auditoria do pipeline de features
# ---------------------------------------------------------------------------

@pytest.mark.real_data
class TestRealFeatureAudit:

    def test_feature_count(self, real_features):
        X, _ = real_features
        assert X.shape[1] == len(FEATURE_COLS), \
            f"Esperado {len(FEATURE_COLS)} features, gerado {X.shape[1]}"

    def test_no_nulls(self, real_features):
        X, _ = real_features
        null_counts = X.isnull().sum()
        assert null_counts.sum() == 0, \
            f"Nulos encontrados:\n{null_counts[null_counts > 0]}"

    def test_no_infinities(self, real_features):
        X, _ = real_features
        assert np.isfinite(X.values).all(), "Infinitos encontrados após feature engineering"

    def test_fraud_count_preserved(self, real_df, real_features):
        _, y = real_features
        assert y.sum() == real_df["isFraud"].sum(), \
            "Número de fraudes mudou após feature engineering"

    def test_scaled_no_nan(self, real_scaled):
        X_scaled, _ = real_scaled
        assert np.isfinite(X_scaled).all(), "NaN/Inf após StandardScaler"

    def test_velocity_features_populated(self, real_features):
        X, _ = real_features
        # Com dados reais, algumas contas devem ter mais de 1 transação
        assert X["velocity_orig"].max() > 1, \
            "velocity_orig nunca > 1 — feature pode estar com bug"

    def test_off_hours_transactions_exist(self, real_features):
        X, _ = real_features
        assert X["off_hours"].sum() > 0, \
            "Nenhuma transação fora do horário comercial — checar step"

    def test_feature_stats(self, real_features, capsys):
        """Imprime estatísticas das features para auditoria manual."""
        X, y = real_features
        with capsys.disabled():
            print(f"\n{'─'*60}")
            print(f"  AUDITORIA DE FEATURES — DADOS REAIS")
            print(f"{'─'*60}")
            print(f"  Shape              : {X.shape}")
            print(f"  Fraudes            : {y.sum():,} ({y.mean()*100:.3f}%)")
            print(f"  Tipos de transação : {{}}")
            print(f"\n  Estatísticas por feature (média | std | min | max):")
            for col in FEATURE_COLS:
                s = X[col]
                print(f"    {col:<28} {s.mean():>10.3f} | {s.std():>10.3f} "
                      f"| {s.min():>10.3f} | {s.max():>10.3f}")
            print(f"{'─'*60}\n")


# ---------------------------------------------------------------------------
# 3. Avaliação de desempenho dos modelos
# ---------------------------------------------------------------------------

@pytest.mark.real_data
class TestRealModelPerformance:

    # Thresholds mínimos baseados no notebook de referência
    AE_AUC_MIN = 0.95
    IF_AUC_MIN = 0.70
    AE_F1_MIN = 0.55
    AE_ERROR_RATIO_MIN = 50.0   # erro médio fraudes / erro médio normais

    def test_autoencoder_auc(self, real_trained_autoencoder, real_scaled, real_features):
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features
        scores = reconstruction_errors(ae, X_scaled)
        auc = roc_auc_score(y, scores)
        assert auc >= self.AE_AUC_MIN, \
            f"AE AUC-ROC {auc:.4f} abaixo do mínimo {self.AE_AUC_MIN}"

    def test_isolation_forest_auc(self, real_trained_iso, real_scaled, real_features):
        X_scaled, _ = real_scaled
        _, y = real_features
        scores = iso_scores(real_trained_iso, X_scaled)
        auc = roc_auc_score(y, scores)
        assert auc >= self.IF_AUC_MIN, \
            f"IF AUC-ROC {auc:.4f} abaixo do mínimo {self.IF_AUC_MIN}"

    def test_autoencoder_fraud_f1(self, real_trained_autoencoder, real_scaled, real_features):
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features
        scores = reconstruction_errors(ae, X_scaled)
        thr, f1 = find_optimal_threshold(scores, y)
        assert f1 >= self.AE_F1_MIN, \
            f"AE F1 fraude {f1:.4f} abaixo do mínimo {self.AE_F1_MIN} (threshold={thr:.4f})"

    def test_autoencoder_error_ratio(self, real_trained_autoencoder, real_scaled, real_features):
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features
        errors = reconstruction_errors(ae, X_scaled)
        ratio = errors[y == 1].mean() / (errors[y == 0].mean() + 1e-9)
        assert ratio >= self.AE_ERROR_RATIO_MIN, \
            f"Razão erro fraude/normal {ratio:.1f}x abaixo do mínimo {self.AE_ERROR_RATIO_MIN}x"

    def test_no_total_silence(self, real_trained_autoencoder, real_scaled, real_features):
        """Modelo não pode prever tudo como normal (recall = 0)."""
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)
        tp = ((preds == 1) & (y == 1)).sum()
        assert tp > 0, "Modelo prevê tudo como normal — recall zero"

    def test_no_total_alarm(self, real_trained_autoencoder, real_scaled, real_features):
        """Modelo não pode prever tudo como fraude (precision degradada)."""
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features
        scores = reconstruction_errors(ae, X_scaled)
        thr, _ = find_optimal_threshold(scores, y)
        preds = ensemble_predict(scores, thr, None)
        fraud_rate_pred = preds.mean()
        assert fraud_rate_pred < 0.5, \
            f"Modelo flagrando {fraud_rate_pred*100:.1f}% como fraude — possível colapso"

    def test_performance_report(self, real_trained_autoencoder, real_trained_iso,
                                real_scaled, real_features, capsys):
        """Imprime relatório completo de performance para análise."""
        ae, _ = real_trained_autoencoder
        X_scaled, _ = real_scaled
        _, y = real_features

        ae_scores = reconstruction_errors(ae, X_scaled)
        if_scores = iso_scores(real_trained_iso, X_scaled)
        thr, f1 = find_optimal_threshold(ae_scores, y)
        preds = ensemble_predict(ae_scores, thr, None)

        auc_ae = roc_auc_score(y, ae_scores)
        auc_if = roc_auc_score(y, if_scores)
        error_ratio = ae_scores[y == 1].mean() / (ae_scores[y == 0].mean() + 1e-9)

        with capsys.disabled():
            print(f"\n{'─'*60}")
            print(f"  RELATÓRIO DE PERFORMANCE — DADOS REAIS")
            print(f"{'─'*60}")
            print(f"  AUC-ROC  Autoencoder      : {auc_ae:.4f}  (mín={self.AE_AUC_MIN})")
            print(f"  AUC-ROC  Isolation Forest  : {auc_if:.4f}  (mín={self.IF_AUC_MIN})")
            print(f"  F1 fraude (threshold ótimo): {f1:.4f}  (mín={self.AE_F1_MIN})")
            print(f"  Razão erro fraude/normal   : {error_ratio:.1f}x  (mín={self.AE_ERROR_RATIO_MIN}x)")
            print(f"  Threshold ótimo (MSE)      : {thr:.6f}")
            print(f"\n  Classification Report (AE + threshold ótimo):")
            print(classification_report(y, preds, target_names=["Normal", "Fraude"]))
            print(f"{'─'*60}\n")
