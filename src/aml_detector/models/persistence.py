import json
from pathlib import Path

import joblib
import numpy as np

from aml_detector.config import MODELS_DIR


def save_artifacts(scaler, ae, threshold: float, metrics: dict) -> Path:
    """Salva scaler, autoencoder, threshold e métricas em MODELS_DIR."""
    MODELS_DIR.mkdir(exist_ok=True)

    joblib.dump(scaler, MODELS_DIR / "scaler.joblib")
    ae.save(MODELS_DIR / "autoencoder.keras")

    meta = {
        "threshold": float(threshold),
        "metrics": {k: float(v) for k, v in metrics.items()},
        "model_version": "1.0",
    }
    (MODELS_DIR / "metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"Artefatos salvos em {MODELS_DIR}")
    return MODELS_DIR


def load_artifacts():
    """Carrega scaler, autoencoder e metadata. Lança FileNotFoundError se não existirem."""
    import keras

    scaler_path = MODELS_DIR / "scaler.joblib"
    ae_path = MODELS_DIR / "autoencoder.keras"
    meta_path = MODELS_DIR / "metadata.json"

    for p in (scaler_path, ae_path, meta_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Artefato não encontrado: {p}\n"
                "Execute scripts/train.py para treinar e salvar o modelo."
            )

    scaler = joblib.load(scaler_path)
    ae = keras.models.load_model(ae_path)
    metadata = json.loads(meta_path.read_text())

    return scaler, ae, metadata


def artifacts_exist() -> bool:
    return all(
        (MODELS_DIR / f).exists()
        for f in ("scaler.joblib", "autoencoder.keras", "metadata.json")
    )
