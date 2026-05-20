import pandas as pd
from aml_detector.config import RANDOM_SEED, SAMPLE_SIZE


REQUIRED_COLS = {
    "step", "type", "amount",
    "nameOrig", "oldbalanceOrg", "newbalanceOrig",
    "nameDest", "oldbalanceDest", "newbalanceDest",
    "isFraud",
}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")
    df = df.dropna(subset=list(REQUIRED_COLS))
    numeric_cols = ["amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=numeric_cols)
    df["isFraud"] = df["isFraud"].astype(int)
    df["type"] = df["type"].str.strip().str.upper()
    return df.reset_index(drop=True)


def load_paysim(path: str, sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    df_full = _clean(pd.read_csv(path))
    print(f"Dataset completo : {len(df_full):,} transações")
    print(f"Fraudes          : {df_full['isFraud'].sum():,}  ({df_full['isFraud'].mean()*100:.3f}%)")

    fraud = df_full[df_full["isFraud"] == 1]
    non_fraud = df_full[df_full["isFraud"] == 0].sample(
        n=sample_size - len(fraud), random_state=RANDOM_SEED
    )
    df = (
        pd.concat([fraud, non_fraud])
        .sample(frac=1, random_state=RANDOM_SEED)
        .reset_index(drop=True)
    )
    print(f"Sample           : {len(df):,} transações | {df['isFraud'].sum():,} fraudes ({df['isFraud'].mean()*100:.3f}%)")
    return df
