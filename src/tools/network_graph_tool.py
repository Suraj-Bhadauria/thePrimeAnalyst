"""
Network Graph Tool for PayInsight AI

This module provides comprehensive P2P transaction network graph analysis
using NetworkX.  It transforms the flat transaction dataset into a directed
weighted multi-graph where demographic-segment nodes are connected by P2P
transaction edges, enabling structural fraud detection that no row-level
tool can perform.

Supported analysis types:
    graph_overview, cycle_detection, degree_centrality, hub_identification,
    flow_analysis, community_detection, path_analysis, temporal_graph_analysis,
    pagerank_analysis, composite_fraud_graph.

Core dependency: NetworkX (MultiDiGraph, simple_cycles, pagerank, centrality).

Author: Team primeFactors
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import networkx as nx
import json
import math
import hashlib
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from src.utils.data_loader import data_loader

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class NetworkGraphInput(BaseModel):
    """Input schema for the network graph tool."""

    graph_analysis_type: str = Field(
        description=(
            "Type of graph analysis: graph_overview, cycle_detection, "
            "degree_centrality, hub_identification, flow_analysis, "
            "community_detection, path_analysis, temporal_graph_analysis, "
            "pagerank_analysis, composite_fraud_graph"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with graph parameters: status_filter (list), "
            "time_window_hours (int), min_cycle_length (int), max_cycle_length (int), "
            "top_n_hubs (int), min_transaction_count (int), filters (list), "
            "node_a (string), node_b (string), centrality_threshold (float), "
            "pagerank_damping (float), pagerank_iterations (int), "
            "community_resolution (float), include_amount_weights (bool), "
            "time_window_start_hour (int), time_window_end_hour (int)"
        ),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ANALYSIS_TYPES = {
    "graph_overview",
    "cycle_detection",
    "degree_centrality",
    "hub_identification",
    "flow_analysis",
    "community_detection",
    "path_analysis",
    "temporal_graph_analysis",
    "pagerank_analysis",
    "composite_fraud_graph",
}

TIME_BUCKETS: Dict[str, Tuple[int, int]] = {
    "Late Night": (0, 5),
    "Morning": (6, 11),
    "Afternoon": (12, 17),
    "Evening": (18, 21),
    "Night": (22, 23),
}

_NODE_INTERPRETATION = (
    "Each node represents a demographic segment (bank + age_group + state "
    "combination), not an individual user. Findings indicate segment-level "
    "patterns that warrant further investigation, not confirmed individual fraud."
)

MAX_GRAPH_CACHE = 5


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _safe(val: Any, decimals: int = 4) -> Any:
    """Round numeric values; pass-through None / non-numeric."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, decimals)
    if isinstance(val, (np.floating, np.integer)):
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, decimals)
    return val


