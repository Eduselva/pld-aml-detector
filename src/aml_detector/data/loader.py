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
    df["isFraud"] = pd.to_numeric(df["isFraud"], errors="coerce").fillna(0).astype(int)
    df["type"] = df["type"].str.strip().str.upper()
    return df.reset_index(drop=True)


def load_paysim(path: str, sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    df_full = _clean(pd.read_csv(path))
    n_fraud = int(df_full["isFraud"].sum())
    n_total = len(df_full)
    print(f"Dataset completo : {n_total:,} transações")
    print(f"Fraudes          : {n_fraud:,}  ({n_fraud/n_total*100:.3f}%)")

    if n_fraud == 0:
        raise ValueError(
            "Nenhuma fraude encontrada no dataset após limpeza. "
            "Verifique se a coluna 'isFraud' está correta."
        )

    fraud = df_full[df_full["isFraud"] == 1]
    non_fraud_pool = df_full[df_full["isFraud"] == 0]
    n_sample = min(len(non_fraud_pool), max(1, sample_size - n_fraud))
    non_fraud = non_fraud_pool.sample(n=n_sample, random_state=RANDOM_SEED)

    df = (
        pd.concat([fraud, non_fraud])
        .sample(frac=1, random_state=RANDOM_SEED)
        .reset_index(drop=True)
    )
    print(f"Sample           : {len(df):,} transações | {df['isFraud'].sum():,} fraudes ({df['isFraud'].mean()*100:.3f}%)")
    return df
