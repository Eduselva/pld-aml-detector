import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from aml_detector.config import GRAPH_MAX_EDGES, GRAPH_TOP_SUSPICIOUS, OUTPUTS_DIR, RANDOM_SEED


def build_graph(df: pd.DataFrame, ae_scores: np.ndarray) -> nx.DiGraph:
    top_suspicious = set(df["nameOrig"].iloc[np.argsort(ae_scores)[-GRAPH_TOP_SUSPICIOUS:]])

    df_graph = df.sample(n=min(GRAPH_MAX_EDGES, len(df)), random_state=RANDOM_SEED)

    G = nx.DiGraph()
    for _, row in df_graph.iterrows():
        orig, dest = row["nameOrig"], row["nameDest"]
        for acc in [orig, dest]:
            if acc not in G:
                G.add_node(acc, is_fraud=0, total_sent=0.0, total_received=0.0,
                           is_suspicious=acc in top_suspicious)
        G.nodes[orig]["total_sent"] += row["amount"]
        G.nodes[dest]["total_received"] += row["amount"]
        if row["isFraud"]:
            G.nodes[orig]["is_fraud"] = 1
            G.nodes[dest]["is_fraud"] = 1
        if G.has_edge(orig, dest):
            G[orig][dest]["weight"] += row["amount"]
            G[orig][dest]["count"] += 1
        else:
            G.add_edge(orig, dest, weight=row["amount"], count=1, is_fraud=int(row["isFraud"]))

    print(f"Grafo: {G.number_of_nodes():,} nós | {G.number_of_edges():,} arestas")
    return G


def compute_graph_metrics(G: nx.DiGraph, sample_size: int = 5000) -> pd.DataFrame:
    print("Calculando métricas de grafo...")

    out_deg = dict(G.out_degree())
    in_deg = dict(G.in_degree())
    pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)

    rng = np.random.default_rng(RANDOM_SEED)
    sample_nodes = list(rng.choice(list(G.nodes()), size=min(sample_size, G.number_of_nodes()), replace=False))
    betweenness = nx.betweenness_centrality(G.subgraph(sample_nodes), normalized=True)

    cyclic_nodes = set()
    for scc in nx.strongly_connected_components(G):
        if len(scc) > 1:
            cyclic_nodes.update(scc)

    rows = []
    for node in G.nodes():
        od = out_deg.get(node, 0)
        id_ = in_deg.get(node, 0)
        sent = G.nodes[node].get("total_sent", 0)
        recv = G.nodes[node].get("total_received", 0)
        rows.append({
            "account": node,
            "out_degree": od,
            "in_degree": id_,
            "fan_out_score": od / max(id_, 1),
            "fan_in_score": id_ / max(od, 1),
            "pagerank": pagerank.get(node, 0),
            "betweenness": betweenness.get(node, 0),
            "sent_vs_received": abs(sent - recv) / max(sent + recv, 1),
            "cycle_flag": int(node in cyclic_nodes),
            "is_fraud": G.nodes[node].get("is_fraud", 0),
            "is_suspicious": int(G.nodes[node].get("is_suspicious", False)),
        })

    df_metrics = pd.DataFrame(rows)

    def _norm(s):
        r = s.max() - s.min()
        return (s - s.min()) / r if r > 0 else s * 0

    df_metrics["graph_risk_score"] = (
        0.25 * _norm(df_metrics["fan_out_score"])
        + 0.25 * _norm(df_metrics["pagerank"])
        + 0.20 * _norm(df_metrics["betweenness"])
        + 0.15 * _norm(df_metrics["sent_vs_received"])
        + 0.15 * df_metrics["cycle_flag"].astype(float)
    )
    df_metrics = df_metrics.sort_values("graph_risk_score", ascending=False)

    print("✓ Métricas calculadas")
    _print_summary(df_metrics)
    return df_metrics


