import json
from pathlib import Path

import joblib
import numpy as np

import aml_detector.config as _config


def _models_dir() -> Path:
    return _config.MODELS_DIR


def save_artifacts(scaler, ae, threshold: float, metrics: dict) -> Path:
    """Salva scaler, autoencoder, threshold e métricas em MODELS_DIR."""
    d = _models_dir()
    d.mkdir(parents=True, exist_ok=True)

    joblib.dump(scaler, d / "scaler.joblib")
    ae.save(d / "autoencoder.keras")

    meta = {
        "threshold": float(threshold),
        "metrics": {k: float(v) for k, v in metrics.items()},
        "model_version": "1.0",
    }
    (d / "metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"Artefatos salvos em {d}")
    return d


def load_artifacts():
    """Carrega scaler, autoencoder e metadata. Lança FileNotFoundError se não existirem."""
    import keras

    d = _models_dir()
    scaler_path = d / "scaler.joblib"
    ae_path = d / "autoencoder.keras"
    meta_path = d / "metadata.json"

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
    d = _models_dir()
    return all(
        (d / f).exists()
        for f in ("scaler.joblib", "autoencoder.keras", "metadata.json")
    )
