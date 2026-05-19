import numpy as np
import pandas as pd
import pytest

RANDOM_SEED = 42
N_NORMAL = 470
N_FRAUD = 30  # ~6% — mantém proporção realista


@pytest.fixture(scope="session")
def raw_df() -> pd.DataFrame:
    """DataFrame sintético com o schema exato do PaySim."""
    rng = np.random.default_rng(RANDOM_SEED)
    n = N_NORMAL + N_FRAUD

    types_normal = rng.choice(["PAYMENT", "CASH_IN", "DEBIT", "TRANSFER", "CASH_OUT"], N_NORMAL)
    types_fraud = rng.choice(["TRANSFER", "CASH_OUT"], N_FRAUD)
    types = np.concatenate([types_normal, types_fraud])

    orig_bal = rng.exponential(100_000, n)
    amounts = rng.exponential(50_000, n)
    # Fraudes: esvaziamento completo (padrão real do PaySim)
    new_bal_orig = np.concatenate([
        np.maximum(orig_bal[:N_NORMAL] - amounts[:N_NORMAL], 0),
        np.zeros(N_FRAUD),
    ])

    df = pd.DataFrame({
        "step": rng.integers(1, 720, n),
        "type": types,
        "amount": amounts,
        "nameOrig": ["C" + str(i) for i in rng.integers(10_000, 99_999, n)],
        "oldbalanceOrg": orig_bal,
        "newbalanceOrig": new_bal_orig,
        "nameDest": np.concatenate([
            ["M" + str(i) for i in rng.integers(10_000, 99_999, N_NORMAL)],
            ["C" + str(i) for i in rng.integers(10_000, 99_999, N_FRAUD)],
        ]),
        "oldbalanceDest": rng.exponential(50_000, n),
        "newbalanceDest": rng.exponential(60_000, n),
        "isFraud": np.array([0] * N_NORMAL + [1] * N_FRAUD),
        "isFlaggedFraud": 0,
    })
    return df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)


@pytest.fixture(scope="session")
def features(raw_df):
    """X, y após feature engineering."""
    from aml_detector.features.engineering import build_features
    return build_features(raw_df)


@pytest.fixture(scope="session")
def scaled(features):
    """X_scaled, scaler após StandardScaler."""
    from aml_detector.features.engineering import scale_features
    X, _ = features
    X_scaled, scaler = scale_features(X)
    return X_scaled, scaler


@pytest.fixture(scope="session")
def trained_autoencoder(scaled, features):
    """Autoencoder treinado com 3 épocas — rápido, só para testes estruturais."""
    import tensorflow as tf
    tf.random.set_seed(RANDOM_SEED)
    from aml_detector.models.autoencoder import train_autoencoder
    X_scaled, _ = scaled
    _, y = features
    ae, history = train_autoencoder(X_scaled, y, epochs=3, batch_size=128, patience=3)
    return ae, history


@pytest.fixture(scope="session")
def trained_iso(scaled):
    """Isolation Forest treinado para testes estruturais."""
    from aml_detector.models.isolation_forest import train_isolation_forest
    X_scaled, _ = scaled
    return train_isolation_forest(X_scaled, contamination=0.06)
