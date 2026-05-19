import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from aml_detector.config import (
    AUTOENCODER_BATCH,
    AUTOENCODER_DROPOUT,
    AUTOENCODER_ENCODER_LAYERS,
    AUTOENCODER_EPOCHS,
    AUTOENCODER_LATENT_DIM,
    AUTOENCODER_LR,
    AUTOENCODER_PATIENCE,
    FEATURE_COLS,
    FEATURE_WEIGHTS,
    RANDOM_SEED,
)


def _build_weight_vector() -> np.ndarray:
    """Vetor de pesos por feature na mesma ordem de FEATURE_COLS."""
    return np.array([FEATURE_WEIGHTS.get(f, 1.0) for f in FEATURE_COLS], dtype=np.float32)


def build_autoencoder(
    input_dim: int,
    encoder_layers: list[int] = AUTOENCODER_ENCODER_LAYERS,
    latent_dim: int = AUTOENCODER_LATENT_DIM,
    dropout_rate: float = AUTOENCODER_DROPOUT,
) -> keras.Model:
    tf.random.set_seed(RANDOM_SEED)

    inp = keras.Input(shape=(input_dim,))

    # Encoder: BN → [Dense → BN → Dropout] x N → latente
    x = layers.BatchNormalization()(inp)
    for units in encoder_layers:
        x = layers.Dense(units, activation="relu")(x)
        x = layers.BatchNormalization()(x)
        x = layers.Dropout(dropout_rate)(x)

    latent = layers.Dense(latent_dim, activation="relu", name="latent")(x)

    # Decoder: espelhado sem Dropout (reconstrução deve ser determinística)
    x = latent
    for units in reversed(encoder_layers):
        x = layers.Dense(units, activation="relu")(x)
        x = layers.BatchNormalization()(x)

    decoded = layers.Dense(input_dim, activation="linear", name="reconstruction")(x)

    model = keras.Model(inputs=inp, outputs=decoded, name="autoencoder")
    return model


def weighted_mse(feature_weights: np.ndarray):
    """MSE com peso por feature — penaliza mais o erro nas features AML críticas."""
    w = tf.constant(feature_weights, dtype=tf.float32)

    def loss(y_true, y_pred):
        sq_err = tf.square(y_true - y_pred)
        return tf.reduce_mean(sq_err * w, axis=1)

    loss.__name__ = "weighted_mse"
    return loss


def train_autoencoder(
    X_scaled: np.ndarray,
    y,
    epochs: int = AUTOENCODER_EPOCHS,
    batch_size: int = AUTOENCODER_BATCH,
    patience: int = AUTOENCODER_PATIENCE,
    learning_rate: float = AUTOENCODER_LR,
) -> tuple[keras.Model, object]:
    X_normal = X_scaled[y == 0]
    print(f"Treinando Autoencoder em {len(X_normal):,} transações normais...")
    print(f"  Arquitetura : {AUTOENCODER_ENCODER_LAYERS} → latent({AUTOENCODER_LATENT_DIM})")
    print(f"  Dropout     : {AUTOENCODER_DROPOUT}  |  LR: {learning_rate}")

    input_dim = X_scaled.shape[1]
    ae = build_autoencoder(input_dim)

    w_vec = _build_weight_vector()
    # Garante que o vetor tem o tamanho correto (pode diferir se input_dim != len(FEATURE_COLS))
    if len(w_vec) != input_dim:
        w_vec = np.ones(input_dim, dtype=np.float32)

    ae.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss=weighted_mse(w_vec),
    )
    ae.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=3,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    history = ae.fit(
        X_normal, X_normal,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        verbose=1,
        callbacks=callbacks,
    )

    errors = reconstruction_errors(ae, X_scaled)
    ratio = errors[y == 1].mean() / (errors[y == 0].mean() + 1e-9)
    print(f"\nErro médio — normais : {errors[y == 0].mean():.4f}")
    print(f"Erro médio — fraudes : {errors[y == 1].mean():.4f}")
    print(f"Razão fraude/normal  : {ratio:.1f}x")
    return ae, history


def reconstruction_errors(ae: keras.Model, X_scaled: np.ndarray, batch_size: int = 1024) -> np.ndarray:
    """MSE por amostra (sem pesos) — usado para scoring e threshold."""
    X_recon = ae.predict(X_scaled, batch_size=batch_size, verbose=0)
    return np.mean((X_scaled - X_recon) ** 2, axis=1)


def per_feature_errors(ae: keras.Model, X_scaled: np.ndarray, batch_size: int = 1024) -> np.ndarray:
    """Erro por feature — útil para diagnóstico e SHAP."""
    X_recon = ae.predict(X_scaled, batch_size=batch_size, verbose=0)
    return (X_scaled - X_recon) ** 2
