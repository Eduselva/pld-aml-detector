import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="AML Detector",
    page_icon="🔍",
)

DATA_DIR = Path(__file__).parent / "data"

COLOR_FRAUD  = "#EF553B"
COLOR_NORMAL = "#636EFA"
COLOR_OK     = "#00CC96"
COLOR_WARN   = "#FFA15A"

# ── Carregamento ──────────────────────────────────────────────────────────────

@st.cache_data
def load_json(name):
    return json.loads((DATA_DIR / name).read_text())

@st.cache_data
def load_csv(name):
    return pd.read_csv(DATA_DIR / name)


def fmt_brl(v):
    if v >= 1e9:
        return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.1f}M"
    return f"R$ {v:,.0f}"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.shields.io/badge/AML-Detector-blue?style=for-the-badge")
    st.markdown("### Navegação")
    page = st.radio(
        "",
        ["Visão Geral", "Detecção por Tipo", "Análise de Erros",
         "Explicabilidade (SHAP)", "Análise de Grafo", "Sobre o Projeto"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Dataset: PaySim · 200k transações · 4.1% fraude")
    st.caption("[GitHub](https://github.com/Eduselva/pld-aml-detector)")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — VISÃO GERAL
# ═══════════════════════════════════════════════════════════════════════════════

if page == "Visão Geral":
    st.title("🔍 AML Detector — Detecção de Lavagem de Dinheiro")
    st.markdown(
        "Pipeline **não supervisionado** com Isolation Forest + Autoencoder aplicado ao PaySim. "
        "Desenvolvido para validar o uso de modelos sem labels históricos em cenários reais de PLD."
    )
    st.divider()

    m = load_json("metrics.json")

    # ── Métricas principais
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        ok = m["auc_autoencoder"] >= 0.95
        st.metric("AUC-ROC Autoencoder", f"{m['auc_autoencoder']:.4f}",
                  delta="✓ Meta ≥ 0.95" if ok else "✗ Meta ≥ 0.95",
                  delta_color="normal" if ok else "inverse")
    with c2:
        ok = m["f1"] >= 0.55
        st.metric("F1 Fraude", f"{m['f1']:.4f}",
                  delta="✓ Meta ≥ 0.55" if ok else "✗ Meta ≥ 0.55",
                  delta_color="normal" if ok else "inverse")
    with c3:
        ok = m["precision"] >= 0.50
        st.metric("Precision", f"{m['precision']:.4f}",
                  delta="✓ Meta ≥ 0.50" if ok else "✗ Meta ≥ 0.50",
                  delta_color="normal" if ok else "inverse")
    with c4:
        st.metric("Recall", f"{m['recall']:.4f}", delta=f"{m['recall']*100:.1f}% das fraudes")
    with c5:
        ok = m["error_ratio"] >= 50
        st.metric("Razão Erro Fraude/Normal", f"{m['error_ratio']:.1f}x",
                  delta="✓ Meta ≥ 50x" if ok else "✗ Meta ≥ 50x",
                  delta_color="normal" if ok else "inverse")

    st.divider()
    col_left, col_right = st.columns(2)

    # ── Curva ROC
    with col_left:
        st.subheader("Curva ROC")
        roc = load_json("roc_curve.json")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=roc["ae"]["fpr"], y=roc["ae"]["tpr"],
            name=f"Autoencoder (AUC={roc['ae']['auc']:.3f})",
            line=dict(color=COLOR_FRAUD, width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=roc["iso"]["fpr"], y=roc["iso"]["tpr"],
            name=f"Isolation Forest (AUC={roc['iso']['auc']:.3f})",
            line=dict(color=COLOR_NORMAL, width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines",
            line=dict(dash="dash", color="gray", width=1),
            showlegend=False,
        ))
        fig.update_layout(
            xaxis_title="Taxa de Falso Positivo", yaxis_title="Taxa de Verdadeiro Positivo",
            legend=dict(x=0.55, y=0.05), height=380, margin=dict(t=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Distribuição de scores AE
    with col_right:
        st.subheader("Distribuição de Scores — Autoencoder")
        scores_df = load_csv("scores.csv")
        cap = np.percentile(scores_df["score_ae"], 99)
        scores_clipped = scores_df.copy()
        scores_clipped["score_ae"] = scores_clipped["score_ae"].clip(upper=cap)

        fig2 = go.Figure()
        for label, color, name in [("normal", COLOR_NORMAL, "Normal"),
                                    ("fraud",  COLOR_FRAUD,  "Fraude")]:
            sub = scores_clipped[scores_clipped["label"] == label]["score_ae"]
            fig2.add_trace(go.Histogram(
                x=sub, name=name, marker_color=color,
                opacity=0.65, nbinsx=60, histnorm="probability density",
            ))
        fig2.add_vline(x=m["threshold"], line_dash="dash", line_color="black",
                       annotation_text=f"Threshold={m['threshold']:.3f}",
                       annotation_position="top right")
        fig2.update_layout(
            barmode="overlay", xaxis_title=f"MSE (cap p99={cap:.2f})",
            yaxis_title="Densidade", height=380, margin=dict(t=10),
            legend=dict(x=0.75, y=0.95),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Detecção resumida
    st.divider()
    st.subheader("Resumo de Detecção")
    c1, c2, c3 = st.columns(3)
    total = m["tp"] + m["fn"]
    with c1:
        fig = go.Figure(go.Pie(
            labels=["Detectadas (TP)", "Perdidas (FN)", "Falsos Alarmes (FP)"],
            values=[m["tp"], m["fn"], m["fp"]],
            marker_colors=[COLOR_OK, COLOR_FRAUD, COLOR_WARN],
            hole=0.5,
        ))
        fig.update_layout(title="Distribuição das predições", height=300, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.metric("Fraudes detectadas", f"{m['tp']:,}", delta=f"{m['tp_rate']*100:.1f}% do total")
        st.metric("Fraudes perdidas",   f"{m['fn']:,}", delta=f"-{m['fn_rate']*100:.1f}%", delta_color="inverse")
        st.metric("Falsos positivos",   f"{m['fp']:,}")
    with c3:
        var = load_json("value_at_risk.json")
        st.metric("Valor detectado (TP)", fmt_brl(var["tp_total"]))
        st.metric("Valor não detectado (FN)", fmt_brl(var["fn_total"]),
                  delta=f"Média por fraude: {fmt_brl(var['fn_mean'])}", delta_color="inverse")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — DETECÇÃO POR TIPO
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Detecção por Tipo":
    st.title("Detecção por Tipo de Transação")
    st.markdown("O modelo tem desempenhos muito diferentes para **TRANSFER** e **CASH_OUT** — o threshold adaptativo ajuda, mas o gap persiste.")
    st.divider()

    tb  = load_json("type_breakdown.json")
    ada = load_json("adaptive_thresholds.json")
    var = load_json("value_at_risk.json")
    m   = load_json("metrics.json")

    # ── Taxa de detecção por tipo
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Taxa de Detecção — Threshold Global")
        tipos = list(tb.keys())
        rates = [tb[t]["rate"] * 100 for t in tipos]
        colors = [COLOR_OK if r >= 80 else COLOR_WARN if r >= 60 else COLOR_FRAUD for r in rates]
        fig = go.Figure(go.Bar(
            x=tipos, y=rates, marker_color=colors,
            text=[f"{r:.1f}%" for r in rates], textposition="outside",
        ))
        fig.add_hline(y=80, line_dash="dot", line_color="gray",
                      annotation_text="Meta 80%", annotation_position="right")
        fig.update_layout(yaxis=dict(range=[0, 110], title="Taxa de detecção (%)"),
                          height=350, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Threshold Adaptativo — Ganho por Tipo")
        tipos_ada = list(ada.keys())
        f1_vals  = [ada[t]["f1"]  for t in tipos_ada]
        rec_vals = [ada[t]["recall"] for t in tipos_ada]
        prec_vals= [ada[t]["precision"] for t in tipos_ada]

        fig2 = go.Figure()
        for metric, vals, color in [
            ("F1",        f1_vals,   "#AB63FA"),
            ("Precision", prec_vals, COLOR_NORMAL),
            ("Recall",    rec_vals,  COLOR_OK),
        ]:
            fig2.add_trace(go.Bar(name=metric, x=tipos_ada, y=vals,
                                  text=[f"{v:.3f}" for v in vals], textposition="outside"))
        fig2.update_layout(barmode="group", yaxis=dict(range=[0, 1.15]),
                           height=350, margin=dict(t=20))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Tabela comparativa
    st.subheader("Comparativo: Global vs Adaptativo")
    rows = []
    for t in tipos_ada:
        rows.append({
            "Tipo": t,
            "Threshold Global": f"{m['threshold']:.4f}",
            "Threshold Adaptativo": f"{ada[t]['threshold']:.4f}",
            "F1 Adaptativo": f"{ada[t]['f1']:.3f}",
            "Precision": f"{ada[t]['precision']:.3f}",
            "Recall": f"{ada[t]['recall']:.3f}",
            "Detecção Global": f"{tb[t]['rate']*100:.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Valor financeiro
    st.divider()
    st.subheader("Impacto Financeiro")
    col1, col2 = st.columns(2)
    with col1:
        fig3 = go.Figure(go.Bar(
            x=["Detectado (TP)", "Não detectado (FN)"],
            y=[var["tp_total"] / 1e9, var["fn_total"] / 1e9],
            marker_color=[COLOR_OK, COLOR_FRAUD],
            text=[fmt_brl(var["tp_total"]), fmt_brl(var["fn_total"])],
            textposition="outside",
        ))
        fig3.update_layout(yaxis_title="Valor (R$ bilhões)", height=350, margin=dict(t=20))
        st.plotly_chart(fig3, use_container_width=True)
    with col2:
        st.metric("Total detectado",      fmt_brl(var["tp_total"]),
                  delta=f"Valor médio por fraude: {fmt_brl(var['tp_mean'])}")
        st.metric("Total não detectado",  fmt_brl(var["fn_total"]),
                  delta=f"Valor médio: {fmt_brl(var['fn_mean'])}", delta_color="inverse")
        pct_captured = var["tp_total"] / (var["tp_total"] + var["fn_total"]) * 100
        st.metric("% do valor total capturado", f"{pct_captured:.1f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — ANÁLISE DE ERROS
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Análise de Erros":
    st.title("Análise de Erros — Por que o modelo perde certas fraudes?")
    st.markdown(
        "Entender os **falsos negativos** (fraudes perdidas) é essencial para identificar "
        "os limites do modelo e orientar melhorias."
    )
    st.divider()

    ef = load_csv("error_features.csv")
    m  = load_json("metrics.json")
    tb = load_json("type_breakdown.json")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fraudes detectadas (TP)", f"{m['tp']:,}",
                  delta=f"{m['tp_rate']*100:.1f}% das fraudes")
    with col2:
        st.metric("Fraudes perdidas (FN)", f"{m['fn']:,}",
                  delta=f"-{m['fn_rate']*100:.1f}%", delta_color="inverse")
    with col3:
        st.metric("Falsos positivos (FP)", f"{m['fp']:,}",
                  delta="Alarmes sem fraude", delta_color="off")

    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Δ Features: Detectadas (TP) − Perdidas (FN)")
        st.caption("Valores positivos: detectadas têm valor maior nessa feature")
        delta_df = ef.sort_values("Δ (TP-FN)", ascending=True)
        colors = [COLOR_OK if v > 0 else COLOR_FRAUD for v in delta_df["Δ (TP-FN)"]]
        fig = go.Figure(go.Bar(
            x=delta_df["Δ (TP-FN)"],
            y=delta_df["feature"],
            orientation="h",
            marker_color=colors,
        ))
        fig.update_layout(height=400, margin=dict(t=10),
                          xaxis_title="Diferença média (TP − FN)")
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Detecção por Tipo")
        tipos = list(tb.keys())
        tp_vals = [tb[t]["tp"] for t in tipos]
        fn_vals = [tb[t]["fn"] for t in tipos]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="Detectadas (TP)", x=tipos, y=tp_vals,
                              marker_color=COLOR_OK))
        fig2.add_trace(go.Bar(name="Perdidas (FN)", x=tipos, y=fn_vals,
                              marker_color=COLOR_FRAUD))
        fig2.update_layout(barmode="stack", height=300, margin=dict(t=10))
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Principais achados")
        st.info(
            "**diff_orig** é a feature com maior diferença — fraudes detectadas movimentam "
            "valores muito maiores que as perdidas."
        )
        st.warning(
            "**CASH_OUT** tem apenas 56.7% de detecção. Fraudes de baixo valor nesse tipo "
            "têm padrão muito similar às transações normais."
        )
        st.error(
            "Fraudes perdidas têm valor médio de R$277k contra R$1,9M das detectadas — "
            "o modelo é mais sensível a volumes altos."
        )

    # ── Tabela de features
    st.divider()
    st.subheader("Features médias por grupo")
    st.dataframe(
        ef.set_index("feature").style.background_gradient(
            subset=["Δ (TP-FN)"], cmap="RdYlGn", vmin=-0.5, vmax=0.5
        ),
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 4 — SHAP
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Explicabilidade (SHAP)":
    st.title("Explicabilidade — SHAP")
    st.markdown(
        "SHAP (SHapley Additive exPlanations) mostra quais features mais influenciam "
        "a decisão de cada modelo. Fundamental para compliance e auditoria regulatória."
    )
    st.divider()

    shap_iso = load_json("shap_iso.json")
    shap_ae  = load_json("shap_ae.json")

    col1, col2 = st.columns(2)

    def shap_chart(data, title, color):
        df = pd.DataFrame({"feature": list(data.keys()), "importance": list(data.values())})
        df = df.sort_values("importance", ascending=True).tail(15)
        fig = go.Figure(go.Bar(
            x=df["importance"], y=df["feature"], orientation="h",
            marker_color=color,
        ))
        fig.update_layout(title=title, height=450, margin=dict(t=40),
                          xaxis_title="mean(|SHAP value|)")
        return fig

    with col1:
        st.plotly_chart(
            shap_chart(shap_iso, "Isolation Forest — Importância Global", COLOR_NORMAL),
            use_container_width=True,
        )
        st.info(
            "**off_hours** lidera — o IF usa fortemente o horário da transação. "
            "Fraudes ocorrem mais fora do horário comercial no PaySim."
        )

    with col2:
        st.plotly_chart(
            shap_chart(shap_ae, "Autoencoder — Importância para Erro de Reconstrução", COLOR_FRAUD),
            use_container_width=True,
        )
        st.info(
            "**diff_orig** domina — a variação no saldo de origem é o principal "
            "sinal para o autoencoder. Transações que zeram contas têm erro alto."
        )

    st.divider()
    st.subheader("O que cada modelo aprendeu")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Isolation Forest**")
        st.markdown("""
- Usa padrões **temporais** (`off_hours`, `step`, `day_of_sim`)
- Identifica contas completamente zeradas (`orig_zeroed`)
- Detecta transferências atípicas (`is_transfer`, `full_drain`)
- Sensível a altos saldos de origem (`oldbalanceOrg`)
        """)
    with c2:
        st.markdown("**Autoencoder**")
        st.markdown("""
- Foca na **movimentação financeira** (`diff_orig`, `balance_error`)
- Altamente sensível ao saldo de destino (`newbalanceDest`)
- Dificuldade com transações de baixo valor (pouco erro de reconstrução)
- Aprende melhor padrões de TRANSFER do que CASH_OUT
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 5 — ANÁLISE DE GRAFO
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Análise de Grafo":
    import streamlit.components.v1 as components

    st.title("Análise de Grafo — Rede de Transações Suspeitas")
    st.markdown(
        "O grafo mapeia contas como nós e transações como arestas. "
        "Padrões como **smurfing** (fan-out), **aggregation** (fan-in) e **layering** (ciclos) "
        "são identificados por métricas de centralidade."
    )
    st.divider()

    _graph_summary_path = DATA_DIR / "graph_summary.json"
    _graph_hubs_path    = DATA_DIR / "graph_top_hubs.csv"
    _graph_html_path    = DATA_DIR / "graph_interactive.html"

    if not _graph_summary_path.exists():
        st.warning(
            "Os dados de grafo ainda não foram exportados. "
            "Execute a célula de export no notebook Kaggle e faça upload dos arquivos "
            "`graph_summary.json`, `graph_top_hubs.csv` e `graph_interactive.html` "
            "para `dashboard/data/`."
        )
    else:
        gs = load_json("graph_summary.json")

        # ── Métricas resumo
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nós (contas)", f"{gs['n_nodes']:,}")
        c2.metric("Arestas (transações)", f"{gs['n_edges']:,}")
        c3.metric("Hubs alta centralidade", f"{gs['high_centrality_hubs']:,}")
        c4.metric("Contas alto risco", f"{gs['high_risk_score']:,}")

        st.divider()

        # ── Padrões detectados
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.subheader("Padrões de lavagem — resultados")
            data_patterns = {
                "Padrão": ["Smurfing (fan-out > 5)", "Aggregation (fan-in > 5)", "Layering (ciclos)", "Hubs suspeitos (PageRank top 1%)"],
                "Técnica": ["Fan-out score", "Fan-in score", "SCCs com > 1 nó", "PageRank"],
                "Contas":  [gs["smurfing_fanout"], gs["aggregation_fanin"], gs["layering_cycles"], gs["high_centrality_hubs"]],
            }
            st.dataframe(pd.DataFrame(data_patterns), use_container_width=True, hide_index=True)

            st.warning(
                "**PaySim gera transações 1-para-1** — cada conta envia para apenas uma outra "
                "por transação. Por isso smurfing e layering clássicos não aparecem na estrutura "
                "do grafo. Em dados reais, esses padrões seriam detectáveis."
            )
            st.info(
                f"**{gs['high_centrality_hubs']} hubs de alta centralidade** identificados — "
                "contas que intermediam muitas transações e têm PageRank no top 1%."
            )

        with col_right:
            st.subheader("Top 10 contas por Graph Risk Score")
            if _graph_hubs_path.exists():
                hubs_df = load_csv("graph_top_hubs.csv")
                display_cols = ["account", "out_degree", "in_degree",
                                "fan_out_score", "pagerank", "graph_risk_score", "is_fraud"]
                st.dataframe(
                    hubs_df[display_cols].head(10).style.background_gradient(
                        subset=["graph_risk_score"], cmap="Reds", vmin=0, vmax=1
                    ),
                    use_container_width=True,
                )

        # ── Rede interativa PyVis
        if _graph_html_path.exists():
            st.divider()
            st.subheader("Rede Interativa — Top 200 contas suspeitas")
            st.caption(
                "Vermelho = conta fraudulenta · Laranja = alto risco (score > 0.6) · "
                "Azul = normal. Tamanho proporcional ao graph risk score. "
                "Arraste, zoom e clique nos nós para detalhes."
            )
            html_content = _graph_html_path.read_text(encoding="utf-8")
            components.html(html_content, height=620, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 6 — SOBRE O PROJETO
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Sobre o Projeto":
    st.title("Sobre o Projeto")
    st.markdown(
        "Este projeto valida o uso de **modelos não supervisionados** para detecção de "
        "lavagem de dinheiro em cenários sem labels históricos — e documenta de forma "
        "transparente onde essa abordagem funciona e onde tem limitações."
    )
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Por que não supervisionado?")
        st.markdown("""
Em operações reais de PLD, é comum **não ter labels históricos confiáveis**:
- Ausência de registros de investigações anteriores
- Restrições regulatórias de compartilhamento de dados
- Fraudes novas que nunca foram catalogadas

Nesse cenário, modelos supervisionados **não são viáveis**. O pipeline usa:

| Modelo | Papel |
|---|---|
| **Isolation Forest** | Isola anomalias no espaço de features |
| **Autoencoder** | Aprende o "normal" — fraudes geram erro de reconstrução alto |
| **Ensemble** | Combina os dois com threshold adaptativo por tipo |
| **SHAP** | Explica cada decisão (requisito regulatório) |
| **Grafo** | Detecta padrões de rede (smurfing, hubs suspeitos) |
        """)

        st.subheader("Quando usar esta abordagem")
        data = {
            "Cenário": [
                "Sem labels históricos",
                "Labels confiáveis disponíveis",
                "Fraudes novas / nunca vistas",
                "Alta precisão regulatória",
                "Explicabilidade necessária",
            ],
            "Recomendação": ["✅ Use", "⚠️ Prefira supervisionado", "✅ Melhor opção", "⚠️ Combine com regras", "✅ SHAP disponível"],
        }
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Limitações conhecidas")

        st.error("""
**CASH_OUT de baixo valor — principal ponto cego**

Fraudes CASH_OUT com valor < R$200k têm apenas 56.7% de detecção.
As features `full_drain` e `orig_zeroed` são quase idênticas entre
fraudes detectadas e perdidas — padrão genuinamente difícil sem labels.
        """)

        st.warning("""
**Variabilidade entre treinos**

O autoencoder pode convergir para soluções diferentes a cada execução.
Mitigado com multi-run (3 seeds) selecionando o menor val_loss,
mas a variabilidade persiste (F1 varia de 0.58 a 0.64).
        """)

        st.warning("""
**Precision abaixo da meta**

Com threshold otimizado para F1, a precision fica em 0.48–0.57.
O threshold adaptativo por tipo melhora para 0.61–0.63.
Em produção, é necessário calibrar o trade-off recall × precision.
        """)

        st.info("""
**Grafo limitado pela amostra**

A análise usa 200k de 6.3M transações. Padrões de smurfing e layering
que cruzam diferentes partes do dataset podem não aparecer.
Os 113 hubs de alta centralidade são o resultado mais robusto.
        """)

    st.divider()
    st.subheader("Próximos passos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Segmentação de modelos**\nTreinar AE_TRANSFER e AE_CASH_OUT separados para melhorar detecção por tipo.")
    with c2:
        st.markdown("**Projeto supervisionado**\nCom labels históricos disponíveis, usar XGBoost/RF com as mesmas 28 features.")
    with c3:
        st.markdown("**Threshold adaptativo por valor**\nSegmentar também por faixa de valor para melhorar CASH_OUT de baixo valor.")

    st.divider()
    st.markdown(
        "**Repositório:** [github.com/Eduselva/pld-aml-detector](https://github.com/Eduselva/pld-aml-detector) · "
        "**Dataset:** [PaySim — Kaggle](https://www.kaggle.com/datasets/ealaxi/paysim1)"
    )
