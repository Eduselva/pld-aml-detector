import pandas as pd
from aml_detector.config import RANDOM_SEED, SAMPLE_SIZE


def load_paysim(path: str, sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    df_full = pd.read_csv(path)
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