def _fmt_inr(val: float | None) -> str:
    """Format an INR value for display."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:.2f}Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:.2f}L"
    return f"₹{val:,.2f}"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class NetworkGraphTool:
    """
    P2P transaction network graph analysis tool.

    Builds a directed weighted multi-graph from P2P transactions using
    NetworkX and exposes ten analysis modes — from basic topology to
    composite fraud intelligence.

    Node identifiers are constructed from ``sender_bank + age_group + state``
    combinations because the dataset lacks explicit user IDs.
    """

    def __init__(self) -> None:
        """Initialise with the global data_loader singleton."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)
        # LRU graph cache: key → (graph, p2p_df)
        self._graph_cache: OrderedDict[str, Tuple[nx.MultiDiGraph, pd.DataFrame]] = OrderedDict()

    # ==================================================================
    # Public entry point
    # ==================================================================

    def analyze(self, graph_analysis_type: str, parameters: str) -> str:
        """
        Main entry invoked by the LangChain tool wrapper.

        Args:
            graph_analysis_type: One of the ten supported analysis types.
            parameters: JSON string with analysis configuration.

        Returns:
            JSON string — either a success payload or an error payload.
        """
        if graph_analysis_type not in VALID_ANALYSIS_TYPES:
            return self._error(
                graph_analysis_type,
                f"Unknown graph_analysis_type '{graph_analysis_type}'. "
                f"Valid types: {sorted(VALID_ANALYSIS_TYPES)}",
                "Use one of the supported graph_analysis_type values.",
            )

        try:
            params: Dict[str, Any] = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error(
                graph_analysis_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string.",
            )

        dispatch = {
            "graph_overview": self._graph_overview,
            "cycle_detection": self._cycle_detection,
            "degree_centrality": self._degree_centrality,
            "hub_identification": self._hub_identification,
            "flow_analysis": self._flow_analysis,
            "community_detection": self._community_detection,
            "path_analysis": self._path_analysis,
            "temporal_graph_analysis": self._temporal_graph_analysis,
            "pagerank_analysis": self._pagerank_analysis,
            "composite_fraud_graph": self._composite_fraud_graph,
        }

        try:
            return dispatch[graph_analysis_type](params)
        except Exception as exc:
            return self._error(
                graph_analysis_type,
                f"Internal error during {graph_analysis_type}: {exc}",
                "Check parameters and retry.",
            )

    # ==================================================================
    # Graph construction helpers
    # ==================================================================

    def _cache_key(self, params: Dict[str, Any]) -> str:
        """Deterministic cache key from the filter configuration."""
        sig = {
            "status_filter": sorted(params.get("status_filter", ["SUCCESS"])),
            "filters": sorted(
                [json.dumps(f, sort_keys=True) for f in params.get("filters", [])]
            ),
            "min_transaction_count": params.get("min_transaction_count", 2),
            "time_window_start_hour": params.get("time_window_start_hour"),
            "time_window_end_hour": params.get("time_window_end_hour"),
        }
        raw = json.dumps(sig, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def _check_graph_cache(self, key: str) -> Optional[Tuple[nx.MultiDiGraph, pd.DataFrame]]:
        """Return cached graph if available, moving it to the end (LRU)."""
        if key in self._graph_cache:
            self._graph_cache.move_to_end(key)
            return self._graph_cache[key]
        return None

    def _update_graph_cache(self, key: str, graph: nx.MultiDiGraph, p2p_df: pd.DataFrame) -> None:
        """Store graph in cache; evict oldest if over capacity."""
        self._graph_cache[key] = (graph, p2p_df)
        self._graph_cache.move_to_end(key)
        while len(self._graph_cache) > MAX_GRAPH_CACHE:
            self._graph_cache.popitem(last=False)

    # ------------------------------------------------------------------

    def _filter_p2p_transactions(self, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Filter the master DataFrame to P2P SUCCESS transactions and apply
        any additional user-supplied filters.

        Returns:
            Filtered DataFrame containing only the rows to be used as graph edges.
        """
        df = self.df.copy()
        # P2P only
        df = df[df["transaction_type"] == "P2P"]

        # Status filter
        status_filter = params.get("status_filter", ["SUCCESS"])
        df = df[df["transaction_status"].isin(status_filter)]

        # Hour window
        start_h = params.get("time_window_start_hour")
        end_h = params.get("time_window_end_hour")
        if start_h is not None:
            df = df[df["hour_of_day"] >= int(start_h)]
        if end_h is not None:
            df = df[df["hour_of_day"] <= int(end_h)]

        # Generic filters
        for flt in params.get("filters", []):
            col = data_loader.resolve_column(flt.get("column", ""))
            op = flt.get("operator", "==")
            val = flt.get("value")
            if col not in df.columns or val is None:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > float(val)]
            elif op == ">=":
                df = df[df[col] >= float(val)]
            elif op == "<":
                df = df[df[col] < float(val)]
            elif op == "<=":
                df = df[df[col] <= float(val)]
            elif op == "in":
                df = df[df[col].isin(val if isinstance(val, list) else [val])]

        return df

    def _construct_node_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add ``sender_node`` and ``receiver_node`` columns constructed from
        bank + age_group + state.

        Returns:
            DataFrame with the two new columns.
        """
        df = df.copy()
        df["sender_node"] = (
            df["sender_bank"].astype(str) + "_"
            + df["sender_age_group"].astype(str) + "_"
            + df["sender_state"].astype(str)
        )
        df["receiver_node"] = (
            df["receiver_bank"].astype(str) + "_"
            + df["receiver_age_group"].astype(str) + "_"
            + df["sender_state"].astype(str)
        )
        return df

    def _build_graph(self, params: Dict[str, Any]) -> Tuple[nx.MultiDiGraph, pd.DataFrame, bool, str]:
        """
        Build (or retrieve from cache) the NetworkX MultiDiGraph.

        Returns:
            (graph, filtered_p2p_df, was_cached, execution_note)
        """
        key = self._cache_key(params)
        cached = self._check_graph_cache(key)
        if cached is not None:
            return cached[0], cached[1], True, ""

        p2p = self._filter_p2p_transactions(params)
        if p2p.empty:
            G = nx.MultiDiGraph()
            self._update_graph_cache(key, G, p2p)
            return G, p2p, False, "No P2P transactions matched the filters."

        p2p = self._construct_node_ids(p2p)

        # Min-transaction-count pruning
        min_txn = params.get("min_transaction_count", 2)
        if min_txn > 1:
            counts = pd.concat([p2p["sender_node"], p2p["receiver_node"]]).value_counts()
            valid_nodes = set(counts[counts >= min_txn].index)
            p2p = p2p[
                p2p["sender_node"].isin(valid_nodes) & p2p["receiver_node"].isin(valid_nodes)
            ]

        if p2p.empty:
            G = nx.MultiDiGraph()
            self._update_graph_cache(key, G, p2p)
            return G, p2p, False, "All nodes pruned by min_transaction_count filter."

        G = nx.MultiDiGraph()
        note_parts: list[str] = []

        # Add nodes with attributes
        self._add_node_attributes(G, p2p)
        # Add edges
        self._add_edge_attributes(G, p2p)

        if G.number_of_nodes() > 500:
            note_parts.append(
                f"Large graph ({G.number_of_nodes()} nodes). "
                "Cycle detection will be restricted to strongly connected components."
            )

        self._update_graph_cache(key, G, p2p)
        return G, p2p, False, " ".join(note_parts)

    def _add_node_attributes(self, G: nx.MultiDiGraph, df: pd.DataFrame) -> None:
        """Compute and attach per-node attributes from the edge DataFrame."""
        # Sender aggregates
        s_grp = df.groupby("sender_node").agg(
            total_sent=("amount_inr", "sum"),
            txn_count_out=("transaction_id", "count"),
            fraud_out=("fraud_flag", "sum"),
        )
        # Receiver aggregates
        r_grp = df.groupby("receiver_node").agg(
            total_received=("amount_inr", "sum"),
            txn_count_in=("transaction_id", "count"),
            fraud_in=("fraud_flag", "sum"),
        )
        all_nodes = set(df["sender_node"]).union(set(df["receiver_node"]))
        for nid in all_nodes:
            parts = nid.split("_", 2)
            bank = parts[0] if len(parts) > 0 else ""
            age = parts[1] if len(parts) > 1 else ""
            state = parts[2] if len(parts) > 2 else ""
            sent = float(s_grp.loc[nid, "total_sent"]) if nid in s_grp.index else 0.0
            recv = float(r_grp.loc[nid, "total_received"]) if nid in r_grp.index else 0.0
            out_c = int(s_grp.loc[nid, "txn_count_out"]) if nid in s_grp.index else 0
            in_c = int(r_grp.loc[nid, "txn_count_in"]) if nid in r_grp.index else 0
            f_out = int(s_grp.loc[nid, "fraud_out"]) if nid in s_grp.index else 0
            f_in = int(r_grp.loc[nid, "fraud_in"]) if nid in r_grp.index else 0
            G.add_node(
                nid,
                bank=bank,
                age_group=age,
                state=state,
                total_sent=sent,
                total_received=recv,
                transaction_count_out=out_c,
                transaction_count_in=in_c,
                is_net_sender=sent > recv,
                is_net_receiver=recv > sent,
                fraud_edge_count=f_out + f_in,
            )

    def _add_edge_attributes(self, G: nx.MultiDiGraph, df: pd.DataFrame) -> None:
        """Add every P2P transaction as a directed edge with attributes."""
        for row in df.itertuples(index=False):
            G.add_edge(
                row.sender_node,
                row.receiver_node,
                transaction_id=row.transaction_id,
                amount_inr=float(row.amount_inr),
                timestamp=str(row.timestamp),
                hour_of_day=int(row.hour_of_day),
                fraud_flag=bool(row.fraud_flag),
                transaction_status=row.transaction_status,
            )

    # ==================================================================
    # Graph statistics helpers
    # ==================================================================

    def _graph_stats(self, G: nx.MultiDiGraph, p2p_df: pd.DataFrame) -> Dict[str, Any]:
        """Return the standard graph_stats block."""
        n = G.number_of_nodes()
        e = G.number_of_edges()
        max_possible = n * (n - 1) if n > 1 else 1
        density = e / max_possible if max_possible else 0.0
        wcc = nx.number_weakly_connected_components(G) if n > 0 else 0
        scc = nx.number_strongly_connected_components(G) if n > 0 else 0
        total_val = float(p2p_df["amount_inr"].sum()) if not p2p_df.empty else 0.0
        return {
            "total_nodes": n,
            "total_edges": e,
            "total_p2p_transactions_analyzed": len(p2p_df),
            "total_value_in_graph_inr": _safe(total_val, 2),
            "graph_density": _safe(density, 6),
            "weakly_connected_components": wcc,
            "strongly_connected_components": scc,
        }

    def _default_risk_highlights(self) -> Dict[str, Any]:
        return {
            "total_flagged_nodes": 0,
            "total_flagged_as_hubs": 0,
            "total_cycles_detected": 0,
            "highest_risk_node": None,
            "highest_risk_node_score": None,
            "estimated_value_at_risk_inr": None,
        }

    def _build_node_record(
        self,
        G: nx.MultiDiGraph,
        nid: str,
        *,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Build the standard node record structure."""
        d = G.nodes.get(nid, {})
        in_c = d.get("transaction_count_in", 0)
        out_c = d.get("transaction_count_out", 0)
        total_recv = d.get("total_received", 0.0)
        total_sent = d.get("total_sent", 0.0)
        total_txn = in_c + out_c
        n = G.number_of_nodes()
        denom = (n - 1) if n > 1 else 1
        in_deg_raw = G.in_degree(nid) if G.has_node(nid) else 0
        out_deg_raw = G.out_degree(nid) if G.has_node(nid) else 0
        rec: Dict[str, Any] = {
            "node_id": nid,
            "bank": d.get("bank", ""),
            "age_group": d.get("age_group", ""),
            "state": d.get("state", ""),
            "total_transactions_in": in_c,
            "total_transactions_out": out_c,
            "total_transactions": total_txn,
            "total_amount_received_inr": _safe(total_recv, 2),
            "total_amount_sent_inr": _safe(total_sent, 2),
            "net_flow_inr": _safe(total_recv - total_sent, 2),
            "avg_incoming_amount_inr": _safe(total_recv / in_c, 2) if in_c else 0.0,
            "avg_outgoing_amount_inr": _safe(total_sent / out_c, 2) if out_c else 0.0,
            "in_degree_centrality": _safe(in_deg_raw / denom, 6),
            "out_degree_centrality": _safe(out_deg_raw / denom, 6),
            "pagerank_score": None,
            "community_id": None,
            "fraud_edge_count": d.get("fraud_edge_count", 0),
            "fraud_edge_rate_pct": _safe(
                d.get("fraud_edge_count", 0) / total_txn * 100, 2
            ) if total_txn else 0.0,
            "appears_in_cycle": False,
            "cycle_count": 0,
            "hub_classification": "Normal",
            "composite_risk_score": None,
        }
        if extra:
            rec.update(extra)
        return rec

    # ==================================================================
    # Executive narrative helpers
    # ==================================================================

    def _generate_executive_narrative(
        self,
        analysis_type: str,
        gs: Dict[str, Any],
        highlights: Dict[str, Any],
        detail: str = "",
    ) -> str:
        """Build a 4-sentence leadership narrative."""
        n = gs.get("total_nodes", 0)
        e = gs.get("total_edges", 0)
        val = gs.get("total_value_in_graph_inr", 0)
        s1 = (
            f"The P2P transaction network comprises {n:,} demographic segment nodes "
            f"connected by {e:,} transactions representing {_fmt_inr(val)} in total "
            f"transferred value."
        )
        s2 = detail if detail else "Analysis completed successfully."
        hr = highlights.get("highest_risk_node")
        hs = highlights.get("highest_risk_node_score")
        fc = highlights.get("total_cycles_detected", 0)
        fh = highlights.get("total_flagged_as_hubs", 0)
        s3 = (
            f"{fh} nodes flagged as potential hubs and {fc} cycles detected. "
            + (f"Highest risk node is {hr} (score {hs})." if hr else "No dominant risk node identified.")
        )
        var = highlights.get("estimated_value_at_risk_inr")
        s4 = (
            f"Estimated value flowing through flagged nodes/cycles: {_fmt_inr(var)}. "
            "Priority investigation should focus on flagged hubs and shortest cycles."
            if var
            else "No immediate high-value risk corridors detected in this analysis scope."
        )
        return f"{s1} {s2} {s3} {s4}"

    def _assess_network_health(self, score: float) -> str:
        if score > 80:
            return "Clean"
        if score > 60:
            return "Moderate Concern"
        if score > 40:
            return "High Concern"
        return "Critical"

    # ==================================================================
    # Error / success response builders
    # ==================================================================

    def _error(self, atype: str, msg: str, suggestion: str) -> str:
        return json.dumps({
            "success": False,
            "graph_analysis_type": atype,
            "error": msg,
            "suggestion": suggestion,
        })

    def _success(
        self,
        atype: str,
        gs: Dict[str, Any],
        results: Dict[str, Any],
        risk: Dict[str, Any],
        summary: Dict[str, Any],
        *,
        filters_applied: list | None = None,
        cached: bool = False,
        time_window: int | None = None,
        note: str = "",
    ) -> str:
        return json.dumps({
            "success": True,
            "graph_analysis_type": atype,
            "graph_scope": "P2P transactions only",
            "filters_applied": filters_applied or [],
            "graph_stats": gs,
            "analysis_results": results,
            "risk_highlights": risk,
            "summary": summary,
            "metadata": {
                "node_interpretation": _NODE_INTERPRETATION,
                "graph_type": "networkx.MultiDiGraph",
                "graph_cached": cached,
                "time_window_applied_hours": time_window,
                "execution_note": note,
            },
        })

    # ==================================================================
    # 1. graph_overview
    # ==================================================================

    def _graph_overview(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()
        e = G.number_of_edges()

        if n == 0:
            return self._success(
                "graph_overview", gs, {"message": "Empty graph — no P2P transactions matched."},
                self._default_risk_highlights(),
                {"key_finding": "No P2P transactions in scope.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched the current filters."},
                cached=cached, note=note,
            )

        density = gs["graph_density"]
        topo = "Sparse" if density < 0.01 else ("Moderate" if density <= 0.1 else "Dense")

        # Degree stats
        in_degs = dict(G.in_degree())
        out_degs = dict(G.out_degree())
        avg_in = sum(in_degs.values()) / n if n else 0
        avg_out = sum(out_degs.values()) / n if n else 0
        max_in_node = max(in_degs, key=in_degs.get) if in_degs else None
        max_out_node = max(out_degs, key=out_degs.get) if out_degs else None
        self_loops = nx.number_of_selfloops(G)

        results: Dict[str, Any] = {
            "topology_assessment": topo,
            "avg_in_degree": _safe(avg_in, 2),
            "avg_out_degree": _safe(avg_out, 2),
            "max_in_degree_node": max_in_node,
            "max_in_degree_value": in_degs.get(max_in_node, 0) if max_in_node else 0,
            "max_out_degree_node": max_out_node,
            "max_out_degree_value": out_degs.get(max_out_node, 0) if max_out_node else 0,
            "self_loop_count": self_loops,
        }

        risk = self._default_risk_highlights()
        risk["highest_risk_node"] = max_in_node
        risk["highest_risk_node_score"] = in_degs.get(max_in_node, 0) if max_in_node else None

        detail = (
            f"Graph density is {density:.6f} ({topo}). "
            f"Average in-degree {avg_in:.1f}, average out-degree {avg_out:.1f}. "
            f"Maximum incoming connections node: {max_in_node} with {in_degs.get(max_in_node, 0)} sources."
        )
        narrative = self._generate_executive_narrative("graph_overview", gs, risk, detail)

        summary = {
            "key_finding": f"{topo} P2P network with {n:,} nodes, {e:,} edges, density {density:.6f}.",
            "cycle_statement": "Cycle detection not run in overview mode.",
            "hub_statement": f"Node with most incoming connections: {max_in_node} ({in_degs.get(max_in_node, 0)} sources).",
            "network_health_assessment": topo,
            "executive_narrative": narrative,
        }
        return self._success("graph_overview", gs, results, risk, summary, cached=cached, note=note,
                             filters_applied=params.get("filters", []))

    # ==================================================================
    # 2. cycle_detection
    # ==================================================================

    def _cycle_detection(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "cycle_detection", gs, {"cycles": [], "cycle_summary": {}},
                self._default_risk_highlights(),
                {"key_finding": "No P2P transactions in scope.", "cycle_statement": "No cycles.",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched the current filters."},
                cached=cached, note=note,
            )

        time_window = params.get("time_window_hours", 24)
        min_len = params.get("min_cycle_length", 3)
        max_len = params.get("max_cycle_length", 5)
        top_n = params.get("top_n_hubs", 20)

        cycles_raw = self._detect_cycles_in_scc(G, max_len, note_parts := [])
        note = (note + " " + " ".join(note_parts)).strip()

        # Filter by length
        cycles_filtered = [c for c in cycles_raw if min_len <= len(c) <= max_len]

        # Enrich cycles
        enriched: list[Dict[str, Any]] = []
        for cyc_nodes in cycles_filtered:
            info = self._enrich_cycle(G, cyc_nodes, time_window)
            enriched.append(info)

        # Sort by risk score desc
        enriched.sort(key=lambda x: x.get("cycle_risk_score", 0), reverse=True)
        top_cycles = enriched[:top_n]

        # Summaries
        cycle_len_counts: Dict[int, int] = {}
        tw_count = 0
        for c in enriched:
            cl = c["cycle_length"]
            cycle_len_counts[cl] = cycle_len_counts.get(cl, 0) + 1
            if c.get("is_within_time_window"):
                tw_count += 1

        total_cycle_value = sum(c.get("total_amount_circulated", 0) for c in enriched)
        risk = self._default_risk_highlights()
        risk["total_cycles_detected"] = len(enriched)
        risk["estimated_value_at_risk_inr"] = _safe(total_cycle_value, 2)
        if top_cycles:
            # Collect nodes that appear in cycles
            cycle_nodes_set: set[str] = set()
            for c in enriched:
                cycle_nodes_set.update(c["cycle_nodes"])
            risk["total_flagged_nodes"] = len(cycle_nodes_set)
            risk["highest_risk_node"] = top_cycles[0]["cycle_nodes"][0]
            risk["highest_risk_node_score"] = top_cycles[0].get("cycle_risk_score", 0)

        detail = (
            f"Cycle detection identified {len(enriched)} circular money flows, "
            f"including {cycle_len_counts.get(3, 0)} triangular round-trips. "
            f"{tw_count} cycles complete within the {time_window}-hour time window "
            f"with combined value of {_fmt_inr(total_cycle_value)}."
        )

        summary = {
            "key_finding": f"{len(enriched)} cycles detected ({tw_count} within {time_window}h window), total value {_fmt_inr(total_cycle_value)}.",
            "cycle_statement": detail,
            "hub_statement": f"{risk['total_flagged_nodes']} nodes participate in at least one cycle.",
            "network_health_assessment": self._assess_network_health(
                100 - min(len(enriched) * 2, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("cycle_detection", gs, risk, detail),
        }

        results = {
            "cycles": top_cycles,
            "cycle_summary": {str(k): v for k, v in sorted(cycle_len_counts.items())},
            "time_window_cycles": tw_count,
            "total_cycles_found": len(enriched),
        }
        return self._success("cycle_detection", gs, results, risk, summary,
                             cached=cached, note=note, time_window=time_window,
                             filters_applied=params.get("filters", []))

    def _detect_cycles_in_scc(
        self, G: nx.MultiDiGraph, max_len: int, note_parts: list[str]
    ) -> list[list[str]]:
        """
        Find simple cycles, restricted to SCCs for performance.

        Uses ``networkx.simple_cycles`` on each strongly-connected component.
        If SCCs are large (>200 nodes), applies length limit and notes it.
        """
        simple_G = nx.DiGraph(G)  # collapse multi-edges for cycle enumeration
        sccs = list(nx.strongly_connected_components(simple_G))
        sccs = [s for s in sccs if len(s) >= 2]  # need ≥ 2 nodes for a cycle

        if not sccs:
            return []

        all_cycles: list[list[str]] = []
        large_scc_warning = False

        for scc_nodes in sccs:
            sub = simple_G.subgraph(scc_nodes).copy()
            if len(scc_nodes) > 200:
                large_scc_warning = True
                # Collect with length limit to avoid blowup
                count = 0
                for cyc in nx.simple_cycles(sub, length_bound=max_len):
                    all_cycles.append(list(cyc))
                    count += 1
                    if count >= 500:
                        break
            else:
                count = 0
                for cyc in nx.simple_cycles(sub, length_bound=max_len):
                    all_cycles.append(list(cyc))
                    count += 1
                    if count >= 1000:
                        break

        if large_scc_warning:
            note_parts.append(
                "One or more SCCs exceed 200 nodes — cycle search was length-bounded "
                f"to {max_len} and capped at 500 cycles per SCC."
            )
        return all_cycles

    def _enrich_cycle(
        self, G: nx.MultiDiGraph, cyc_nodes: list[str], time_window_hours: int
    ) -> Dict[str, Any]:
        """Compute detailed metrics for a single detected cycle."""
        cycle_len = len(cyc_nodes)
        edges_info: list[Dict[str, Any]] = []
        total_amount = 0.0
        fraud_count = 0
        timestamps: list[pd.Timestamp] = []
        tx_ids: list[str] = []

        for i in range(cycle_len):
            src = cyc_nodes[i]
            dst = cyc_nodes[(i + 1) % cycle_len]
            # Pick the first edge between src→dst
            edge_data = None
            if G.has_edge(src, dst):
                for _key, edata in G[src][dst].items():
                    edge_data = edata
                    break
            if edge_data:
                amt = edge_data.get("amount_inr", 0)
                total_amount += amt
                if edge_data.get("fraud_flag"):
                    fraud_count += 1
                ts_str = edge_data.get("timestamp", "")
                try:
                    ts = pd.Timestamp(ts_str)
                    timestamps.append(ts)
                except Exception:
                    pass
                tx_ids.append(edge_data.get("transaction_id", ""))

        time_span = 0.0
        within_window = False
        if len(timestamps) >= 2:
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 3600
            within_window = time_span <= time_window_hours

        # Risk score
        score = 50
        if within_window:
            score += 20
        if fraud_count > 0:
            score += 20
        if cycle_len == 3:
            score += 10
        score = min(score, 100)

        label = {3: "Triangular Round-Trip", 4: "Quadrilateral Loop"}.get(
            cycle_len, "Complex Loop"
        )

        return {
            "cycle_nodes": cyc_nodes,
            "cycle_length": cycle_len,
            "cycle_edges": tx_ids,
            "total_amount_circulated": _safe(total_amount, 2),
            "time_span_hours": _safe(time_span, 2),
            "is_within_time_window": within_window,
            "fraud_flagged_edges": fraud_count,
            "cycle_risk_score": score,
            "cycle_label": label,
        }

    # ==================================================================
    # 3. degree_centrality
    # ==================================================================

    def _degree_centrality(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "degree_centrality", gs, {"nodes": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        top_n = params.get("top_n_hubs", 20)
        threshold = params.get("centrality_threshold", 0.001)
        weighted = params.get("include_amount_weights", True)

        in_cent = nx.in_degree_centrality(G)
        out_cent = nx.out_degree_centrality(G)

        records: list[Dict[str, Any]] = []
        for nid in G.nodes():
            ic = in_cent.get(nid, 0)
            oc = out_cent.get(nid, 0)
            rec = self._build_node_record(G, nid, extra={
                "in_degree_centrality": _safe(ic, 6),
                "out_degree_centrality": _safe(oc, 6),
                "total_degree_centrality": _safe(ic + oc, 6),
                "in_degree_raw": G.in_degree(nid),
                "out_degree_raw": G.out_degree(nid),
                "is_hub": ic > threshold,
            })
            records.append(rec)

        records.sort(key=lambda r: r["in_degree_centrality"], reverse=True)
        top_records = records[:top_n]

        # Distribution stats
        all_ic = [in_cent[nid] for nid in G.nodes()]
        dist = {
            "mean": _safe(float(np.mean(all_ic)), 6),
            "median": _safe(float(np.median(all_ic)), 6),
            "std": _safe(float(np.std(all_ic)), 6),
            "p75": _safe(float(np.percentile(all_ic, 75)), 6),
            "p90": _safe(float(np.percentile(all_ic, 90)), 6),
            "p99": _safe(float(np.percentile(all_ic, 99)), 6),
        }

        hub_count = sum(1 for r in records if r.get("is_hub"))
        risk = self._default_risk_highlights()
        risk["total_flagged_as_hubs"] = hub_count
        risk["total_flagged_nodes"] = hub_count
        if top_records:
            risk["highest_risk_node"] = top_records[0]["node_id"]
            risk["highest_risk_node_score"] = top_records[0]["in_degree_centrality"]

        detail = (
            f"Degree centrality computed for {n} nodes. {hub_count} exceed the "
            f"{threshold} threshold. Top node: {top_records[0]['node_id'] if top_records else 'N/A'} "
            f"with in-degree centrality {top_records[0]['in_degree_centrality'] if top_records else 0}."
        )

        summary = {
            "key_finding": f"{hub_count} nodes exceed centrality threshold {threshold}.",
            "cycle_statement": "Cycles not analyzed in degree_centrality mode.",
            "hub_statement": f"Top hub: {top_records[0]['node_id'] if top_records else 'N/A'}.",
            "network_health_assessment": self._assess_network_health(
                100 - min(hub_count * 3, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("degree_centrality", gs, risk, detail),
        }

        results = {
            "nodes": top_records,
            "centrality_distribution": dist,
            "hub_threshold_used": threshold,
            "total_hubs_above_threshold": hub_count,
        }
        return self._success("degree_centrality", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    # ==================================================================
    # 4. hub_identification
    # ==================================================================

    def _hub_identification(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "hub_identification", gs, {"hub_candidates": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        top_n = params.get("top_n_hubs", 20)
        threshold = params.get("centrality_threshold", 0.001)

        in_cent = nx.in_degree_centrality(G)
        out_cent = nx.out_degree_centrality(G)

        candidates: list[Dict[str, Any]] = []
        for nid in G.nodes():
            ic = in_cent.get(nid, 0)
            oc = out_cent.get(nid, 0)
            d = G.nodes[nid]
            in_raw = G.in_degree(nid)
            out_raw = G.out_degree(nid)
            total_txn = in_raw + out_raw
            total_recv = d.get("total_received", 0)
            total_sent = d.get("total_sent", 0)
            fraud_ec = d.get("fraud_edge_count", 0)

            classification, hub_risk = self._classify_hub_type(
                ic, oc, in_raw, out_raw, total_recv, total_sent, fraud_ec, total_txn, threshold
            )
            if classification == "Normal":
                continue

            rec = self._build_node_record(G, nid, extra={
                "in_degree_centrality": _safe(ic, 6),
                "out_degree_centrality": _safe(oc, 6),
                "in_degree_raw": in_raw,
                "out_degree_raw": out_raw,
                "hub_classification": classification,
                "hub_risk_score": hub_risk,
                "in_out_ratio": _safe(in_raw / out_raw, 2) if out_raw else None,
                "net_receiver_ratio": _safe(total_recv / total_sent, 2) if total_sent else None,
            })
            candidates.append(rec)

        candidates.sort(key=lambda x: x.get("hub_risk_score", 0), reverse=True)
        top_candidates = candidates[:top_n]

        mule_count = sum(1 for c in candidates if c["hub_classification"] == "Potential Mule")
        mule_recv = sum(
            c.get("total_amount_received_inr", 0) or 0
            for c in candidates if c["hub_classification"] == "Potential Mule"
        )
        agg_count = sum(1 for c in candidates if c["hub_classification"] == "Aggregation Hub")

        risk = self._default_risk_highlights()
        risk["total_flagged_as_hubs"] = len(candidates)
        risk["total_flagged_nodes"] = len(candidates)
        risk["estimated_value_at_risk_inr"] = _safe(mule_recv, 2)
        if top_candidates:
            risk["highest_risk_node"] = top_candidates[0]["node_id"]
            risk["highest_risk_node_score"] = top_candidates[0].get("hub_risk_score", 0)

        detail = (
            f"Hub identification found {len(candidates)} hub candidates: "
            f"{mule_count} Potential Mules, {agg_count} Aggregation Hubs. "
            f"Potential mules received a combined {_fmt_inr(mule_recv)}."
        )

        summary = {
            "key_finding": f"{len(candidates)} hub candidates identified, {mule_count} classified as Potential Mule.",
            "cycle_statement": "Cycle analysis not run in hub_identification mode.",
            "hub_statement": detail,
            "network_health_assessment": self._assess_network_health(
                100 - min(mule_count * 5 + agg_count * 3, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("hub_identification", gs, risk, detail),
        }

        results = {
            "hub_candidates": top_candidates,
            "total_candidates": len(candidates),
            "mule_risk_summary": {
                "potential_mule_count": mule_count,
                "combined_received_inr": _safe(mule_recv, 2),
            },
            "aggregation_hub_count": agg_count,
        }
        return self._success("hub_identification", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    def _classify_hub_type(
        self,
        ic: float, oc: float,
        in_raw: int, out_raw: int,
        total_recv: float, total_sent: float,
        fraud_ec: int, total_txn: int,
        threshold: float,
    ) -> Tuple[str, float]:
        """
        Classify a node as Potential Mule, Aggregation Hub, High-Traffic Node,
        Fraud-Adjacent, or Normal. Returns (classification, risk_score 0–100).
        """
        in_out_ratio = (in_raw / out_raw) if out_raw > 0 else float("inf")
        fraud_rate = (fraud_ec / total_txn) if total_txn > 0 else 0.0
        net_recv_ratio = (total_recv / total_sent) if total_sent > 0 else float("inf")

        score = 0.0
        # In-degree centrality contribution
        score += min(ic / max(threshold, 1e-9) * 10, 30)
        # In/out ratio
        if in_out_ratio > 3:
            score += 20
        elif in_out_ratio > 1.5:
            score += 10
        # Net receiver
        if net_recv_ratio > 2:
            score += 20
        elif net_recv_ratio > 1.3:
            score += 10
        # Fraud edge rate
        if fraud_rate > 0.05:
            score += 20
        elif fraud_rate > 0.02:
            score += 10
        # Raw volume
        if in_raw > 50:
            score += 10
        score = min(score, 100)

        # Classification
        if fraud_rate > 0.05 and ic < threshold:
            return "Fraud-Adjacent", score
        if in_out_ratio > 3 and net_recv_ratio > 2 and ic >= threshold:
            return "Potential Mule", score
        if ic >= threshold and in_out_ratio > 1.5:
            return "Aggregation Hub", score
        if (in_raw + out_raw) > 30 and in_out_ratio <= 1.5:
            return "High-Traffic Node", score
        if ic >= threshold:
            return "High-Traffic Node", score
        if fraud_rate > 0.05:
            return "Fraud-Adjacent", score
        return "Normal", score

    def _compute_hub_risk_score(self, *args, **kwargs) -> float:
        """Wrapper — actual scoring is inside _classify_hub_type."""
        _, score = self._classify_hub_type(*args, **kwargs)
        return score

    # ==================================================================
    # 5. flow_analysis
    # ==================================================================

    def _flow_analysis(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)

        if p2p.empty:
            return self._success(
                "flow_analysis", gs, {"flows": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        top_n = params.get("top_n_hubs", 20)
        flow_df = p2p if "sender_node" in p2p.columns else self._construct_node_ids(p2p)

        pair_agg = flow_df.groupby(["sender_node", "receiver_node"]).agg(
            transaction_count=("transaction_id", "count"),
            total_amount_inr=("amount_inr", "sum"),
            avg_amount_inr=("amount_inr", "mean"),
            fraud_flag_count=("fraud_flag", "sum"),
            first_transaction_time=("timestamp", "min"),
            last_transaction_time=("timestamp", "max"),
        ).reset_index()

        pair_agg["first_transaction_time"] = pair_agg["first_transaction_time"].astype(str)
        pair_agg["last_transaction_time"] = pair_agg["last_transaction_time"].astype(str)

        # Time span
        try:
            pair_agg["time_span_days"] = (
                (pd.to_datetime(pair_agg["last_transaction_time"])
                 - pd.to_datetime(pair_agg["first_transaction_time"]))
                .dt.total_seconds() / 86400
            )
        except Exception:
            pair_agg["time_span_days"] = 0

        # Bidirectional check
        pair_set = set(zip(pair_agg["sender_node"], pair_agg["receiver_node"]))
        pair_agg["is_bidirectional"] = pair_agg.apply(
            lambda r: (r["receiver_node"], r["sender_node"]) in pair_set, axis=1
        )

        pair_agg.sort_values("total_amount_inr", ascending=False, inplace=True)
        top_flows = pair_agg.head(top_n).to_dict(orient="records")

        # Clean up numeric fields
        for f in top_flows:
            f["total_amount_inr"] = _safe(f["total_amount_inr"], 2)
            f["avg_amount_inr"] = _safe(f["avg_amount_inr"], 2)
            f["fraud_flag_count"] = int(f["fraud_flag_count"])
            f["transaction_count"] = int(f["transaction_count"])
            f["time_span_days"] = _safe(f["time_span_days"], 2)

        total_val = float(p2p["amount_inr"].sum())
        top10_val = float(pair_agg.head(10)["total_amount_inr"].sum()) if len(pair_agg) >= 10 else float(pair_agg["total_amount_inr"].sum())
        flow_concentration = _safe(top10_val / total_val * 100, 2) if total_val else 0

        bidir_pairs = pair_agg[pair_agg["is_bidirectional"]]
        bidir_count = len(bidir_pairs) // 2  # each pair counted twice
        bidir_val = _safe(float(bidir_pairs["total_amount_inr"].sum()) / 2, 2) if len(bidir_pairs) else 0

        dominant = top_flows[0] if top_flows else {}

        risk = self._default_risk_highlights()
        risk["estimated_value_at_risk_inr"] = _safe(bidir_val, 2)

        detail = (
            f"Top {min(top_n, len(top_flows))} flow pairs analyzed. "
            f"Flow concentration: top 10 pairs account for {flow_concentration}% of total P2P value. "
            f"{bidir_count} bidirectional pairs detected (combined value {_fmt_inr(bidir_val)})."
        )

        summary = {
            "key_finding": f"Top 10 node pairs concentrate {flow_concentration}% of P2P value.",
            "cycle_statement": f"{bidir_count} bidirectional pairs detected — softer round-trip indicator.",
            "hub_statement": f"Dominant flow corridor: {dominant.get('sender_node', '?')} → {dominant.get('receiver_node', '?')}.",
            "network_health_assessment": self._assess_network_health(
                100 - min(flow_concentration, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("flow_analysis", gs, risk, detail),
        }

        results = {
            "flows": top_flows,
            "flow_concentration_top10_pct": flow_concentration,
            "bidirectional_pairs": {"count": bidir_count, "total_value_inr": bidir_val},
            "dominant_flow_corridor": dominant,
        }
        return self._success("flow_analysis", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    # ==================================================================
    # 6. community_detection
    # ==================================================================

    def _community_detection(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "community_detection", gs, {"communities": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        resolution = params.get("community_resolution", 1.0)
        partition, modularity = self._run_community_detection(G, resolution)

        if partition is None:
            return self._success(
                "community_detection", gs,
                {"communities": [], "overall_modularity": None},
                self._default_risk_highlights(),
                {"key_finding": "Community detection could not run.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "Community detection algorithm could not partition the graph."},
                cached=cached, note=note + " Community detection failed or no valid partition.",
            )

        # Group nodes by community
        comm_nodes: Dict[int, list[str]] = {}
        for nid, cid in partition.items():
            comm_nodes.setdefault(cid, []).append(nid)

        communities: list[Dict[str, Any]] = []
        isolation_count = 0
        for cid, nodes_list in sorted(comm_nodes.items(), key=lambda x: -len(x[1])):
            internal_edges = 0
            external_edges = 0
            internal_flow = 0.0
            external_flow_in = 0.0
            external_flow_out = 0.0
            fraud_internal = 0
            node_set = set(nodes_list)

            for u, v, edata in G.edges(data=True):
                if u in node_set and v in node_set:
                    internal_edges += 1
                    internal_flow += edata.get("amount_inr", 0)
                    if edata.get("fraud_flag"):
                        fraud_internal += 1
                elif u in node_set:
                    external_edges += 1
                    external_flow_out += edata.get("amount_inr", 0)
                elif v in node_set:
                    external_edges += 1
                    external_flow_in += edata.get("amount_inr", 0)

            fraud_density = (fraud_internal / internal_edges) if internal_edges > 0 else 0
            net_ext = external_flow_in - external_flow_out

            # Dominant bank & state
            banks = [G.nodes[n].get("bank", "") for n in nodes_list if G.has_node(n)]
            states = [G.nodes[n].get("state", "") for n in nodes_list if G.has_node(n)]
            dom_bank = max(set(banks), key=banks.count) if banks else ""
            dom_state = max(set(states), key=states.count) if states else ""

            if fraud_density > 0.05 or (net_ext > 0 and net_ext > internal_flow * 0.5):
                risk_label = "High Risk"
            elif fraud_density > 0.02:
                risk_label = "Medium Risk"
            else:
                risk_label = "Low Risk"

            if external_edges == 0 and internal_edges > 0:
                isolation_count += 1

            communities.append({
                "community_id": cid,
                "node_count": len(nodes_list),
                "internal_edges": internal_edges,
                "external_edges": external_edges,
                "internal_flow_inr": _safe(internal_flow, 2),
                "external_flow_in_inr": _safe(external_flow_in, 2),
                "external_flow_out_inr": _safe(external_flow_out, 2),
                "net_external_flow_inr": _safe(net_ext, 2),
                "fraud_edge_density": _safe(fraud_density, 4),
                "dominant_bank": dom_bank,
                "dominant_state": dom_state,
                "community_risk_label": risk_label,
            })

        high_risk_count = sum(1 for c in communities if c["community_risk_label"] == "High Risk")
        risk = self._default_risk_highlights()
        risk["total_flagged_nodes"] = sum(c["node_count"] for c in communities if c["community_risk_label"] == "High Risk")

        detail = (
            f"Community detection found {len(communities)} communities (modularity {_safe(modularity, 4)}). "
            f"{high_risk_count} high-risk communities, {isolation_count} isolation communities "
            f"with no external connections."
        )

        summary = {
            "key_finding": f"{len(communities)} communities detected, modularity score {_safe(modularity, 4)}.",
            "cycle_statement": f"{isolation_count} self-contained communities with zero external edges detected.",
            "hub_statement": f"{high_risk_count} communities flagged as High Risk.",
            "network_health_assessment": self._assess_network_health(
                100 - min(high_risk_count * 10 + isolation_count * 15, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("community_detection", gs, risk, detail),
        }

        results = {
            "communities": communities,
            "overall_modularity": _safe(modularity, 4),
            "isolation_communities": isolation_count,
        }
        return self._success("community_detection", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    def _run_community_detection(
        self, G: nx.MultiDiGraph, resolution: float
    ) -> Tuple[Optional[Dict[str, int]], Optional[float]]:
        """
        Run community detection using Louvain (python-louvain) with fallback
        to NetworkX greedy_modularity_communities.

        Returns:
            (partition_dict, modularity_score) or (None, None) on failure.
        """
        if G.number_of_nodes() == 0:
            return None, None

        undirected = G.to_undirected()
        # Remove multi-edges for community detection
        simple_und = nx.Graph(undirected)

        try:
            import community as community_louvain
            partition = community_louvain.best_partition(simple_und, resolution=resolution)
            modularity = community_louvain.modularity(partition, simple_und)
            return partition, modularity
        except ImportError:
            pass

        try:
            from networkx.algorithms.community import greedy_modularity_communities, modularity as nx_mod
            comms = list(greedy_modularity_communities(simple_und))
            partition = {}
            for idx, comm_set in enumerate(comms):
                for node in comm_set:
                    partition[node] = idx
            mod_val = nx_mod(simple_und, comms)
            return partition, mod_val
        except Exception:
            return None, None

    # ==================================================================
    # 7. path_analysis
    # ==================================================================

    def _path_analysis(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)

        node_a = params.get("node_a")
        node_b = params.get("node_b")

        if not node_a or not node_b:
            return self._error(
                "path_analysis",
                "Both node_a and node_b must be specified.",
                "Provide node_a and node_b as demographic segment strings e.g. 'HDFC_26-35_Maharashtra'.",
            )

        if not G.has_node(node_a):
            return self._error("path_analysis", f"node_a '{node_a}' not found in the graph.",
                               f"Available nodes sample: {list(G.nodes())[:10]}")
        if not G.has_node(node_b):
            return self._error("path_analysis", f"node_b '{node_b}' not found in the graph.",
                               f"Available nodes sample: {list(G.nodes())[:10]}")

        simple_G = nx.DiGraph(G)

        # All simple paths up to length 5
        paths_raw: list[list[str]] = []
        try:
            for p in nx.all_simple_paths(simple_G, node_a, node_b, cutoff=5):
                paths_raw.append(p)
                if len(paths_raw) >= 50:
                    break
        except nx.NetworkXNoPath:
            pass

        # Shortest path
        shortest = None
        try:
            shortest = nx.shortest_path(simple_G, node_a, node_b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        direct_edge = G.has_edge(node_a, node_b)

        # Reverse path check
        reverse_exists = False
        try:
            nx.shortest_path(simple_G, node_b, node_a)
            reverse_exists = True
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        enriched_paths: list[Dict[str, Any]] = []
        for p in paths_raw:
            info = self._enrich_path(G, p)
            enriched_paths.append(info)

        enriched_paths.sort(key=lambda x: x.get("path_length", 999))

        fraud_on_any = any(ep.get("fraud_flagged_edges", 0) > 0 for ep in enriched_paths)
        short_path_exists = any(ep.get("path_length", 999) <= 2 for ep in enriched_paths)

        risk = self._default_risk_highlights()
        if fraud_on_any:
            risk["total_flagged_nodes"] = 2

        path_risk = "Low"
        if fraud_on_any and short_path_exists:
            path_risk = "High"
        elif fraud_on_any or short_path_exists:
            path_risk = "Medium"

        detail = (
            f"{len(enriched_paths)} paths found from {node_a} to {node_b}. "
            f"Direct edge: {'Yes' if direct_edge else 'No'}. "
            f"Shortest path length: {len(shortest) - 1 if shortest else 'N/A'} hops. "
            f"Reverse path exists: {'Yes' if reverse_exists else 'No'}."
        )

        summary = {
            "key_finding": f"{len(enriched_paths)} paths found between {node_a} and {node_b}.",
            "cycle_statement": f"Reverse path {'exists' if reverse_exists else 'does not exist'} — {'bidirectional connection' if reverse_exists else 'unidirectional flow'}.",
            "hub_statement": f"Direct edge: {'Yes' if direct_edge else 'No'}.",
            "network_health_assessment": path_risk,
            "executive_narrative": self._generate_executive_narrative("path_analysis", gs, risk, detail),
        }

        results = {
            "paths": enriched_paths,
            "shortest_path": shortest,
            "direct_edge_exists": direct_edge,
            "reverse_path_exists": reverse_exists,
            "path_risk_assessment": path_risk,
        }
        return self._success("path_analysis", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    def _enrich_path(self, G: nx.MultiDiGraph, path_nodes: list[str]) -> Dict[str, Any]:
        """Compute metrics for a single path."""
        tx_ids: list[str] = []
        amounts: list[float] = []
        timestamps: list[pd.Timestamp] = []
        fraud_count = 0

        for i in range(len(path_nodes) - 1):
            src = path_nodes[i]
            dst = path_nodes[i + 1]
            if G.has_edge(src, dst):
                for _k, ed in G[src][dst].items():
                    tx_ids.append(ed.get("transaction_id", ""))
                    amounts.append(ed.get("amount_inr", 0))
                    if ed.get("fraud_flag"):
                        fraud_count += 1
                    try:
                        timestamps.append(pd.Timestamp(ed.get("timestamp", "")))
                    except Exception:
                        pass
                    break  # first edge only

        bottleneck = min(amounts) if amounts else 0.0
        time_span = 0.0
        if len(timestamps) >= 2:
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 3600

        return {
            "path_nodes": path_nodes,
            "path_length": len(path_nodes) - 1,
            "path_edges": tx_ids,
            "total_amount_along_path": _safe(bottleneck, 2),
            "path_time_span_hours": _safe(time_span, 2),
            "fraud_flagged_edges": fraud_count,
        }

    # ==================================================================
    # 8. temporal_graph_analysis
    # ==================================================================

    def _temporal_graph_analysis(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)

        if p2p.empty:
            return self._success(
                "temporal_graph_analysis", gs, {"time_buckets": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        # Ensure node IDs
        work_df = p2p if "sender_node" in p2p.columns else self._construct_node_ids(p2p)

        bucket_results: list[Dict[str, Any]] = []
        peak_edges = 0
        peak_period = ""
        peak_fraud_count = 0
        peak_fraud_period = ""

        for bname, (h_start, h_end) in TIME_BUCKETS.items():
            sub = work_df[(work_df["hour_of_day"] >= h_start) & (work_df["hour_of_day"] <= h_end)]
            if sub.empty:
                bucket_results.append({
                    "time_bucket": bname,
                    "hour_range": f"{h_start}-{h_end}",
                    "node_count": 0, "edge_count": 0, "density": 0,
                    "top_3_hubs": [], "cycle_count": 0,
                    "fraud_edge_count": 0,
                    "temporal_risk_label": "Low",
                })
                continue

            # Build mini graph for this bucket
            sub_G = nx.MultiDiGraph()
            self._add_node_attributes(sub_G, sub)
            self._add_edge_attributes(sub_G, sub)

            bn = sub_G.number_of_nodes()
            be = sub_G.number_of_edges()
            max_e = bn * (bn - 1) if bn > 1 else 1
            bd = be / max_e if max_e else 0

            # Top 3 hubs by in-degree
            in_degs = dict(sub_G.in_degree())
            top3 = sorted(in_degs.items(), key=lambda x: -x[1])[:3]
            top3_hubs = [{"node_id": nid, "in_degree": deg} for nid, deg in top3]

            # Quick cycle count in SCCs
            simple_sub = nx.DiGraph(sub_G)
            cycle_count = 0
            for scc in nx.strongly_connected_components(simple_sub):
                if len(scc) < 2:
                    continue
                sg = simple_sub.subgraph(scc).copy()
                ct = 0
                for _ in nx.simple_cycles(sg, length_bound=5):
                    ct += 1
                    if ct >= 100:
                        break
                cycle_count += ct

            fraud_ec = int(sub["fraud_flag"].sum())

            if be > peak_edges:
                peak_edges = be
                peak_period = bname
            if fraud_ec > peak_fraud_count:
                peak_fraud_count = fraud_ec
                peak_fraud_period = bname

            risk_label = "Low"
            if fraud_ec / be > 0.05 if be else False or cycle_count > 5:
                risk_label = "High"
            elif cycle_count > 0 or (fraud_ec / be > 0.02 if be else False):
                risk_label = "Medium"

            bucket_results.append({
                "time_bucket": bname,
                "hour_range": f"{h_start}-{h_end}",
                "node_count": bn,
                "edge_count": be,
                "density": _safe(bd, 6),
                "top_3_hubs": top3_hubs,
                "cycle_count": cycle_count,
                "fraud_edge_count": fraud_ec,
                "temporal_risk_label": risk_label,
            })

        risk = self._default_risk_highlights()
        high_risk_buckets = [b for b in bucket_results if b["temporal_risk_label"] == "High"]
        risk["total_flagged_nodes"] = len(high_risk_buckets)

        detail = (
            f"Temporal analysis across {len(TIME_BUCKETS)} time buckets. "
            f"Peak activity: {peak_period} ({peak_edges} edges). "
            f"Peak fraud: {peak_fraud_period} ({peak_fraud_count} fraud-flagged edges)."
        )

        summary = {
            "key_finding": f"Peak P2P activity at {peak_period}, peak fraud at {peak_fraud_period}.",
            "cycle_statement": f"Cycles detected across multiple time buckets.",
            "hub_statement": f"Hub concentration varies by time of day.",
            "network_health_assessment": self._assess_network_health(
                100 - min(len(high_risk_buckets) * 15, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("temporal_graph_analysis", gs, risk, detail),
        }

        results = {
            "time_buckets": bucket_results,
            "peak_activity_period": peak_period,
            "peak_fraud_period": peak_fraud_period,
        }
        return self._success("temporal_graph_analysis", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    # ==================================================================
    # 9. pagerank_analysis
    # ==================================================================

    def _pagerank_analysis(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "pagerank_analysis", gs, {"nodes": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        damping = params.get("pagerank_damping", 0.85)
        max_iter = params.get("pagerank_iterations", 100)
        weighted = params.get("include_amount_weights", True)
        top_n = params.get("top_n_hubs", 20)

        weight_attr = "amount_inr" if weighted else None
        pr = nx.pagerank(G, alpha=damping, max_iter=max_iter, weight=weight_attr)

        in_cent = nx.in_degree_centrality(G)
        out_cent = nx.out_degree_centrality(G)

        records: list[Dict[str, Any]] = []
        for nid in G.nodes():
            rec = self._build_node_record(G, nid, extra={
                "pagerank_score": _safe(pr.get(nid, 0), 8),
                "in_degree_centrality": _safe(in_cent.get(nid, 0), 6),
                "out_degree_centrality": _safe(out_cent.get(nid, 0), 6),
                "in_degree_raw": G.in_degree(nid),
            })
            records.append(rec)

        records.sort(key=lambda r: r["pagerank_score"] or 0, reverse=True)
        for rank, r in enumerate(records, 1):
            r["pagerank_rank"] = rank
        top_records = records[:top_n]

        # Correlation
        pr_vals = np.array([pr.get(nid, 0) for nid in G.nodes()])
        ic_vals = np.array([in_cent.get(nid, 0) for nid in G.nodes()])
        if len(pr_vals) > 2 and np.std(pr_vals) > 0 and np.std(ic_vals) > 0:
            correlation = float(np.corrcoef(pr_vals, ic_vals)[0, 1])
        else:
            correlation = None

        # High PageRank but low degree
        median_degree = float(np.median([G.in_degree(nid) for nid in G.nodes()]))
        p90_pr = float(np.percentile(pr_vals, 90))
        hi_pr_lo_deg = [
            r for r in records
            if (r.get("pagerank_score") or 0) >= p90_pr
            and (r.get("in_degree_raw") or 0) <= median_degree
        ][:10]

        # Concentration
        top10_pr = sum(r.get("pagerank_score") or 0 for r in records[:10])
        total_pr = sum(pr.values())
        concentration = _safe(top10_pr / total_pr * 100, 2) if total_pr else 0

        risk = self._default_risk_highlights()
        if top_records:
            risk["highest_risk_node"] = top_records[0]["node_id"]
            risk["highest_risk_node_score"] = top_records[0]["pagerank_score"]

        detail = (
            f"PageRank computed for {n} nodes (damping={damping}). "
            f"Top node: {top_records[0]['node_id'] if top_records else 'N/A'} "
            f"(score {top_records[0]['pagerank_score'] if top_records else 0}). "
            f"Top 10 nodes hold {concentration}% of total PageRank. "
            f"PR-degree correlation: {_safe(correlation, 4)}."
        )

        summary = {
            "key_finding": f"Top 10 nodes hold {concentration}% of PageRank — {'high' if concentration > 30 else 'moderate'} concentration.",
            "cycle_statement": "Cycles not analyzed in pagerank mode.",
            "hub_statement": f"Top PageRank node: {top_records[0]['node_id'] if top_records else 'N/A'}.",
            "network_health_assessment": self._assess_network_health(
                100 - min(concentration, 60)
            ),
            "executive_narrative": self._generate_executive_narrative("pagerank_analysis", gs, risk, detail),
        }

        results = {
            "nodes": top_records,
            "pagerank_vs_degree_correlation": _safe(correlation, 4),
            "high_pagerank_low_degree": hi_pr_lo_deg[:5],
            "pagerank_concentration_top10_pct": concentration,
        }
        return self._success("pagerank_analysis", gs, results, risk, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    # ==================================================================
    # 10. composite_fraud_graph
    # ==================================================================

    def _composite_fraud_graph(self, params: Dict[str, Any]) -> str:
        G, p2p, cached, note = self._build_graph(params)
        gs = self._graph_stats(G, p2p)
        n = G.number_of_nodes()

        if n == 0:
            return self._success(
                "composite_fraud_graph", gs, {"risk_nodes": []},
                self._default_risk_highlights(),
                {"key_finding": "Empty graph.", "cycle_statement": "N/A",
                 "hub_statement": "N/A", "network_health_assessment": "N/A",
                 "executive_narrative": "No P2P transactions matched."},
                cached=cached, note=note,
            )

        # --- Sub-analyses (parse JSON results back to dicts) ---
        cycle_result = json.loads(self._cycle_detection(params))
        hub_result = json.loads(self._hub_identification(params))
        pr_result = json.loads(self._pagerank_analysis(params))
        comm_result = json.loads(self._community_detection(params))

        # Collect cycle nodes
        cycle_nodes_set: set[str] = set()
        cycle_data = cycle_result.get("analysis_results", {})
        for cyc in cycle_data.get("cycles", []):
            cycle_nodes_set.update(cyc.get("cycle_nodes", []))

        # Hub nodes
        hub_nodes: Dict[str, str] = {}
        for cand in hub_result.get("analysis_results", {}).get("hub_candidates", []):
            hub_nodes[cand["node_id"]] = cand.get("hub_classification", "Normal")

        # PageRank top 10%
        pr_nodes = pr_result.get("analysis_results", {}).get("nodes", [])
        pr_scores: Dict[str, float] = {r["node_id"]: r.get("pagerank_score", 0) or 0 for r in pr_nodes}
        all_pr = list(pr_scores.values())
        pr_p90 = float(np.percentile(all_pr, 90)) if all_pr else 0
        high_pr_nodes = {nid for nid, sc in pr_scores.items() if sc >= pr_p90}

        # Community risk
        high_risk_comm_nodes: set[str] = set()
        partition_map: Dict[str, int] = {}
        communities = comm_result.get("analysis_results", {}).get("communities", [])
        # Rebuild partition from community detection (we need node→community mapping)
        # Since we don't get it directly, we'll use community detection again
        _, _ = self._run_community_detection(G, params.get("community_resolution", 1.0))
        # Re-run to get partition
        part, _ = self._run_community_detection(G, params.get("community_resolution", 1.0))
        if part:
            partition_map = part
            # Find high-risk community IDs
            high_risk_comm_ids = {c["community_id"] for c in communities if c.get("community_risk_label") == "High Risk"}
            for nid, cid in partition_map.items():
                if cid in high_risk_comm_ids:
                    high_risk_comm_nodes.add(nid)

        # Compute composite risk
        all_flagged_nodes = cycle_nodes_set | set(hub_nodes.keys()) | high_pr_nodes | high_risk_comm_nodes
        node_risks: list[Dict[str, Any]] = []

        for nid in all_flagged_nodes:
            if not G.has_node(nid):
                continue
            score = 0
            if nid in cycle_nodes_set:
                score += 30
            if nid in hub_nodes and hub_nodes[nid] in ("Potential Mule", "Aggregation Hub"):
                score += 25
            elif nid in hub_nodes:
                score += 10
            if nid in high_pr_nodes:
                score += 20
            if nid in high_risk_comm_nodes:
                score += 15
            if G.nodes[nid].get("fraud_edge_count", 0) > 0:
                score += 10
            score = min(score, 100)

            if score < 40:
                risk_class = "Low Risk"
            elif score < 60:
                risk_class = "Medium Risk"
            elif score < 80:
                risk_class = "High Risk"
            else:
                risk_class = "Critical Risk"

            cycle_count_node = sum(
                1 for cyc in cycle_data.get("cycles", []) if nid in cyc.get("cycle_nodes", [])
            )

            rec = self._build_node_record(G, nid, extra={
                "composite_risk_score": score,
                "risk_classification": risk_class,
                "appears_in_cycle": nid in cycle_nodes_set,
                "cycle_count": cycle_count_node,
                "hub_classification": hub_nodes.get(nid, "Normal"),
                "pagerank_score": _safe(pr_scores.get(nid, 0), 8),
                "community_id": partition_map.get(nid),
                "in_high_risk_community": nid in high_risk_comm_nodes,
            })
            node_risks.append(rec)

        node_risks.sort(key=lambda x: x.get("composite_risk_score", 0), reverse=True)

        critical = [r for r in node_risks if r.get("risk_classification") == "Critical Risk"]
        high = [r for r in node_risks if r.get("risk_classification") == "High Risk"]
        medium = [r for r in node_risks if r.get("risk_classification") == "Medium Risk"]

        total_val = gs.get("total_value_in_graph_inr", 0) or 0
        flagged_val = sum(
            (r.get("total_amount_received_inr") or 0) + (r.get("total_amount_sent_inr") or 0)
            for r in critical + high
        )
        fraud_network_pct = _safe(flagged_val / total_val * 100, 2) if total_val else 0

        # Network health score
        avg_risk = (
            np.mean([r.get("composite_risk_score", 0) for r in node_risks]) if node_risks else 0
        )
        nhs = max(0, 100 - float(avg_risk))

        risk_highlights = self._default_risk_highlights()
        risk_highlights["total_flagged_nodes"] = len(node_risks)
        risk_highlights["total_flagged_as_hubs"] = len(hub_nodes)
        risk_highlights["total_cycles_detected"] = cycle_data.get("total_cycles_found", 0)
        risk_highlights["estimated_value_at_risk_inr"] = _safe(flagged_val, 2)
        if node_risks:
            risk_highlights["highest_risk_node"] = node_risks[0]["node_id"]
            risk_highlights["highest_risk_node_score"] = node_risks[0].get("composite_risk_score", 0)

        detail = (
            f"Composite analysis: {len(critical)} Critical, {len(high)} High, "
            f"{len(medium)} Medium risk nodes. "
            f"{fraud_network_pct}% of P2P value flows through Critical+High risk nodes. "
            f"Network health score: {_safe(nhs, 1)}/100 — {self._assess_network_health(nhs)}."
        )

        summary = {
            "key_finding": f"{len(critical)} Critical + {len(high)} High risk nodes identified from combined graph intelligence.",
            "cycle_statement": f"{cycle_data.get('total_cycles_found', 0)} cycles detected, {len(cycle_nodes_set)} nodes involved.",
            "hub_statement": f"{len(hub_nodes)} hub candidates, including {sum(1 for v in hub_nodes.values() if v == 'Potential Mule')} Potential Mules.",
            "network_health_assessment": self._assess_network_health(nhs),
            "executive_narrative": self._generate_executive_narrative("composite_fraud_graph", gs, risk_highlights, detail),
        }

        results = {
            "risk_nodes": node_risks[:10],
            "risk_breakdown": {
                "critical_count": len(critical),
                "high_count": len(high),
                "medium_count": len(medium),
                "total_flagged": len(node_risks),
            },
            "network_health_score": _safe(nhs, 1),
            "fraud_network_size_pct": fraud_network_pct,
            "cycle_summary": {
                "total_cycles": cycle_data.get("total_cycles_found", 0),
                "nodes_in_cycles": len(cycle_nodes_set),
            },
            "hub_summary": {
                "total_hubs": len(hub_nodes),
                "potential_mules": sum(1 for v in hub_nodes.values() if v == "Potential Mule"),
            },
            "community_summary": {
                "total_communities": len(communities),
                "high_risk_communities": sum(
                    1 for c in communities if c.get("community_risk_label") == "High Risk"
                ),
            },
        }
        return self._success("composite_fraud_graph", gs, results, risk_highlights, summary,
                             cached=cached, note=note, filters_applied=params.get("filters", []))

    # ==================================================================
    # Unused-named wrappers (specification compliance)
    # ==================================================================

    def _compute_centrality_metrics(self, G: nx.MultiDiGraph) -> Dict[str, Dict[str, float]]:
        """Return in/out degree centrality dicts."""
        return {
            "in": nx.in_degree_centrality(G),
            "out": nx.out_degree_centrality(G),
        }

    def _compute_composite_node_risk(self, *args, **kwargs) -> float:
        """Placeholder — actual logic is inline in _composite_fraud_graph."""
        return 0.0


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def create_network_graph_tool() -> StructuredTool:
    """
    Factory function to create the network graph analysis tool for LangChain.

    Returns:
        StructuredTool configured for P2P network graph analysis.
    """
    tool_instance = NetworkGraphTool()

    return StructuredTool.from_function(
        func=tool_instance.analyze,
        name="network_graph_tool",
        description=(
            "For ALL P2P network relationship analysis, money flow graph analysis, "
            "cycle detection, round-tripping detection, money mule identification, "
            "hub detection, centrality analysis, community detection, and PageRank "
            "analysis. Supports filters on any column including merchant_category, "
            "day_of_week, is_weekend, receiver_bank, receiver_age_group. "
            "This tool exclusively analyzes P2P transactions — it auto-filters to "
            "transaction_type == 'P2P'. Input: graph_analysis_type "
            "(string: graph_overview, cycle_detection, degree_centrality, "
            "hub_identification, flow_analysis, community_detection, path_analysis, "
            "temporal_graph_analysis, pagerank_analysis, composite_fraud_graph) "
            "and parameters (JSON string with time_window_hours, top_n_hubs, "
            "min_cycle_length, max_cycle_length, filters, include_amount_weights, "
            "status_filter, min_transaction_count, centrality_threshold, "
            "pagerank_damping, community_resolution, node_a, node_b)."
        ),
        args_schema=NetworkGraphInput,
    )
