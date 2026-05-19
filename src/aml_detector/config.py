from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
OUTPUTS_DIR = ROOT_DIR / "outputs"

DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

RANDOM_SEED = 42
CONTAMINATION = 0.002
SAMPLE_SIZE = 200_000

FEATURE_COLS = [
    "log_amount", "type_enc",
    "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
    "diff_orig", "diff_dest",
    "balance_error", "orig_zeroed", "full_drain",
    "step",
]

AUTOENCODER_LAYERS = [32, 16, 8]
AUTOENCODER_EPOCHS = 30
AUTOENCODER_BATCH = 512
AUTOENCODER_PATIENCE = 5

ISO_N_ESTIMATORS = 200
ISO_MAX_SAMPLES = "auto"

GRAPH_MAX_EDGES = 50_000
GRAPH_TOP_SUSPICIOUS = 500
