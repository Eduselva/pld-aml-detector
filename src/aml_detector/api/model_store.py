"""
Mantém scaler, autoencoder e metadata carregados em memória.
Carregado uma única vez no startup da API.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelStore:
    scaler: Any = None
    autoencoder: Any = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.scaler is not None and self.autoencoder is not None

    @property
    def threshold(self) -> float:
        return self.metadata.get("threshold", 0.0)

    @property
    def version(self) -> str:
        return self.metadata.get("model_version", "unknown")

    @property
    def metrics(self) -> dict:
        return self.metadata.get("metrics", {})

    def load(self):
        from aml_detector.models.persistence import load_artifacts
        self.scaler, self.autoencoder, self.metadata = load_artifacts()
        print(f"Modelo carregado — versão {self.version} | threshold={self.threshold:.6f}")


# Singleton compartilhado pela aplicação
store = ModelStore()
