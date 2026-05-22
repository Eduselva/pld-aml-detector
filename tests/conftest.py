import numpy as np
import pandas as pd
import pytest

RANDOM_SEED = 42
N_NORMAL = 470
N_FRAUD = 30  # ~6% — mantém proporção realista


# ---------------------------------------------------------------------------
# CLI flag --data
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--data",
        action="store",
        default=None,
        metavar="PATH",
        help="Caminho para o CSV do PaySim real. Ativa os testes marcados com @real_data.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_data: testes que requerem o dataset PaySim real (use --data para ativar)",
    )


def pytest_collection_modifyitems(config, items):
    """Pula testes @real_data quando --data não for fornecido."""
    if config.getoption("--data"):
        return
    skip = pytest.mark.skip(reason="Dataset real não fornecido. Use --data /path/to/csv")
    for item in items:
        if item.get_closest_marker("real_data"):
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Fixtures sintéticas (CI — sem dependência de dados reais)
# ---------------------------------------------------------------------------

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
    from aml_detector.features.engineering import build_features
    return build_features(raw_df)


@pytest.fixture(scope="session")
def scaled(features):
    from aml_detector.features.engineering import scale_features
    X, _ = features
    X_scaled, scaler = scale_features(X)
    return X_scaled, scaler


@pytest.fixture(scope="session")
def trained_autoencoder(scaled, features):
    import tensorflow as tf
    tf.random.set_seed(RANDOM_SEED)
    from aml_detector.models.autoencoder import train_autoencoder
    X_scaled, _ = scaled
    _, y = features
    ae, history = train_autoencoder(X_scaled, y, epochs=3, batch_size=128, patience=3)
    return ae, history


@pytest.fixture(scope="session")
def trained_iso(scaled):
    from aml_detector.models.isolation_forest import train_isolation_forest
    X_scaled, _ = scaled
    return train_isolation_forest(X_scaled, contamination=0.06)


# ---------------------------------------------------------------------------
# Fixtures de dados reais (só instanciadas quando --data é passado)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_csv_path(request):
    path = request.config.getoption("--data")
    if not path:
        pytest.skip("--data não fornecido")
    return path


@pytest.fixture(scope="session")
def real_df(real_csv_path):
    """Carrega e amostra o PaySim real mantendo todas as fraudes."""
    from aml_detector.data.loader import load_paysim
    return load_paysim(real_csv_path)


@pytest.fixture(scope="session")
def real_features(real_df):
    from aml_detector.features.engineering import build_features
    return build_features(real_df)


@pytest.fixture(scope="session")
def real_scaled(real_features):
    from aml_detector.features.engineering import scale_features
    X, _ = real_features
    X_scaled, scaler = scale_features(X)
    return X_scaled, scaler


@pytest.fixture(scope="session")
def real_trained_autoencoder(real_scaled, real_features):
    """AE treinado com dados reais — usado para testes de performance."""
    import tensorflow as tf
    tf.random.set_seed(RANDOM_SEED)
    from aml_detector.models.autoencoder import train_autoencoder
    X_scaled, _ = real_scaled
    _, y = real_features
    ae, history = train_autoencoder(X_scaled, y)
    return ae, history


@pytest.fixture(scope="session")
def real_trained_iso(real_scaled, real_features):
    from aml_detector.models.isolation_forest import train_isolation_forest
    X_scaled, _ = real_scaled
    _, y = real_features
    contamination = float(y.mean())
    return train_isolation_forest(X_scaled, contamination=contamination)
