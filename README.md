# PLD-AML Detector

Detecção de lavagem de dinheiro com modelos **não supervisionados** aplicados ao dataset sintético PaySim.

> **Objetivo:** Validar o uso de modelos não supervisionados em cenários onde não há labels históricos confiáveis — e documentar de forma transparente onde essa abordagem funciona bem e onde tem limitações.

---

## Sumário

- [Contexto e motivação](#contexto-e-motivação)
- [Arquitetura do pipeline](#arquitetura-do-pipeline)
- [Resultados obtidos](#resultados-obtidos)
- [Limitações conhecidas](#limitações-conhecidas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Como executar](#como-executar)
- [API REST](#api-rest)
- [Testes](#testes)
- [Dataset](#dataset)

---

## Contexto e motivação

Em operações de PLD (Prevenção à Lavagem de Dinheiro), é comum não ter acesso a labels históricos confiáveis — seja por ausência de registros de investigações anteriores, seja por restrições regulatórias. Nesse cenário, modelos supervisionados não são viáveis.

Este projeto explora até onde modelos **não supervisionados** conseguem chegar:

- **Isolation Forest** — detecta anomalias por isolamento de pontos no espaço de features
- **Autoencoder** — aprende a reconstruir transações normais; fraudes geram erro de reconstrução alto
- **Ensemble** — combina os dois modelos com thresholds adaptativos por tipo de transação
- **SHAP** — explica quais features influenciam cada decisão (requisito regulatório)
- **Análise de Grafo** — identifica padrões de rede como smurfing, layering e hubs suspeitos

---

## Arquitetura do pipeline

```
CSV PaySim
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Feature Engineering  (28 features)                 │
│  Base · Tipo · Conta · Balanço · Velocidade · Tempo │
└────────────────────┬────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐   ┌─────────────────────────────┐
│ Isolation Forest │   │ Autoencoder  (Weighted MSE) │
│  n_estimators=300│   │ 28→64→32→16→8→16→32→64→28  │
│  contamination=y │   │ BatchNorm · Dropout(0.15)   │
└────────┬─────────┘   └──────────────┬──────────────┘
         │                            │
         │             ┌──────────────▼──────────────┐
         │             │  Threshold Adaptativo        │
         │             │  TRANSFER: ~0.26             │
         │             │  CASH_OUT: ~0.31             │
         └─────────────┴──────────────┬──────────────┘
                                      │
                             ┌────────▼────────┐
                             │    Ensemble      │
                             │  AE + IF low-val │
                             └────────┬────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                   ▼
              SHAP Values      Graph Analysis       API REST
              (explicação)     (rede suspeita)    (FastAPI)
```

### Features engineered (28)

| Grupo | Features |
|---|---|
| Base | `log_amount`, `type_enc` |
| Balanços | `diff_orig`, `diff_dest`, `balance_error`, `orig_zeroed`, `full_drain` |
| Ratios | `balance_error_ratio`, `amount_ratio_dest`, `balance_retention_orig` |
| Conta | `dest_is_customer`, `orig_to_customer`, `dest_had_zero`, `dest_zeroed_after` |
| Tipo | `is_fraud_type`, `is_transfer`, `is_cashout` |
| Velocidade | `velocity_orig`, `velocity_dest`, `log_volume_orig` |
| Temporal | `hour_of_day`, `day_of_sim`, `off_hours`, `step` |
| Raw | `oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest` |

---

## Resultados obtidos

Avaliação no dataset PaySim (200k transações, 4.1% fraude).

### Métricas principais

| Métrica | Valor | Meta | Status |
|---|---|---|---|
| AUC-ROC Autoencoder | 0.9609 | ≥ 0.95 | ✓ |
| AUC-ROC Isolation Forest | 0.9091 | — | ✓ |
| F1 fraude | 0.578 | ≥ 0.55 | ✓ |
| Precision fraude | 0.481 | ≥ 0.50 | ✗ |
| Recall fraude | 0.725 | — | — |
| Razão erro fraude/normal | 67.6x | ≥ 50x | ✓ |

### Detecção por tipo de transação

| Tipo | Detectadas | Perdidas | Taxa | Threshold |
|---|---|---|---|---|
| TRANSFER | 3.620 | 477 | **88.4%** | ~0.257 |
| CASH_OUT | 2.335 | 1.781 | **56.7%** | ~0.306 |

### Threshold adaptativo

Ao usar thresholds separados por tipo de transação:

| Tipo | F1 | Precision | Recall |
|---|---|---|---|
| TRANSFER | 0.766 | 0.631 | **0.974** |
| CASH_OUT | 0.586 | 0.609 | 0.565 |
| **Global adaptativo** | **0.593** | — | — |

### Valor financeiro

| | Total | Valor médio |
|---|---|---|
| Fraudes detectadas (TP) | R$ 11,4 bilhões | R$ 1,9 milhão |
| Fraudes perdidas (FN) | R$ 625 milhões | R$ 277 mil |

### SHAP — features mais importantes

**Isolation Forest:** `off_hours` > `orig_zeroed` > `is_transfer` > `full_drain`

**Autoencoder:** `diff_orig` > `newbalanceDest` > `balance_error` > `oldbalanceDest`

---

## Limitações conhecidas

Esta seção documenta de forma transparente os pontos fracos identificados — parte essencial da validação da abordagem não supervisionada.

### 1. CASH_OUT de baixo valor — principal ponto cego

Fraudes CASH_OUT com valor abaixo de ~R$200k têm taxa de detecção de apenas **56.7%**. A análise de features mostra que essas transações têm `full_drain=0.9996` e `orig_zeroed=0.9935` — praticamente idênticos às fraudes detectadas — o que indica que o padrão é genuinamente difícil de separar sem labels.

### 2. Variabilidade entre treinos

Por ser não supervisionado, o autoencoder pode convergir para soluções diferentes a cada execução. Foi implementado multi-run (3 seeds) com seleção pelo menor val_loss, mas a variabilidade persiste:

| Execução | F1 | Razão erro | Precision |
|---|---|---|---|
| Run 1 | 0.643 | 34.4x | 0.569 |
| Run 2 | 0.582 | 18.9x | 0.640 |
| Run 3 | 0.578 | 67.6x | 0.481 |

### 3. Precision abaixo da meta

Com threshold otimizado para F1, a precision fica em torno de 0.48–0.57. Com threshold adaptativo por tipo, melhora para 0.609–0.631. Em produção, é necessário calibrar o trade-off entre recall (não deixar fraudes passarem) e precision (custo operacional de investigação).

### 4. Grafo limitado pela amostra

A análise de grafo usa uma amostra de 200k de 6,3M transações. Padrões de smurfing e layering que envolvem contas em diferentes partes do dataset podem não aparecer na amostra. Os 113 hubs de alta centralidade identificados são o resultado mais robusto.

### 5. Quando usar e quando não usar

| Cenário | Recomendação |
|---|---|
| Sem labels históricos | ✓ Use esta abordagem |
| Labels confiáveis disponíveis | Prefira modelo supervisionado (XGBoost, RF) |
| Fraudes novas / nunca vistas | ✓ Não supervisionado generaliza melhor |
| Alta precisão regulatória necessária | Combine com regras de negócio |

---

## Estrutura do projeto

```
pld-aml-detector/
├── src/aml_detector/
│   ├── config.py                  # Hiperparâmetros e constantes
│   ├── data/
│   │   └── loader.py              # Carga e limpeza do PaySim
│   ├── features/
│   │   └── engineering.py         # 28 features engineered
│   ├── models/
│   │   ├── autoencoder.py         # Autoencoder + weighted MSE + multi-run
│   │   ├── isolation_forest.py    # Isolation Forest
│   │   ├── ensemble.py            # Threshold adaptativo por tipo
│   │   └── persistence.py         # Salvar/carregar artefatos
│   ├── evaluation/
│   │   └── metrics.py             # ROC, PR, F1, análise de erros
│   ├── explainability/
│   │   └── shap_explain.py        # SHAP para IF e Autoencoder
│   ├── graph/
│   │   └── analysis.py            # NetworkX + métricas + PyVis
│   └── api/
│       ├── app.py                 # FastAPI + lifespan
│       ├── routes.py              # /predict, /batch, /health
│       ├── schemas.py             # Pydantic schemas
│       └── model_store.py         # Singleton de modelos em memória
├── scripts/
│   └── train.py                   # Pipeline completo CLI
├── notebooks/
│   └── evaluation.ipynb           # Avaliação completa (roda no Kaggle)
├── tests/
│   ├── conftest.py                # Fixtures sintéticas + --data flag
│   ├── test_features.py           # 21 testes de feature engineering
│   ├── test_models.py             # 19 testes de modelos
│   ├── test_contracts.py          # 22 testes de contratos de dados
│   ├── test_pipeline.py           # 8 testes end-to-end
│   └── test_real_data.py          # 22 testes com dados reais (@real_data)
└── pyproject.toml
```

---

## Como executar

### No Kaggle (recomendado — sem instalação local)

1. Acesse [kaggle.com](https://www.kaggle.com) e crie um novo notebook
2. Adicione o dataset `ealaxi/paysim1` pelo painel direito
3. Menu **File → Import Notebook → GitHub** → cole a URL deste repositório
4. Selecione `notebooks/evaluation.ipynb` e execute

### Localmente

```bash
# 1. Clonar e instalar
git clone https://github.com/Eduselva/pld-aml-detector.git
cd pld-aml-detector
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"

# 2. Dataset (requer conta Kaggle)
pip install kaggle
kaggle datasets download -d ealaxi/paysim1 -p data/
unzip data/paysim1.zip -d data/

# 3. Treinar
python scripts/train.py --data data/PS_20174392719_1491204439457_log.csv

# 4. Subir API
uvicorn aml_detector.api.app:app --reload
```

---

## API REST

Após treinar, a API fica disponível em `http://localhost:8000`.

### Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/health` | Status do serviço |
| GET | `/model/info` | Versão, threshold, métricas |
| POST | `/predict` | Classificar uma transação |
| POST | `/predict/batch` | Classificar até 1.000 transações |

### Exemplo

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "step": 1,
    "type": "TRANSFER",
    "amount": 500000,
    "nameOrig": "C123456789",
    "oldbalanceOrg": 500000,
    "newbalanceOrig": 0,
    "nameDest": "C987654321",
    "oldbalanceDest": 0,
    "newbalanceDest": 500000
  }'
```

```json
{
  "is_fraud": true,
  "risk_score": 0.843,
  "threshold": 0.302,
  "confidence": 0.71
}
```

Documentação interativa: `http://localhost:8000/docs`

---

## Testes

```bash
# Testes com dados sintéticos (sem dependências externas)
pytest tests/ -v

# Testes com dados reais
pytest tests/ -v --data data/PS_20174392719_1491204439457_log.csv

# Com cobertura
pytest tests/ --cov=aml_detector --cov-report=term-missing
```

| Suite | Testes | Descrição |
|---|---|---|
| `test_features.py` | 21 | Feature engineering e scaling |
| `test_models.py` | 19 | Autoencoder, IF, ensemble |
| `test_contracts.py` | 22 | Contratos de dados e pipeline |
| `test_pipeline.py` | 8 | End-to-end sintético |
| `test_real_data.py` | 22 | Validação com dados reais (AUC≥0.95, F1≥0.55) |

---

## Dataset

**PaySim — Synthetic Financial Datasets For Fraud Detection**
- Fonte: [kaggle.com/datasets/ealaxi/paysim1](https://www.kaggle.com/datasets/ealaxi/paysim1)
- 6,3 milhões de transações sintéticas
- 8.213 fraudes (0.13%) — apenas em TRANSFER e CASH_OUT
- Simulação de transações móveis baseada em dados reais anonimizados

---

## Próximos passos

- [ ] Dashboard interativo (Streamlit) com visualização dos resultados e pontos fracos
- [ ] Segmentação de modelos por tipo de transação (AE_TRANSFER / AE_CASH_OUT)
- [ ] Projeto complementar com dados rotulados — abordagem semi-supervisionada