def _print_summary(df_metrics: pd.DataFrame):
    n_fanout = (df_metrics["fan_out_score"] > 5).sum()
    n_fanin = (df_metrics["fan_in_score"] > 5).sum()
    n_cycles = df_metrics["cycle_flag"].sum()
    n_hubs = (df_metrics["pagerank"] > df_metrics["pagerank"].quantile(0.99)).sum()
    n_high_risk = (df_metrics["graph_risk_score"] > 0.7).sum()

    print("╔══════════════════════════════════════════════╗")
    print("║         PADRÕES DETECTADOS NO GRAFO          ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Fan-out suspeito  (smurfing)   : {n_fanout:>6,}    ║")
    print(f"║  Fan-in suspeito   (aggregation): {n_fanin:>6,}    ║")
    print(f"║  Contas em ciclos  (layering)   : {n_cycles:>6,}    ║")
    print(f"║  Hubs de alta centralidade      : {n_hubs:>6,}    ║")
    print(f"║  Graph risk score > 0.7         : {n_high_risk:>6,}    ║")
    print("╚══════════════════════════════════════════════╝")


def plot_ego_networks(G: nx.DiGraph, df_metrics: pd.DataFrame, n_accounts: int = 4, save: bool = True):
    top_accounts = df_metrics.head(n_accounts)["account"].tolist()
    fig, axes = plt.subplots(1, n_accounts, figsize=(5 * n_accounts, 5))

    for i, account in enumerate(top_accounts):
        ax = axes[i]
        if account not in G:
            ax.set_visible(False)
            continue

        ego = nx.ego_graph(G, account, radius=2, undirected=True)
        if ego.number_of_nodes() > 60:
            keep = [account] + list(G.successors(account)) + list(G.predecessors(account))
            ego = G.subgraph(keep[:60]).copy()

        pos = nx.spring_layout(ego, seed=42, k=0.8)
        colors = [
            "#E74C3C" if n == account
            else "#E67E22" if ego.nodes[n].get("is_fraud")
            else "#AED6F1"
            for n in ego.nodes()
        ]
        sizes = [400 if n == account else 100 + 20 * (ego.in_degree(n) + ego.out_degree(n)) for n in ego.nodes()]

        nx.draw_networkx(
            ego, pos=pos, ax=ax, node_color=colors, node_size=sizes,
            edge_color="#BDC3C7", arrows=True, arrowsize=8,
            with_labels=False, alpha=0.85, width=0.7
        )
        risk = df_metrics.loc[df_metrics["account"] == account, "graph_risk_score"].values
        ax.set_title(f"{account[:10]}…\nRisk={risk[0]:.3f}", fontsize=8)
        ax.axis("off")

    legend_el = [
        mpatches.Patch(color="#E74C3C", label="Conta central (suspeita)"),
        mpatches.Patch(color="#E67E22", label="Conta fraudulenta"),
        mpatches.Patch(color="#AED6F1", label="Normal"),
    ]
    fig.legend(handles=legend_el, loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle("Ego Networks — Top Contas por Graph Risk Score", fontsize=12)
    plt.tight_layout()

    if save:
        path = OUTPUTS_DIR / "ego_networks.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"Ego networks salvo em {path}")
    return fig


def export_pyvis(G: nx.DiGraph, df_metrics: pd.DataFrame, output_path: str = None):
    try:
        from pyvis.network import Network
    except ImportError:
        print("PyVis não instalado. Execute: pip install pyvis")
        return

    if output_path is None:
        output_path = str(OUTPUTS_DIR / "graph_interactive.html")

    top200 = set(df_metrics.head(200)["account"])
    subG = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        if u in top200 or v in top200:
            subG.add_edge(u, v, **data)

    risk_map = df_metrics.set_index("account")["graph_risk_score"].to_dict()
    fraud_map = df_metrics.set_index("account")["is_fraud"].to_dict()

    net = Network(height="600px", width="100%", directed=True, notebook=False)
    net.set_options('{"physics":{"stabilization":{"iterations":100}}}')

    for node in subG.nodes():
        risk = risk_map.get(node, 0)
        fraud = fraud_map.get(node, 0)
        color = "#E74C3C" if fraud else ("#E67E22" if risk > 0.6 else "#AED6F1")
        net.add_node(
            node, label=node[:8], color=color, size=8 + 25 * risk,
            title=f"{node}<br>Risk: {risk:.3f}<br>Fraud: {bool(fraud)}"
        )

    for u, v, data in subG.edges(data=True):
        net.add_edge(u, v, value=np.log1p(data.get("weight", 1)))

    net.save_graph(output_path)
    print(f"Grafo interativo salvo em {output_path}")
