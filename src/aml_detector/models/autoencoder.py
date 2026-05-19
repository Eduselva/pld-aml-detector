import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from aml_detector.config import (
    AUTOENCODER_BATCH,
    AUTOENCODER_EPOCHS,
    AUTOENCODER_LAYERS,
    AUTOENCODER_PATIENCE,
    RANDOM_SEED,
)


def build_autoencoder(input_dim: int, hidden_layers: list[int] = AUTOENCODER_LAYERS) -> keras.Model:
    tf.random.set_seed(RANDOM_SEED)

    inp = keras.Input(shape=(input_dim,))
    x = inp
    for units in hidden_layers:
        x = layers.Dense(units, activation="relu")(x)

    encoded = layers.Dense(hidden_layers[-1], activation="relu", name="latent")(x)

    x = encoded
    for units in reversed(hidden_layers[:-1]):
        x = layers.Dense(units, activation="relu")(x)
    x = layers.Dense(32, activation="relu")(x)
    decoded = layers.Dense(input_dim, activation="linear")(x)

    model = keras.Model(inputs=inp, outputs=decoded, name="autoencoder")
    model.compile(optimizer="adam", loss="mse")
    return model


def train_autoencoder(
    X_scaled: np.ndarray,
    y,
    epochs: int = AUTOENCODER_EPOCHS,
    batch_size: int = AUTOENCODER_BATCH,
    patience: int = AUTOENCODER_PATIENCE,
) -> tuple[keras.Model, object]:
    X_normal = X_scaled[y == 0]
    print(f"Treinando Autoencoder em {len(X_normal):,} transações normais...")

    ae = build_autoencoder(X_scaled.shape[1])
    ae.summary()

    history = ae.fit(
        X_normal, X_normal,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        verbose=1,
        callbacks=[keras.callbacks.EarlyStopping(patience=patience, restore_best_weights=True)],
    )

    recon_errors = reconstruction_errors(ae, X_scaled)
    print(f"\nErro médio — normais : {recon_errors[y == 0].mean():.4f}")
    print(f"Erro médio — fraudes : {recon_errors[y == 1].mean():.4f}")
    return ae, history


def reconstruction_errors(ae: keras.Model, X_scaled: np.ndarray, batch_size: int = 1024) -> np.ndarray:
    X_recon = ae.predict(X_scaled, batch_size=batch_size, verbose=0)
    return np.mean((X_scaled - X_recon) ** 2, axis=1)
