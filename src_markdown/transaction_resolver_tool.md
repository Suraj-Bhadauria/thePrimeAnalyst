# tools\transaction_resolver_tool.py

```python
"""
Transaction Resolver Tool for PayInsight AI

This module provides the drill-down layer of the entire analytics platform —
the bridge between high-level analytical findings and ground-truth transaction
evidence.  Every other tool in the system operates at an aggregated or
analytical level; this tool is the **only** way to retrieve individual
transaction rows and IDs.

Supported resolution modes:
    direct_lookup, criteria_based, graph_hub_resolver, graph_cycle_resolver,
    graph_community_resolver, anomaly_resolver, ranking_resolver,
    comparison_resolver, time_window_resolver, profile_based_resolver,
    multi_finding_resolver, context_aware_resolver.

Author: Team primeFactors
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import json
import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.utils.data_loader import data_loader

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class TransactionResolverInput(BaseModel):
    """Input schema for the transaction resolver tool."""

    resolution_mode: str = Field(
        description=(
            "Type of transaction retrieval: direct_lookup, criteria_based, "
            "graph_hub_resolver, graph_cycle_resolver, graph_community_resolver, "
            "anomaly_resolver, ranking_resolver, comparison_resolver, "
            "time_window_resolver, profile_based_resolver, multi_finding_resolver, "
            "context_aware_resolver"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with resolution criteria: filters (list), top_n (int), "
            "sort_by (string), sort_ascending (bool), include_full_record (bool), "
            "include_risk_annotation (bool), deduplicate (bool), "
            "transaction_ids (list), node_id (string), node_bank (string), "
            "node_age_group (string), node_state (string), node_role (string), "
            "cycle_nodes (list), community_id (int), community_nodes (list), "
            "min_anomaly_score (float), anomaly_features (list), "
            "include_non_flagged_only (bool), segment_column (string), "
            "segment_value (string), metric_context (string), "
            "start_hour (int), end_hour (int), start_date (string), "
            "end_date (string), day_of_week_filter (list), "
            "profile_description (string), amount_range (dict), "
            "prior_tool_output (string), prior_tool_name (string), "
            "user_intent (string), finding_sets (list)"
        ),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_RESOLUTION_MODES = {
    "direct_lookup",
    "criteria_based",
    "graph_hub_resolver",
    "graph_cycle_resolver",
    "graph_community_resolver",
    "anomaly_resolver",
    "ranking_resolver",
    "comparison_resolver",
    "time_window_resolver",
    "profile_based_resolver",
    "multi_finding_resolver",
    "context_aware_resolver",
}

SORT_COLUMNS = {"amount_inr", "timestamp", "fraud_flag", "hour_of_day"}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

HOUR_LABELS: Dict[int, str] = {
    0: "12 AM", 1: "1 AM", 2: "2 AM", 3: "3 AM", 4: "4 AM", 5: "5 AM",
    6: "6 AM", 7: "7 AM", 8: "8 AM", 9: "9 AM", 10: "10 AM", 11: "11 AM",
    12: "12 PM", 13: "1 PM", 14: "2 PM", 15: "3 PM", 16: "4 PM", 17: "5 PM",
    18: "6 PM", 19: "7 PM", 20: "8 PM", 21: "9 PM", 22: "10 PM", 23: "11 PM",
}

# Bank name normalisation for profile parsing
BANK_ALIASES: Dict[str, str] = {
    "sbi": "SBI", "hdfc": "HDFC", "icici": "ICICI", "axis": "Axis",
    "pnb": "PNB", "kotak": "Kotak", "indusind": "IndusInd",
    "yes bank": "Yes Bank", "yes": "Yes Bank",
}

# State name normalisation
STATE_ALIASES: Dict[str, str] = {
    "maharashtra": "Maharashtra", "up": "Uttar Pradesh",
    "uttar pradesh": "Uttar Pradesh", "delhi": "Delhi",
    "karnataka": "Karnataka", "tamil nadu": "Tamil Nadu",
    "kerala": "Kerala", "gujarat": "Gujarat", "rajasthan": "Rajasthan",
    "west bengal": "West Bengal", "bihar": "Bihar", "punjab": "Punjab",
    "haryana": "Haryana", "madhya pradesh": "Madhya Pradesh",
    "mp": "Madhya Pradesh", "telangana": "Telangana",
    "andhra pradesh": "Andhra Pradesh", "odisha": "Odisha",
    "assam": "Assam", "jharkhand": "Jharkhand",
    "chhattisgarh": "Chhattisgarh", "goa": "Goa",
    "himachal pradesh": "Himachal Pradesh",
    "uttarakhand": "Uttarakhand",
}

# Time-of-day natural language map
TIME_OF_DAY_MAP: Dict[str, Tuple[int, int]] = {
    "night": (22, 5),
    "late night": (0, 5),
    "early morning": (4, 7),
    "morning": (6, 11),
    "afternoon": (12, 17),
    "evening": (18, 21),
    "peak hours": (9, 20),
    "off peak": (0, 8),
    "midnight": (0, 3),
    "dawn": (4, 6),
    "business hours": (9, 17),
}


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
    """Format an INR value for display with Indian number system."""
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


class TransactionResolverTool:
    """
    Transaction resolution and drill-down tool for PayInsight AI.

    Given any prior finding from any other tool in the system, this tool
    retrieves the exact transaction rows that produced or constitute that
    finding.  It supports 12 resolution modes ranging from direct ID lookup
    to fully context-aware resolution from prior tool output.

    This is the **only** tool in the system that returns individual
    transaction records and IDs.
    """

    def __init__(self) -> None:
        """Initialise with the global data_loader singleton."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

    # ==================================================================
    # Public entry point
    # ==================================================================

    def resolve(self, resolution_mode: str, parameters: str) -> str:
        """
        Main entry invoked by the LangChain tool wrapper.

        Args:
            resolution_mode: One of the twelve supported resolution modes.
            parameters: JSON string with resolution criteria and options.

        Returns:
            JSON string — success payload with transactions or error payload.
        """
        if resolution_mode not in VALID_RESOLUTION_MODES:
            return self._error_response(
                resolution_mode,
                f"Unknown resolution_mode '{resolution_mode}'. "
                f"Valid modes: {sorted(VALID_RESOLUTION_MODES)}",
                "Use one of the supported resolution_mode values.",
            )

        try:
            params: Dict[str, Any] = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                resolution_mode,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string.",
            )

        dispatch: Dict[str, Any] = {
            "direct_lookup": self._direct_lookup,
            "criteria_based": self._criteria_based,
            "graph_hub_resolver": self._graph_hub_resolver,
            "graph_cycle_resolver": self._graph_cycle_resolver,
            "graph_community_resolver": self._graph_community_resolver,
            "anomaly_resolver": self._anomaly_resolver,
            "ranking_resolver": self._ranking_resolver,
            "comparison_resolver": self._comparison_resolver,
            "time_window_resolver": self._time_window_resolver,
            "profile_based_resolver": self._profile_based_resolver,
            "multi_finding_resolver": self._multi_finding_resolver,
            "context_aware_resolver": self._context_aware_resolver,
        }

        try:
            return dispatch[resolution_mode](params)
        except Exception as exc:
            return self._error_response(
                resolution_mode,
                f"Execution error: {exc}",
                "Check parameters and retry.",
            )

    # ==================================================================
    # Resolution Modes
    # ==================================================================

    def _direct_lookup(self, params: Dict[str, Any]) -> str:
        """Retrieve one or more transactions by explicit transaction_id list."""
        transaction_ids: List[str] = params.get("transaction_ids", [])
        if not transaction_ids:
            return self._error_response(
                "direct_lookup",
                "No transaction_ids provided in parameters.",
                "Provide a 'transaction_ids' list: [\"TXN0000000001\", ...]",
            )

        df = self.df.copy()
        # Apply universal filters first
        df = self._apply_filters(df, params.get("filters", []))

        matched = df[df["transaction_id"].isin(transaction_ids)]
        found_ids = set(matched["transaction_id"].tolist())
        not_found_ids = [tid for tid in transaction_ids if tid not in found_ids]

        records = self._build_transaction_records(
            matched, params,
            default_reason="Directly requested by transaction ID",
            default_signal="direct_lookup",
        )

        output = self._build_output(
            mode="direct_lookup",
            criteria=f"Direct lookup of {len(transaction_ids)} transaction ID(s)",
            records=records,
            df_matched=matched,
            params=params,
        )
        if not_found_ids:
            output["not_found_ids"] = not_found_ids
            output["metadata"]["execution_note"] = (
                f"{len(not_found_ids)} ID(s) not found in dataset: {not_found_ids[:10]}"
            )
        return json.dumps(output, default=str)

    def _criteria_based(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions matching explicit column filter criteria."""
        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))
        df = self._apply_amount_range(df, params.get("amount_range"))
        df = self._apply_hour_range(df, params.get("start_hour"), params.get("end_hour"))
        df = self._apply_day_of_week_filter(df, params.get("day_of_week_filter"))
        df = self._apply_date_range(df, params.get("start_date"), params.get("end_date"))

        total_matching = len(df)
        total_value = float(df["amount_inr"].sum()) if total_matching > 0 else 0.0

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)

        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        criteria_desc = self._build_resolution_reason_criteria(params)
        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Transaction matching: {criteria_desc}",
            default_signal="criteria_match",
        )

        output = self._build_output(
            mode="criteria_based",
            criteria=criteria_desc,
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
        )
        output["value_summary"]["total_matching_value_inr"] = _safe(total_value, 2)
        return json.dumps(output, default=str)

    def _graph_hub_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions involving a specific hub node."""
        node_bank, node_age, node_state = self._parse_node_id(params)
        if not node_bank:
            return self._error_response(
                "graph_hub_resolver",
                "Could not determine node identity. Provide node_id "
                "(e.g., 'HDFC_26-35_Maharashtra') or node_bank + node_age_group + node_state.",
                "Example: {\"node_id\": \"HDFC_26-35_Maharashtra\", \"node_role\": \"both\"}",
            )

        node_role = params.get("node_role", "both").lower()
        df = self.df.copy()
        # Pre-filter to P2P
        df = df[df["transaction_type"] == "P2P"]
        df = self._apply_filters(df, params.get("filters", []))

        node_id_str = f"{node_bank}_{node_age}_{node_state}"

        # Build masks based on role
        sender_mask = (
            (df["sender_bank"] == node_bank)
            & (df["sender_age_group"] == node_age)
            & (df["sender_state"] == node_state)
        )
        receiver_mask = (
            (df["receiver_bank"] == node_bank)
            & (df["receiver_age_group"] == node_age)
            & (df["sender_state"] == node_state)  # dataset uses sender_state for both
        )

        if node_role == "sender":
            df_hub = df[sender_mask].copy()
        elif node_role == "receiver":
            df_hub = df[receiver_mask].copy()
        else:  # both
            df_hub = df[sender_mask | receiver_mask].copy()

        # Tag role for each row
        df_hub = df_hub.copy()
        if node_role == "both":
            df_hub.loc[:, "_node_role"] = "sender"
            df_hub.loc[receiver_mask.reindex(df_hub.index, fill_value=False), "_node_role"] = "receiver"
            both_mask = sender_mask.reindex(df_hub.index, fill_value=False) & receiver_mask.reindex(df_hub.index, fill_value=False)
            df_hub.loc[both_mask, "_node_role"] = "both"
        else:
            df_hub.loc[:, "_node_role"] = node_role

        total_matching = len(df_hub)
        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df_hub = self._sort_df(df_hub, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df_hub.head(top_n)

        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Transaction involving hub node {node_id_str} as {node_role} — flagged for high degree centrality",
            default_signal=f"hub_{node_role}",
        )

        output = self._build_output(
            mode="graph_hub_resolver",
            criteria=f"Hub node {node_id_str} as {node_role}",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="network_graph_tool",
        )

        # Hub transaction summary
        all_sender = df[sender_mask]
        all_receiver = df[receiver_mask]
        output["hub_transaction_summary"] = {
            "total_as_sender": len(all_sender),
            "total_as_receiver": len(all_receiver),
            "total_value_sent_inr": _safe(float(all_sender["amount_inr"].sum()), 2),
            "total_value_received_inr": _safe(float(all_receiver["amount_inr"].sum()), 2),
            "net_flow_direction": "net_receiver" if float(all_receiver["amount_inr"].sum()) > float(all_sender["amount_inr"].sum()) else "net_sender",
        }

        return json.dumps(output, default=str)

    def _graph_cycle_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve the exact transactions forming a detected cycle."""
        cycle_nodes: List[str] = params.get("cycle_nodes", [])
        if len(cycle_nodes) < 2:
            return self._error_response(
                "graph_cycle_resolver",
                "cycle_nodes must contain at least 2 node IDs forming the cycle.",
                "Provide cycle_nodes: [\"HDFC_26-35_Maharashtra\", \"SBI_18-25_UP\", ...]",
            )

        df = self.df.copy()
        df = df[df["transaction_type"] == "P2P"]
        status_filter = params.get("status_filter", ["SUCCESS"])
        if status_filter:
            df = df[df["transaction_status"].isin(status_filter)]
        df = self._apply_filters(df, params.get("filters", []))

        time_window_hours = params.get("time_window_hours")
        all_leg_txns: List[pd.DataFrame] = []
        cycle_length = len(cycle_nodes)

        for i in range(cycle_length):
            src_node = cycle_nodes[i]
            dst_node = cycle_nodes[(i + 1) % cycle_length]
            src_bank, src_age, src_state = self._parse_single_node_id(src_node)
            dst_bank, dst_age, dst_state = self._parse_single_node_id(dst_node)

            if not src_bank or not dst_bank:
                continue

            mask = (
                (df["sender_bank"] == src_bank)
                & (df["sender_age_group"] == src_age)
                & (df["sender_state"] == src_state)
                & (df["receiver_bank"] == dst_bank)
                & (df["receiver_age_group"] == dst_age)
            )
            leg_df = df[mask].copy()
            leg_df.loc[:, "_cycle_leg"] = i + 1
            leg_df.loc[:, "_cycle_leg_label"] = f"Leg {i + 1}: {src_node} → {dst_node}"
            all_leg_txns.append(leg_df)

        if not all_leg_txns:
            return self._build_empty_output(
                "graph_cycle_resolver",
                f"No transactions found for cycle: {' → '.join(cycle_nodes)}",
                "Verify cycle_nodes match the network_graph_tool output format (bank_agegroup_state).",
            )

        combined = pd.concat(all_leg_txns, ignore_index=True)
        total_matching = len(combined)
        total_cycle_value = float(combined["amount_inr"].sum())

        # Count cycle instances — approximate by min transactions per leg
        leg_counts = [len(leg) for leg in all_leg_txns]
        cycle_instances = min(leg_counts) if leg_counts else 0

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        combined = self._sort_df(combined, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = combined.head(top_n)

        cycle_path = " → ".join(cycle_nodes) + " → " + cycle_nodes[0]

        records: List[Dict[str, Any]] = []
        for _, row in df_limited.iterrows():
            rec = self._build_single_record(row, params)
            leg_num = int(row.get("_cycle_leg", 0))
            rec["cycle_leg"] = leg_num
            rec["cycle_leg_label"] = row.get("_cycle_leg_label", "")
            rec["resolution_reason"] = f"Part of detected cycle: {cycle_path} — Leg {leg_num}"
            rec["risk_signal"] = f"cycle_leg_{leg_num}"
            rec["risk_priority"] = self._classify_risk_priority(row, f"cycle_leg_{leg_num}")
            records.append(rec)

        output = self._build_output(
            mode="graph_cycle_resolver",
            criteria=f"Cycle: {cycle_path}",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="network_graph_tool",
        )
        output["cycle_instances"] = cycle_instances
        output["total_cycle_value"] = _safe(total_cycle_value, 2)
        output["cycle_path"] = cycle_path

        return json.dumps(output, default=str)

    def _graph_community_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve all internal transactions within a detected community."""
        community_nodes: List[str] = params.get("community_nodes", [])
        community_id = params.get("community_id")

        # Try to extract community nodes from prior_tool_output if not directly given
        if not community_nodes and params.get("prior_tool_output"):
            community_nodes = self._extract_community_nodes(
                params.get("prior_tool_output", ""),
                community_id,
            )

        if not community_nodes:
            return self._error_response(
                "graph_community_resolver",
                "No community_nodes provided. Supply community_nodes list or prior_tool_output with community_id.",
                "Example: {\"community_nodes\": [\"HDFC_26-35_Maharashtra\", ...], \"community_id\": 0}",
            )

        df = self.df.copy()
        df = df[df["transaction_type"] == "P2P"]
        df = self._apply_filters(df, params.get("filters", []))

        # Parse each community node into (bank, age, state)
        node_profiles = [self._parse_single_node_id(n) for n in community_nodes]
        valid_profiles = [(b, a, s) for b, a, s in node_profiles if b]

        if not valid_profiles:
            return self._build_empty_output(
                "graph_community_resolver",
                "Could not parse any community node IDs.",
                "Ensure node IDs are in bank_agegroup_state format.",
            )

        # Build sender and receiver membership masks
        sender_masks = pd.DataFrame(False, index=df.index, columns=["is_member"])
        receiver_masks = pd.DataFrame(False, index=df.index, columns=["is_member"])

        for bank, age, state in valid_profiles:
            s_mask = (
                (df["sender_bank"] == bank)
                & (df["sender_age_group"] == age)
                & (df["sender_state"] == state)
            )
            r_mask = (
                (df["receiver_bank"] == bank)
                & (df["receiver_age_group"] == age)
            )
            sender_masks["is_member"] = sender_masks["is_member"] | s_mask
            receiver_masks["is_member"] = receiver_masks["is_member"] | r_mask

        # Internal = both sender AND receiver in community
        internal_mask = sender_masks["is_member"] & receiver_masks["is_member"]
        df_internal = df[internal_mask].copy()

        total_matching = len(df_internal)
        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df_internal = self._sort_df(df_internal, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df_internal.head(top_n)

        cid_label = community_id if community_id is not None else "unknown"
        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Internal transaction within Community {cid_label} — both sender and receiver are members of this money flow cluster",
            default_signal="community_internal",
        )

        output = self._build_output(
            mode="graph_community_resolver",
            criteria=f"Community {cid_label} with {len(community_nodes)} nodes",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="network_graph_tool",
        )

        # Community transaction summary
        external_sender = sender_masks["is_member"] & ~receiver_masks["is_member"]
        external_receiver = ~sender_masks["is_member"] & receiver_masks["is_member"]
        internal_value = float(df_internal["amount_inr"].sum()) if total_matching > 0 else 0.0
        external_value = float(df[external_sender | external_receiver]["amount_inr"].sum())
        total_community_value = internal_value + external_value

        output["community_transaction_summary"] = {
            "internal_transaction_count": total_matching,
            "internal_value_inr": _safe(internal_value, 2),
            "internal_fraction": _safe(internal_value / total_community_value, 4) if total_community_value > 0 else 0,
            "external_fraction": _safe(external_value / total_community_value, 4) if total_community_value > 0 else 0,
        }

        return json.dumps(output, default=str)

    def _anomaly_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions flagged as anomalous by anomaly_detection_tool."""
        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))

        min_score = params.get("min_anomaly_score", 70)
        include_non_flagged_only = params.get("include_non_flagged_only", False)
        anomaly_features = params.get("anomaly_features", [])

        # Try to extract anomalies from prior_tool_output
        prior_output = params.get("prior_tool_output", "")
        anomaly_list: List[Dict[str, Any]] = []
        if prior_output:
            anomaly_list = self._parse_anomaly_output(prior_output)

        if anomaly_list:
            # Match anomalies to dataset rows using composite keys
            matched_indices: List[int] = []
            anomaly_scores: Dict[int, float] = {}
            anomaly_reasons: Dict[int, str] = {}

            for anomaly in anomaly_list:
                score = anomaly.get("anomaly_score", anomaly.get("score", 0))
                if score < min_score:
                    continue

                # Try matching by transaction_id first
                txn_id = anomaly.get("transaction_id")
                if txn_id:
                    match_idx = df.index[df["transaction_id"] == txn_id].tolist()
                else:
                    # Composite key matching: amount + type + hour
                    mask = pd.Series(True, index=df.index)
                    if "amount_inr" in anomaly:
                        mask &= (df["amount_inr"] - anomaly["amount_inr"]).abs() < 0.01
                    if "transaction_type" in anomaly:
                        mask &= df["transaction_type"] == anomaly["transaction_type"]
                    if "hour_of_day" in anomaly:
                        mask &= df["hour_of_day"] == anomaly["hour_of_day"]
                    if "sender_bank" in anomaly:
                        mask &= df["sender_bank"] == anomaly["sender_bank"]
                    match_idx = df.index[mask].tolist()

                for idx in match_idx:
                    matched_indices.append(idx)
                    anomaly_scores[idx] = score
                    anomaly_reasons[idx] = anomaly.get("reason", anomaly.get("anomaly_reasons", "Isolation Forest detection"))

            if matched_indices:
                df = df.loc[list(set(matched_indices))]
            else:
                # Fallback: use fraud_flag or high-amount heuristic
                df = df[df["fraud_flag"] == True]
        else:
            # No prior output — use fraud_flag as proxy
            df = df[df["fraud_flag"] == True]

        if include_non_flagged_only:
            df = df[df["fraud_flag"] == False]

        total_matching = len(df)
        top_n = min(params.get("top_n", 50), 500)

        # Sort by anomaly score if available, else by amount descending
        if anomaly_list and any(idx in anomaly_scores for idx in df.index):
            df = df.copy()
            df.loc[:, "_anomaly_score"] = df.index.map(lambda x: anomaly_scores.get(x, 0))
            df = df.sort_values("_anomaly_score", ascending=False)
        else:
            sort_by = params.get("sort_by", "amount_inr")
            ascending = params.get("sort_ascending", False)
            df = self._sort_df(df, sort_by, ascending)

        df_limited = df.head(top_n)

        records: List[Dict[str, Any]] = []
        for _, row in df_limited.iterrows():
            rec = self._build_single_record(row, params)
            score = anomaly_scores.get(row.name, None)
            reason_text = anomaly_reasons.get(row.name, "Anomaly detection")
            rec["resolution_reason"] = f"Flagged as anomalous by Isolation Forest with score {_safe(score)} — {reason_text}"
            rec["risk_signal"] = "isolation_forest_anomaly"
            rec["anomaly_score"] = _safe(score)
            rec["is_new_discovery"] = not bool(row.get("fraud_flag", False))
            rec["risk_priority"] = self._classify_risk_priority(row, "isolation_forest_anomaly", anomaly_score=score)
            records.append(rec)

        output = self._build_output(
            mode="anomaly_resolver",
            criteria=f"Anomalous transactions with score >= {min_score}",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="anomaly_detection_tool",
        )

        return json.dumps(output, default=str)

    def _ranking_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions belonging to a ranked segment."""
        segment_column = data_loader.resolve_column(params.get("segment_column", "")) if params.get("segment_column") else None
        segment_value = params.get("segment_value")
        metric_context = params.get("metric_context", "")

        if not segment_column or segment_value is None:
            return self._error_response(
                "ranking_resolver",
                "segment_column and segment_value are required.",
                "Example: {\"segment_column\": \"sender_state\", \"segment_value\": \"Maharashtra\", \"metric_context\": \"volume\"}",
            )

        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))

        if segment_column not in df.columns:
            return self._error_response(
                "ranking_resolver",
                f"Column '{segment_column}' not found in dataset.",
                f"Available columns: {list(df.columns[:15])}",
            )

        df = df[df[segment_column] == segment_value]
        total_matching = len(df)

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"{segment_value} was ranked for {metric_context} — this is one of its contributing transactions",
            default_signal=f"ranked_segment_{metric_context}",
        )

        output = self._build_output(
            mode="ranking_resolver",
            criteria=f"{segment_column} = {segment_value} (ranked by {metric_context})",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="ranking_tool",
        )

        return json.dumps(output, default=str)

    def _comparison_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions from a segment in a comparison analysis."""
        segment_column = data_loader.resolve_column(params.get("segment_column", "")) if params.get("segment_column") else None
        segment_value = params.get("segment_value")
        metric_context = params.get("metric_context", "")

        if not segment_column or segment_value is None:
            return self._error_response(
                "comparison_resolver",
                "segment_column and segment_value are required.",
                "Example: {\"segment_column\": \"device_type\", \"segment_value\": \"Android\", \"metric_context\": \"failure_rate\"}",
            )

        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))

        if segment_column not in df.columns:
            return self._error_response(
                "comparison_resolver",
                f"Column '{segment_column}' not found in dataset.",
                f"Available columns: {list(df.columns[:15])}",
            )

        df = df[df[segment_column] == segment_value]
        total_matching = len(df)

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        # Add metric_contribution for comparison context
        records: List[Dict[str, Any]] = []
        for _, row in df_limited.iterrows():
            rec = self._build_single_record(row, params)
            rec["resolution_reason"] = (
                f"{segment_value} was identified in comparison analysis for {metric_context} "
                f"— this transaction contributed to its metrics"
            )
            rec["risk_signal"] = "comparison_segment"
            rec["risk_priority"] = self._classify_risk_priority(row, "comparison_segment")
            # metric_contribution: relevant for failure_rate or fraud_rate comparisons
            if "failure" in metric_context.lower():
                rec["metric_contribution"] = "FAILED" if row.get("transaction_status") == "FAILED" else "SUCCESS"
            elif "fraud" in metric_context.lower():
                rec["metric_contribution"] = "FLAGGED" if row.get("fraud_flag") else "CLEAN"
            else:
                rec["metric_contribution"] = "contributing"
            records.append(rec)

        output = self._build_output(
            mode="comparison_resolver",
            criteria=f"{segment_column} = {segment_value} from comparison ({metric_context})",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
            prior_tool="comparison_tool",
        )

        return json.dumps(output, default=str)

    def _time_window_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions within a specific time window."""
        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))
        df = self._apply_amount_range(df, params.get("amount_range"))

        start_hour = params.get("start_hour")
        end_hour = params.get("end_hour")
        df = self._apply_hour_range(df, start_hour, end_hour)
        df = self._apply_day_of_week_filter(df, params.get("day_of_week_filter"))
        df = self._apply_date_range(df, params.get("start_date"), params.get("end_date"))

        total_matching = len(df)

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        hour_desc = ""
        if start_hour is not None and end_hour is not None:
            hour_desc = f"{start_hour}:00–{end_hour}:00"
        elif start_hour is not None:
            hour_desc = f"from {start_hour}:00"
        elif end_hour is not None:
            hour_desc = f"until {end_hour}:00"

        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Transaction occurred within specified time window {hour_desc}",
            default_signal="time_window_match",
        )

        output = self._build_output(
            mode="time_window_resolver",
            criteria=f"Time window: {hour_desc}" if hour_desc else "Time-based criteria",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
        )

        # Time window summary — distribution of returned transactions across hours
        if len(df_limited) > 0:
            hour_dist = df_limited["hour_of_day"].value_counts().sort_index().to_dict()
            output["time_window_summary"] = {
                str(h): int(c) for h, c in hour_dist.items()
            }

        return json.dumps(output, default=str)

    def _profile_based_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions matching a natural language profile description."""
        profile_desc = params.get("profile_description", "")
        if not profile_desc:
            return self._error_response(
                "profile_based_resolver",
                "No profile_description provided.",
                "Example: {\"profile_description\": \"high-value P2P transactions at night from HDFC users\"}",
            )

        parsed = self._parse_profile_description(profile_desc)

        df = self.df.copy()
        df = self._apply_filters(df, params.get("filters", []))

        # Apply parsed criteria
        for f in parsed.get("parsed_filters", []):
            col = data_loader.resolve_column(f.get("column", ""))
            op = f.get("operator", "==")
            val = f.get("value")
            if col not in df.columns:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > val]
            elif op == "<":
                df = df[df[col] < val]
            elif op == ">=":
                df = df[df[col] >= val]
            elif op == "<=":
                df = df[df[col] <= val]
            elif op == "in":
                df = df[df[col].isin(val)]
            elif op == "between":
                low, high = val
                if low <= high:
                    df = df[(df[col] >= low) & (df[col] <= high)]
                else:
                    # Wraparound (e.g., night: 22–5)
                    df = df[(df[col] >= low) | (df[col] <= high)]

        df = self._apply_amount_range(df, params.get("amount_range"))

        total_matching = len(df)

        if total_matching == 0:
            return self._build_empty_output(
                "profile_based_resolver",
                f"No transactions matched profile: {profile_desc}",
                f"Parsed criteria: {parsed.get('criteria_summary', 'none')}. Try broadening the criteria.",
            )

        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        criteria_summary = parsed.get("criteria_summary", profile_desc)
        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Matched profile: {criteria_summary}",
            default_signal="profile_match",
        )

        output = self._build_output(
            mode="profile_based_resolver",
            criteria=criteria_summary,
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=total_matching,
        )
        output["metadata"]["parsed_criteria_if_profile"] = parsed.get("criteria_summary", "")
        output["parsed_criteria"] = parsed

        return json.dumps(output, default=str)

    def _multi_finding_resolver(self, params: Dict[str, Any]) -> str:
        """Retrieve transactions appearing in multiple prior findings simultaneously."""
        finding_sets: List[Dict[str, Any]] = params.get("finding_sets", [])
        if len(finding_sets) < 2:
            return self._error_response(
                "multi_finding_resolver",
                "At least 2 finding_sets are required for intersection analysis.",
                "Provide finding_sets: [{\"mode\": \"anomaly_resolver\", \"params\": {...}}, {\"mode\": \"graph_cycle_resolver\", \"params\": {...}}]",
            )

        # Resolve each finding set to get transaction IDs
        set_ids: List[Tuple[str, set]] = []
        for fs in finding_sets:
            mode = fs.get("mode", "criteria_based")
            fs_params = fs.get("params", {})
            # Override top_n to a high value to get all
            fs_params["top_n"] = 500
            try:
                result_json = self.resolve(mode, json.dumps(fs_params))
                result = json.loads(result_json)
                ids = set(result.get("transaction_id_list", []))
                set_ids.append((mode, ids))
            except Exception:
                set_ids.append((mode, set()))

        if not set_ids:
            return self._build_empty_output(
                "multi_finding_resolver",
                "Could not resolve any finding sets.",
                "Check individual finding_set definitions.",
            )

        # Compute intersection
        intersection = set_ids[0][1]
        for _, ids in set_ids[1:]:
            intersection = intersection & ids

        if not intersection:
            # Build stats about individual sets
            individual_stats = [
                {"finding": mode, "count": len(ids)} for mode, ids in set_ids
            ]
            output = self._build_empty_output(
                "multi_finding_resolver",
                f"No transactions appear in all {len(set_ids)} finding sets simultaneously.",
                f"Individual set sizes: {individual_stats}. Try relaxing criteria.",
            )
            return output

        # Retrieve full records for intersection
        df = self.df[self.df["transaction_id"].isin(intersection)].copy()
        sort_by = params.get("sort_by", "amount_inr")
        ascending = params.get("sort_ascending", False)
        df = self._sort_df(df, sort_by, ascending)
        top_n = min(params.get("top_n", 50), 500)
        df_limited = df.head(top_n)

        finding_names = [mode for mode, _ in set_ids]
        records = self._build_transaction_records(
            df_limited, params,
            default_reason=f"Transaction appears in {len(set_ids)} simultaneous findings: {finding_names}",
            default_signal="multi_finding_intersection",
        )
        for rec in records:
            rec["finding_membership"] = finding_names

        output = self._build_output(
            mode="multi_finding_resolver",
            criteria=f"Intersection of {len(set_ids)} findings",
            records=records,
            df_matched=df_limited,
            params=params,
            total_matching_override=len(intersection),
        )
        output["intersection_stats"] = {
            "individual_set_sizes": [
                {"finding": mode, "count": len(ids)} for mode, ids in set_ids
            ],
            "intersection_size": len(intersection),
            "intersection_percentage": _safe(
                len(intersection) / max(min(len(ids) for _, ids in set_ids), 1) * 100, 2
            ),
        }

        return json.dumps(output, default=str)

    def _context_aware_resolver(self, params: Dict[str, Any]) -> str:
        """Automatically determine resolution criteria from conversation context."""
        prior_output_str = params.get("prior_tool_output", "")
        prior_tool_name = params.get("prior_tool_name", "")
        user_intent = params.get("user_intent", "show me the transactions")

        if not prior_output_str and not prior_tool_name:
            # Fall back to criteria_based with whatever filters are available
            return self._criteria_based(params)

        # Parse prior tool output
        prior_data: Dict[str, Any] = {}
        if prior_output_str:
            try:
                prior_data = json.loads(prior_output_str) if isinstance(prior_output_str, str) else prior_output_str
            except (json.JSONDecodeError, TypeError):
                prior_data = {}

        sub_mode, sub_params = self._determine_context_aware_submode(
            prior_data, prior_tool_name, user_intent, params
        )

        # Execute the sub-mode
        result_json = self.resolve(sub_mode, json.dumps(sub_params))

        # Augment with context-aware metadata
        try:
            result = json.loads(result_json)
            result["metadata"]["resolution_mode_used"] = "context_aware_resolver"
            result["metadata"]["sub_mode_if_context_aware"] = sub_mode
            result["resolution_interpretation"] = (
                f"Based on {prior_tool_name} output, resolved using {sub_mode} "
                f"to retrieve matching transactions."
            )
            return json.dumps(result, default=str)
        except (json.JSONDecodeError, TypeError):
            return result_json

    # ==================================================================
    # Internal helpers — filtering
    # ==================================================================

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """
        Apply a list of filter conditions to *df* and return the subset.

        Args:
            df: Source DataFrame.
            filters: List of dicts each with column, operator, value.

        Returns:
            Filtered DataFrame.
        """
        for f in filters:
            col = data_loader.resolve_column(f.get("column", ""))
            op = f.get("operator", "==")
            val = f.get("value")
            if col not in df.columns:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > val]
            elif op == "<":
                df = df[df[col] < val]
            elif op == ">=":
                df = df[df[col] >= val]
            elif op == "<=":
                df = df[df[col] <= val]
            elif op == "in":
                df = df[df[col].isin(val)]
        return df

    def _apply_amount_range(
        self, df: pd.DataFrame, amount_range: Optional[Dict[str, float]]
    ) -> pd.DataFrame:
        """Apply min/max amount_inr range filter."""
        if not amount_range:
            return df
        min_val = amount_range.get("min")
        max_val = amount_range.get("max")
        if min_val is not None:
            df = df[df["amount_inr"] >= min_val]
        if max_val is not None:
            df = df[df["amount_inr"] <= max_val]
        return df

    def _apply_hour_range(
        self, df: pd.DataFrame, start_hour: Optional[int], end_hour: Optional[int]
    ) -> pd.DataFrame:
        """Apply hour_of_day range filter, supporting wraparound (e.g. 22–5)."""
        if start_hour is None and end_hour is None:
            return df
        if start_hour is not None and end_hour is not None:
            if start_hour <= end_hour:
                df = df[(df["hour_of_day"] >= start_hour) & (df["hour_of_day"] <= end_hour)]
            else:
                # Wraparound: e.g. 22 to 5 means 22,23,0,1,2,3,4,5
                df = df[(df["hour_of_day"] >= start_hour) | (df["hour_of_day"] <= end_hour)]
        elif start_hour is not None:
            df = df[df["hour_of_day"] >= start_hour]
        elif end_hour is not None:
            df = df[df["hour_of_day"] <= end_hour]
        return df

    def _apply_day_of_week_filter(
        self, df: pd.DataFrame, day_filter: Optional[List[int]]
    ) -> pd.DataFrame:
        """Apply day_of_week filter from a list of integer day codes (0=Mon..6=Sun)."""
        if not day_filter:
            return df
        return df[df["day_of_week"].isin(day_filter)]

    def _apply_date_range(
        self, df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]
    ) -> pd.DataFrame:
        """Apply start_date / end_date filter on the timestamp column."""
        if start_date:
            try:
                df = df[df["timestamp"] >= pd.to_datetime(start_date)]
            except Exception:
                pass
        if end_date:
            try:
                df = df[df["timestamp"] <= pd.to_datetime(end_date)]
            except Exception:
                pass
        return df

    def _sort_df(
        self, df: pd.DataFrame, sort_by: str, ascending: bool = False
    ) -> pd.DataFrame:
        """Sort DataFrame by a column, falling back to amount_inr if invalid."""
        if sort_by not in df.columns:
            sort_by = "amount_inr"
        return df.sort_values(sort_by, ascending=ascending, na_position="last")

    # ==================================================================
    # Internal helpers — node ID parsing
    # ==================================================================

    def _parse_node_id(
        self, params: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract node identity from params — either from node_id or components.

        Returns:
            (bank, age_group, state) tuple.  All None if unparseable.
        """
        node_id = params.get("node_id", "")
        if node_id:
            return self._parse_single_node_id(node_id)
        bank = params.get("node_bank")
        age = params.get("node_age_group")
        state = params.get("node_state")
        if bank and age and state:
            return (bank, age, state)
        return (None, None, None)

    @staticmethod
    def _parse_single_node_id(node_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse a pseudo-node ID in 'Bank_AgeGroup_State' format.

        Handles formats like:
            - HDFC_26-35_Maharashtra
            - SBI_18-25_Uttar Pradesh
            - Yes Bank_56+_Delhi

        Returns:
            (bank, age_group, state) tuple.
        """
        if not node_id:
            return (None, None, None)

        # Age group pattern: one of 18-25, 26-35, 36-45, 46-55, 56+
        age_pattern = r"(18-25|26-35|36-45|46-55|56\+)"
        match = re.search(age_pattern, node_id)
        if not match:
            # Try splitting by underscore
            parts = node_id.split("_")
            if len(parts) >= 3:
                return (parts[0], parts[1], "_".join(parts[2:]))
            return (None, None, None)

        age_group = match.group(1)
        age_start = match.start()
        age_end = match.end()

        # Bank is everything before the age group (strip trailing underscore)
        bank = node_id[:age_start].rstrip("_").strip()
        # State is everything after the age group (strip leading underscore)
        state = node_id[age_end:].lstrip("_").strip()

        if bank and age_group and state:
            return (bank, age_group, state)
        return (None, None, None)

    def _resolve_node_to_filters(
        self, bank: str, age: str, state: str, role: str = "sender"
    ) -> List[Dict[str, Any]]:
        """Build filter conditions for a node profile as sender or receiver."""
        if role == "sender":
            return [
                {"column": "sender_bank", "operator": "==", "value": bank},
                {"column": "sender_age_group", "operator": "==", "value": age},
                {"column": "sender_state", "operator": "==", "value": state},
                {"column": "transaction_type", "operator": "==", "value": "P2P"},
            ]
        else:
            return [
                {"column": "receiver_bank", "operator": "==", "value": bank},
                {"column": "receiver_age_group", "operator": "==", "value": age},
                {"column": "transaction_type", "operator": "==", "value": "P2P"},
            ]

    # ==================================================================
    # Internal helpers — prior tool output parsing
    # ==================================================================

    def _parse_prior_tool_output(
        self, prior_data: Dict[str, Any], tool_name: str
    ) -> Dict[str, Any]:
        """
        Extract key identifiers from a prior tool's output JSON.

        Args:
            prior_data: Parsed JSON from a prior tool call.
            tool_name: Which tool produced the output.

        Returns:
            Dict with extracted identifiers (hub_nodes, cycle_nodes, etc.).
        """
        extracted: Dict[str, Any] = {}

        analysis = prior_data.get("analysis_results", prior_data)

        if tool_name == "network_graph_tool":
            # Hub nodes
            hubs = analysis.get("top_hubs", analysis.get("hub_nodes", []))
            if not hubs:
                hubs = analysis.get("hubs", [])
            extracted["hub_nodes"] = [
                h.get("node_id", h.get("node", "")) for h in hubs if isinstance(h, dict)
            ]
            # Cycles
            cycles = analysis.get("cycles", analysis.get("detected_cycles", []))
            extracted["cycles"] = cycles
            # Communities
            communities = analysis.get("communities", [])
            extracted["communities"] = communities
            # Ranked items (composite)
            ranked = analysis.get("ranked_items", analysis.get("top_anomalies", []))
            extracted["ranked_items"] = ranked

        elif tool_name == "anomaly_detection_tool":
            anomalies = analysis.get("top_anomalies", analysis.get("anomalies", []))
            extracted["anomalies"] = anomalies

        elif tool_name == "ranking_tool":
            ranked = analysis.get("ranked_items", analysis.get("rankings", []))
            if ranked and isinstance(ranked, list) and len(ranked) > 0:
                top_item = ranked[0]
                extracted["top_segment_label"] = top_item.get("label", top_item.get("dimension_value", ""))
            extracted["ranked_items"] = ranked
            # Try to get dimension
            extracted["dimension"] = analysis.get("dimension", prior_data.get("dimension", ""))

        elif tool_name == "comparison_tool":
            seg_a = analysis.get("segment_a", analysis.get("segments", {}).get("segment_a", {}))
            seg_b = analysis.get("segment_b", analysis.get("segments", {}).get("segment_b", {}))
            extracted["segment_a_label"] = seg_a.get("label", seg_a.get("name", "")) if isinstance(seg_a, dict) else ""
            extracted["segment_b_label"] = seg_b.get("label", seg_b.get("name", "")) if isinstance(seg_b, dict) else ""
            extracted["segment_column"] = analysis.get("segment_column", prior_data.get("segment_column", ""))

        elif tool_name == "multi_metric_tool":
            filters = analysis.get("filters_applied", prior_data.get("filters_applied", []))
            extracted["filters"] = filters

        elif tool_name == "trend_tool":
            peaks = analysis.get("peak_points", analysis.get("peaks", []))
            extracted["peaks"] = peaks
            extracted["filters"] = analysis.get("filters_applied", [])

        return extracted

    def _parse_anomaly_output(self, prior_output: str) -> List[Dict[str, Any]]:
        """Parse anomaly detection output to extract anomaly records."""
        try:
            data = json.loads(prior_output) if isinstance(prior_output, str) else prior_output
        except (json.JSONDecodeError, TypeError):
            return []

        analysis = data.get("analysis_results", data)
        anomalies = analysis.get("top_anomalies", analysis.get("anomalies", []))
        if isinstance(anomalies, list):
            return anomalies
        return []

    def _extract_community_nodes(
        self, prior_output: str, community_id: Optional[int]
    ) -> List[str]:
        """Extract community node list from network_graph_tool output."""
        try:
            data = json.loads(prior_output) if isinstance(prior_output, str) else prior_output
        except (json.JSONDecodeError, TypeError):
            return []

        analysis = data.get("analysis_results", data)
        communities = analysis.get("communities", [])

        if community_id is not None and isinstance(communities, list):
            for comm in communities:
                if isinstance(comm, dict):
                    cid = comm.get("community_id", comm.get("id"))
                    if cid == community_id:
                        return comm.get("nodes", comm.get("members", []))

        # If no specific match, return the first community
        if communities and isinstance(communities, list) and isinstance(communities[0], dict):
            return communities[0].get("nodes", communities[0].get("members", []))
        return []

    # ==================================================================
    # Internal helpers — profile description parsing
    # ==================================================================

    def _parse_profile_description(self, desc: str) -> Dict[str, Any]:
        """
        Parse a natural language profile description into filter conditions.

        Handles bank names, transaction types, time-of-day, amounts,
        statuses, devices, networks, states, age groups, weekend/weekday,
        and fraud mentions.

        Args:
            desc: Natural language profile description.

        Returns:
            Dict with 'parsed_filters' (list of filters) and 'criteria_summary'.
        """
        desc_lower = desc.lower()
        filters: List[Dict[str, Any]] = []
        criteria_parts: List[str] = []

        # Bank detection
        for alias, canonical in BANK_ALIASES.items():
            if alias in desc_lower:
                filters.append({"column": "sender_bank", "operator": "==", "value": canonical})
                criteria_parts.append(f"sender_bank={canonical}")
                break

        # Transaction type detection
        type_map = {
            "p2p": "P2P", "p2m": "P2M", "bill payment": "Bill Payment",
            "bill_payment": "Bill Payment", "recharge": "Recharge",
        }
        for alias, canonical in type_map.items():
            if alias in desc_lower:
                filters.append({"column": "transaction_type", "operator": "==", "value": canonical})
                criteria_parts.append(f"transaction_type={canonical}")
                break

        # Time of day detection
        for time_label, (start, end) in TIME_OF_DAY_MAP.items():
            if time_label in desc_lower:
                filters.append({"column": "hour_of_day", "operator": "between", "value": [start, end]})
                criteria_parts.append(f"hour_of_day={time_label}({start}-{end})")
                break

        # Amount detection
        high_value_match = re.search(r"high[\s-]?value", desc_lower)
        above_match = re.search(r"above\s*₹?\s*([\d,]+)", desc_lower)
        below_match = re.search(r"below\s*₹?\s*([\d,]+)", desc_lower)
        range_match = re.search(r"₹?\s*([\d,]+)\s*(?:to|-)\s*₹?\s*([\d,]+)", desc_lower)

        if range_match:
            low = float(range_match.group(1).replace(",", ""))
            high = float(range_match.group(2).replace(",", ""))
            filters.append({"column": "amount_inr", "operator": ">=", "value": low})
            filters.append({"column": "amount_inr", "operator": "<=", "value": high})
            criteria_parts.append(f"amount_inr ₹{low:,.0f}–₹{high:,.0f}")
        elif above_match:
            val = float(above_match.group(1).replace(",", ""))
            filters.append({"column": "amount_inr", "operator": ">", "value": val})
            criteria_parts.append(f"amount_inr > ₹{val:,.0f}")
        elif below_match:
            val = float(below_match.group(1).replace(",", ""))
            filters.append({"column": "amount_inr", "operator": "<", "value": val})
            criteria_parts.append(f"amount_inr < ₹{val:,.0f}")
        elif high_value_match:
            filters.append({"column": "amount_inr", "operator": ">", "value": 10000})
            criteria_parts.append("amount_inr > ₹10,000 (high-value)")

        # Status detection
        status_map = {
            "failed": "FAILED", "fail": "FAILED",
            "successful": "SUCCESS", "success": "SUCCESS",
            "pending": "PENDING",
        }
        for alias, canonical in status_map.items():
            if alias in desc_lower:
                filters.append({"column": "transaction_status", "operator": "==", "value": canonical})
                criteria_parts.append(f"transaction_status={canonical}")
                break

        # Device detection
        device_map = {"android": "Android", "ios": "iOS", "web": "Web"}
        for alias, canonical in device_map.items():
            if alias in desc_lower:
                filters.append({"column": "device_type", "operator": "==", "value": canonical})
                criteria_parts.append(f"device_type={canonical}")
                break

        # Network detection
        net_map = {"5g": "5G", "4g": "4G", "wifi": "WiFi", "wi-fi": "WiFi"}
        for alias, canonical in net_map.items():
            if alias in desc_lower:
                filters.append({"column": "network_type", "operator": "==", "value": canonical})
                criteria_parts.append(f"network_type={canonical}")
                break

        # State detection
        for alias, canonical in STATE_ALIASES.items():
            if alias in desc_lower:
                filters.append({"column": "sender_state", "operator": "==", "value": canonical})
                criteria_parts.append(f"sender_state={canonical}")
                break

        # Age group detection
        age_patterns = {
            r"18[\s-]*25|young|youth": "18-25",
            r"26[\s-]*35": "26-35",
            r"36[\s-]*45|middle[\s-]?age": "36-45",
            r"46[\s-]*55": "46-55",
            r"56\+|senior|elderly|old": "56+",
        }
        for pattern, age_val in age_patterns.items():
            if re.search(pattern, desc_lower):
                filters.append({"column": "sender_age_group", "operator": "==", "value": age_val})
                criteria_parts.append(f"sender_age_group={age_val}")
                break

        # Weekend/weekday detection
        if "weekend" in desc_lower:
            filters.append({"column": "is_weekend", "operator": "==", "value": True})
            criteria_parts.append("is_weekend=True")
        elif "weekday" in desc_lower:
            filters.append({"column": "is_weekend", "operator": "==", "value": False})
            criteria_parts.append("is_weekend=False")

        # Fraud detection
        fraud_words = ["fraud", "flagged", "suspicious", "marked"]
        if any(w in desc_lower for w in fraud_words):
            filters.append({"column": "fraud_flag", "operator": "==", "value": True})
            criteria_parts.append("fraud_flag=True")

        criteria_summary = ", ".join(criteria_parts) if criteria_parts else f"profile: {desc}"

        return {
            "parsed_filters": filters,
            "criteria_summary": criteria_summary,
            "criteria_parts": criteria_parts,
        }

    # ==================================================================
    # Internal helpers — context-aware sub-mode determination
    # ==================================================================

    def _determine_context_aware_submode(
        self,
        prior_data: Dict[str, Any],
        prior_tool_name: str,
        user_intent: str,
        original_params: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Determine which sub-resolution mode to use based on prior tool context.

        Args:
            prior_data: Parsed JSON from a prior tool call.
            prior_tool_name: Which tool produced the output.
            user_intent: What the user asked after seeing the prior result.
            original_params: Original parameters from the resolver call.

        Returns:
            (sub_mode, sub_params) tuple.
        """
        extracted = self._parse_prior_tool_output(prior_data, prior_tool_name)
        intent_lower = user_intent.lower() if user_intent else ""

        # Carry over universal params
        base_params: Dict[str, Any] = {
            "filters": original_params.get("filters", []),
            "top_n": original_params.get("top_n", 50),
            "sort_by": original_params.get("sort_by", "amount_inr"),
            "sort_ascending": original_params.get("sort_ascending", False),
        }

        if prior_tool_name == "network_graph_tool":
            # Check for cycle-related intent
            if any(w in intent_lower for w in ["cycle", "round", "circular", "loop"]):
                cycles = extracted.get("cycles", [])
                if cycles and isinstance(cycles[0], dict):
                    cycle_nodes = cycles[0].get("cycle_nodes", cycles[0].get("nodes", []))
                elif cycles and isinstance(cycles[0], list):
                    cycle_nodes = cycles[0]
                else:
                    cycle_nodes = []
                if cycle_nodes:
                    return ("graph_cycle_resolver", {**base_params, "cycle_nodes": cycle_nodes})

            # Check for community-related intent
            if any(w in intent_lower for w in ["community", "cluster", "group"]):
                communities = extracted.get("communities", [])
                if communities and isinstance(communities[0], dict):
                    nodes = communities[0].get("nodes", communities[0].get("members", []))
                    cid = communities[0].get("community_id", communities[0].get("id", 0))
                    return ("graph_community_resolver", {
                        **base_params,
                        "community_nodes": nodes,
                        "community_id": cid,
                    })

            # Default: hub resolver with top hub
            hub_nodes = extracted.get("hub_nodes", [])
            if hub_nodes:
                return ("graph_hub_resolver", {
                    **base_params,
                    "node_id": hub_nodes[0],
                    "node_role": "both",
                })

            # Final fallback: try ranked_items for composite fraud
            ranked = extracted.get("ranked_items", [])
            if ranked and isinstance(ranked[0], dict):
                node_id = ranked[0].get("node_id", ranked[0].get("node", ""))
                if node_id:
                    return ("graph_hub_resolver", {
                        **base_params,
                        "node_id": node_id,
                        "node_role": "both",
                    })

        elif prior_tool_name == "anomaly_detection_tool":
            return ("anomaly_resolver", {
                **base_params,
                "prior_tool_output": json.dumps(prior_data),
                "min_anomaly_score": original_params.get("min_anomaly_score", 70),
                "include_non_flagged_only": original_params.get("include_non_flagged_only", False),
            })

        elif prior_tool_name == "ranking_tool":
            dimension = extracted.get("dimension", "")
            top_label = extracted.get("top_segment_label", "")
            if dimension and top_label:
                return ("ranking_resolver", {
                    **base_params,
                    "segment_column": dimension,
                    "segment_value": top_label,
                    "metric_context": "ranking",
                })

        elif prior_tool_name == "comparison_tool":
            seg_col = extracted.get("segment_column", "")
            label_a = extracted.get("segment_a_label", "")
            label_b = extracted.get("segment_b_label", "")
            # Determine which segment user is interested in from intent
            target_label = label_a
            if label_b and label_b.lower() in intent_lower:
                target_label = label_b
            if seg_col and target_label:
                return ("comparison_resolver", {
                    **base_params,
                    "segment_column": seg_col,
                    "segment_value": target_label,
                    "metric_context": "comparison",
                })

        elif prior_tool_name == "multi_metric_tool":
            prior_filters = extracted.get("filters", [])
            return ("criteria_based", {
                **base_params,
                "filters": prior_filters + base_params.get("filters", []),
            })

        elif prior_tool_name == "trend_tool":
            prior_filters = extracted.get("filters", [])
            peaks = extracted.get("peaks", [])
            if peaks and isinstance(peaks[0], dict):
                peak_hour = peaks[0].get("hour", peaks[0].get("hour_of_day"))
                if peak_hour is not None:
                    return ("time_window_resolver", {
                        **base_params,
                        "start_hour": max(0, int(peak_hour) - 1),
                        "end_hour": min(23, int(peak_hour) + 1),
                        "filters": prior_filters + base_params.get("filters", []),
                    })
            return ("criteria_based", {
                **base_params,
                "filters": prior_filters + base_params.get("filters", []),
            })

        # Global fallback: criteria_based with profile parsing from user_intent
        if user_intent:
            return ("profile_based_resolver", {
                **base_params,
                "profile_description": user_intent,
            })

        return ("criteria_based", base_params)

    # ==================================================================
    # Internal helpers — risk classification
    # ==================================================================

    def _classify_risk_priority(
        self,
        row: pd.Series,
        risk_signal: str,
        anomaly_score: Optional[float] = None,
    ) -> str:
        """
        Classify a transaction into Critical / High / Medium / Low risk.

        Args:
            row: Transaction row from DataFrame.
            risk_signal: The risk signal category string.
            anomaly_score: Optional anomaly score (0–100).

        Returns:
            Risk priority string.
        """
        critical_signals = {"cycle_leg", "hub_receiver"}
        critical_conditions = 0

        fraud_flag = bool(row.get("fraud_flag", False))
        amount = float(row.get("amount_inr", 0))
        hour = int(row.get("hour_of_day", 12))
        device = str(row.get("device_type", ""))
        network = str(row.get("network_type", ""))

        if fraud_flag:
            critical_conditions += 1
        if amount > 25000:
            critical_conditions += 1
        if 0 <= hour <= 5:
            critical_conditions += 1
        if device == "Web" and network in ("3G", "4G"):
            critical_conditions += 1
        if any(risk_signal.startswith(s) for s in critical_signals):
            critical_conditions += 1
        if anomaly_score is not None and anomaly_score > 80:
            critical_conditions += 1

        if critical_conditions >= 2:
            return "Critical"
        if critical_conditions >= 1 or risk_signal == "multi_finding_intersection" or fraud_flag:
            return "High"
        if risk_signal in (
            "community_internal", "isolation_forest_anomaly",
            "hub_sender", "hub_both", "cycle_leg_1", "cycle_leg_2", "cycle_leg_3",
        ):
            return "Medium"
        return "Low"

    # ==================================================================
    # Internal helpers — record building
    # ==================================================================

    def _build_single_record(
        self, row: pd.Series, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a complete transaction record dict from a DataFrame row.

        Args:
            row: Single row from the DataFrame.
            params: Resolution parameters (for include_full_record, etc.).

        Returns:
            Dict with all transaction fields.
        """
        include_full = params.get("include_full_record", True)

        # Timestamp formatting
        ts = row.get("timestamp")
        ts_formatted = str(ts) if pd.notna(ts) else "N/A"
        ts_human = "N/A"
        if pd.notna(ts):
            try:
                ts_dt = pd.Timestamp(ts)
                ts_formatted = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
                ts_human = ts_dt.strftime("%A, %b %d at %-I:%M %p") if hasattr(ts_dt, 'strftime') else str(ts)
                # Windows strftime doesn't support %-I, fallback
                try:
                    ts_human = ts_dt.strftime("%A, %b %d at %I:%M %p").replace(" 0", " ")
                except Exception:
                    ts_human = str(ts)
            except Exception:
                pass

        amount = float(row.get("amount_inr", 0))
        hour = int(row.get("hour_of_day", 0))
        dow = int(row.get("day_of_week", 0))
        is_wknd = bool(row.get("is_weekend", False))
        fraud = bool(row.get("fraud_flag", False))

        record: Dict[str, Any] = {
            # Identity
            "transaction_id": str(row.get("transaction_id", "")),
            "timestamp": ts_formatted,
            "timestamp_human": ts_human,
            # Transaction details
            "transaction_type": str(row.get("transaction_type", "")),
            "merchant_category": str(row.get("merchant_category", "N/A")) if pd.notna(row.get("merchant_category")) else "N/A",
            "amount_inr": _safe(amount, 2),
            "amount_inr_formatted": _fmt_inr(amount),
            "transaction_status": str(row.get("transaction_status", "")),
            # Sender profile
            "sender_bank": str(row.get("sender_bank", "")),
            "sender_age_group": str(row.get("sender_age_group", "")),
            "sender_state": str(row.get("sender_state", "")),
            "sender_node_id": f"{row.get('sender_bank', '')}_{row.get('sender_age_group', '')}_{row.get('sender_state', '')}",
        }

        # Receiver profile
        rec_bank = str(row.get("receiver_bank", "")) if pd.notna(row.get("receiver_bank")) else "N/A"
        rec_age = str(row.get("receiver_age_group", "")) if pd.notna(row.get("receiver_age_group")) else "N/A"
        record["receiver_bank"] = rec_bank
        record["receiver_age_group"] = rec_age
        record["receiver_node_id"] = f"{rec_bank}_{rec_age}" if rec_bank != "N/A" else "N/A"

        if include_full:
            record.update({
                "device_type": str(row.get("device_type", "")),
                "network_type": str(row.get("network_type", "")),
                "hour_of_day": hour,
                "hour_label": HOUR_LABELS.get(hour, f"{hour}:00"),
                "day_of_week": dow,
                "day_label": DAY_NAMES[dow] if 0 <= dow <= 6 else str(dow),
                "is_weekend": is_wknd,
                "weekend_label": "Weekend" if is_wknd else "Weekday",
                "fraud_flag": fraud,
                "fraud_label": "⚠️ Flagged" if fraud else "Clean",
            })

        # Resolution fields — set defaults, caller will override
        record["resolution_reason"] = ""
        record["risk_signal"] = ""
        record["risk_priority"] = "Low"
        record["anomaly_score"] = None
        record["finding_source"] = ""

        return record

    def _build_transaction_records(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any],
        default_reason: str = "",
        default_signal: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Build a list of complete transaction record dicts from a DataFrame.

        Args:
            df: Filtered/sorted DataFrame.
            params: Resolution parameters.
            default_reason: Default resolution_reason for each record.
            default_signal: Default risk_signal for each record.

        Returns:
            List of transaction record dicts.
        """
        include_risk = params.get("include_risk_annotation", True)
        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            rec = self._build_single_record(row, params)
            if include_risk:
                rec["resolution_reason"] = default_reason
                rec["risk_signal"] = default_signal
                rec["risk_priority"] = self._classify_risk_priority(row, default_signal)
            records.append(rec)
        return records

    def _build_resolution_reason_criteria(self, params: Dict[str, Any]) -> str:
        """Build a human-readable criteria description from params."""
        parts: List[str] = []
        for f in params.get("filters", []):
            col = f.get("column", "")
            op = f.get("operator", "==")
            val = f.get("value", "")
            parts.append(f"{col}{op}{val}")
        if params.get("amount_range"):
            ar = params["amount_range"]
            if "min" in ar:
                parts.append(f"amount_inr >= {ar['min']}")
            if "max" in ar:
                parts.append(f"amount_inr <= {ar['max']}")
        if params.get("start_hour") is not None:
            parts.append(f"hour_of_day >= {params['start_hour']}")
        if params.get("end_hour") is not None:
            parts.append(f"hour_of_day <= {params['end_hour']}")
        return ", ".join(parts) if parts else "all transactions"

    # ==================================================================
    # Internal helpers — summaries & output
    # ==================================================================

    def _compute_value_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute the value_summary block from a DataFrame of matched transactions."""
        if len(df) == 0:
            return {
                "total_amount_returned_inr": 0,
                "avg_amount_returned_inr": 0,
                "max_amount_inr": 0,
                "min_amount_inr": 0,
                "fraud_flagged_count": 0,
                "fraud_flagged_value_inr": 0,
                "success_count": 0,
                "failed_count": 0,
                "pending_count": 0,
            }

        fraud_df = df[df["fraud_flag"] == True]
        return {
            "total_amount_returned_inr": _safe(float(df["amount_inr"].sum()), 2),
            "avg_amount_returned_inr": _safe(float(df["amount_inr"].mean()), 2),
            "max_amount_inr": _safe(float(df["amount_inr"].max()), 2),
            "min_amount_inr": _safe(float(df["amount_inr"].min()), 2),
            "fraud_flagged_count": int(len(fraud_df)),
            "fraud_flagged_value_inr": _safe(float(fraud_df["amount_inr"].sum()), 2) if len(fraud_df) > 0 else 0,
            "success_count": int((df["transaction_status"] == "SUCCESS").sum()),
            "failed_count": int((df["transaction_status"] == "FAILED").sum()),
            "pending_count": int((df["transaction_status"] == "PENDING").sum()),
        }

    def _build_executive_narrative(
        self,
        mode: str,
        criteria: str,
        records: List[Dict[str, Any]],
        df: pd.DataFrame,
        total_matching: int,
    ) -> str:
        """
        Build a 3-4 sentence executive narrative explaining retrieved transactions.

        Args:
            mode: Resolution mode used.
            criteria: Human-readable criteria string.
            records: List of built transaction records.
            df: DataFrame of returned transactions.
            total_matching: Total number of matching transactions before top_n.

        Returns:
            Plain English narrative string.
        """
        count = len(records)
        if count == 0:
            return f"No transactions were found matching the criteria: {criteria}."

        # Sentence 1: What was retrieved
        s1 = (
            f"{count} transaction{'s' if count != 1 else ''} "
            f"{'have' if count != 1 else 'has'} been retrieved"
        )
        if total_matching > count:
            s1 += f" from {total_matching:,} total matches"
        s1 += f" based on {criteria}."

        # Sentence 2: Highlight most important transaction
        highest_val = max(records, key=lambda r: r.get("amount_inr", 0))
        s2 = (
            f"The highest-value transaction is {highest_val.get('transaction_id', 'N/A')} "
            f"— {highest_val.get('amount_inr_formatted', 'N/A')} "
            f"({highest_val.get('transaction_type', '')}) "
            f"from {highest_val.get('sender_bank', '')} "
            f"{highest_val.get('sender_age_group', '')} {highest_val.get('sender_state', '')}."
        )

        # Sentence 3: Fraud signal strength
        fraud_count = sum(1 for r in records if r.get("fraud_flag") or r.get("fraud_label") == "⚠️ Flagged")
        non_fraud_count = count - fraud_count
        if fraud_count > 0:
            non_fraud_value = sum(
                r.get("amount_inr", 0) for r in records
                if not r.get("fraud_flag") and r.get("fraud_label") != "⚠️ Flagged"
            )
            s3 = (
                f"Of the {count} retrieved transactions, {fraud_count} carry existing fraud flags "
                f"while {non_fraud_count} are currently unflagged"
            )
            if non_fraud_count > 0:
                s3 += f" — representing potential new evidence worth {_fmt_inr(non_fraud_value)}"
            s3 += "."
        else:
            s3 = f"None of the {count} retrieved transactions carry existing fraud flags."

        # Sentence 4: Actionable next step
        critical_txns = [r for r in records if r.get("risk_priority") == "Critical"]
        if critical_txns:
            top_ids = [r["transaction_id"] for r in critical_txns[:3]]
            s4 = (
                f"Priority review recommended for {', '.join(top_ids)} "
                f"which carry Critical risk priority."
            )
        else:
            high_txns = [r for r in records if r.get("risk_priority") == "High"]
            if high_txns:
                top_ids = [r["transaction_id"] for r in high_txns[:3]]
                s4 = f"Review recommended for {', '.join(top_ids)} which carry High risk priority."
            else:
                s4 = f"These {count} transactions should be reviewed as part of the ongoing analysis."

        return f"{s1} {s2} {s3} {s4}"

    def _build_output(
        self,
        mode: str,
        criteria: str,
        records: List[Dict[str, Any]],
        df_matched: pd.DataFrame,
        params: Dict[str, Any],
        total_matching_override: Optional[int] = None,
        prior_tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the standardised output wrapper structure.

        Args:
            mode: Resolution mode used.
            criteria: Human-readable criteria.
            records: List of transaction record dicts.
            df_matched: DataFrame of the returned transactions.
            params: Resolution parameters.
            total_matching_override: If provided, use this as total matching count.
            prior_tool: Name of the prior tool that provided context.

        Returns:
            Dict with the full output structure.
        """
        top_n = min(params.get("top_n", 50), 500)
        total_matching = total_matching_override if total_matching_override is not None else len(df_matched)

        # Deduplicate
        if params.get("deduplicate", True) and records:
            seen: set = set()
            deduped: List[Dict[str, Any]] = []
            for r in records:
                tid = r.get("transaction_id", "")
                if tid not in seen:
                    seen.add(tid)
                    deduped.append(r)
            records = deduped

        transaction_id_list = [r.get("transaction_id", "") for r in records]
        value_summary = self._compute_value_summary(df_matched)

        # Risk breakdown
        risk_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for r in records:
            rp = r.get("risk_priority", "Low")
            if rp in risk_counts:
                risk_counts[rp] += 1

        # Highest value transaction
        highest_val_txn = ""
        most_suspicious_txn = ""
        new_fraud = 0
        if records:
            hv = max(records, key=lambda r: r.get("amount_inr", 0))
            highest_val_txn = f"{hv.get('transaction_id', '')} ({hv.get('amount_inr_formatted', '')})"
            critical_recs = [r for r in records if r.get("risk_priority") == "Critical"]
            if critical_recs:
                ms = critical_recs[0]
                most_suspicious_txn = f"{ms.get('transaction_id', '')} — {ms.get('resolution_reason', '')}"
            else:
                high_recs = [r for r in records if r.get("risk_priority") == "High"]
                if high_recs:
                    ms = high_recs[0]
                    most_suspicious_txn = f"{ms.get('transaction_id', '')} — {ms.get('resolution_reason', '')}"
            new_fraud = sum(
                1 for r in records
                if not r.get("fraud_flag") and r.get("risk_priority") in ("Critical", "High")
            )

        executive_narrative = self._build_executive_narrative(
            mode, criteria, records, df_matched, total_matching
        )

        sort_col = params.get("sort_by", "amount_inr")
        sort_dir = "ascending" if params.get("sort_ascending", False) else "descending"

        return {
            "success": True,
            "resolution_mode": mode,
            "resolution_criteria": criteria,
            "prior_tool_context": prior_tool or "none",
            "filters_applied": params.get("filters", []),
            "pagination": {
                "total_matching_transactions": total_matching,
                "transactions_returned": len(records),
                "top_n_limit": top_n,
                "has_more": total_matching > len(records),
                "more_count": max(0, total_matching - len(records)),
            },
            "transactions": records,
            "transaction_id_list": transaction_id_list,
            "value_summary": value_summary,
            "risk_breakdown": {
                "critical_priority_count": risk_counts["Critical"],
                "high_priority_count": risk_counts["High"],
                "medium_priority_count": risk_counts["Medium"],
                "low_priority_count": risk_counts["Low"],
            },
            "summary": {
                "key_finding": f"{len(records)} transactions retrieved via {mode}",
                "transaction_count_statement": (
                    f"{len(records)} transactions retrieved from {total_matching:,} total matches"
                ),
                "highest_value_transaction": highest_val_txn,
                "most_suspicious_transaction": most_suspicious_txn,
                "new_fraud_discoveries": str(new_fraud),
                "executive_narrative": executive_narrative,
            },
            "metadata": {
                "resolution_mode_used": mode,
                "sub_mode_if_context_aware": "",
                "parsed_criteria_if_profile": "",
                "sort_applied": f"{sort_col} {sort_dir}",
                "execution_note": "",
            },
        }

    def _build_empty_output(
        self, mode: str, reason: str, suggestion: str
    ) -> str:
        """
        Build a structured zero-result response — never an empty JSON.

        Args:
            mode: Resolution mode attempted.
            reason: Why zero results were found.
            suggestion: What to try instead.

        Returns:
            JSON string with success=true but empty transactions.
        """
        output = {
            "success": True,
            "resolution_mode": mode,
            "resolution_criteria": reason,
            "prior_tool_context": "none",
            "filters_applied": [],
            "pagination": {
                "total_matching_transactions": 0,
                "transactions_returned": 0,
                "top_n_limit": 50,
                "has_more": False,
                "more_count": 0,
            },
            "transactions": [],
            "transaction_id_list": [],
            "value_summary": {
                "total_amount_returned_inr": 0,
                "avg_amount_returned_inr": 0,
                "max_amount_inr": 0,
                "min_amount_inr": 0,
                "fraud_flagged_count": 0,
                "fraud_flagged_value_inr": 0,
                "success_count": 0,
                "failed_count": 0,
                "pending_count": 0,
            },
            "risk_breakdown": {
                "critical_priority_count": 0,
                "high_priority_count": 0,
                "medium_priority_count": 0,
                "low_priority_count": 0,
            },
            "summary": {
                "key_finding": f"No transactions found for {mode}",
                "transaction_count_statement": "0 transactions retrieved — no matches",
                "highest_value_transaction": "N/A",
                "most_suspicious_transaction": "N/A",
                "new_fraud_discoveries": "0",
                "executive_narrative": (
                    f"No transactions were found matching the criteria. "
                    f"Reason: {reason}. Suggestion: {suggestion}"
                ),
            },
            "metadata": {
                "resolution_mode_used": mode,
                "sub_mode_if_context_aware": "",
                "parsed_criteria_if_profile": "",
                "sort_applied": "N/A",
                "execution_note": f"ZERO RESULTS — {reason}. {suggestion}",
            },
        }
        return json.dumps(output, default=str)

    def _error_response(
        self, mode: str, error_msg: str, suggestion: str
    ) -> str:
        """
        Build a structured error response.

        Args:
            mode: Resolution mode attempted.
            error_msg: Specific error message.
            suggestion: What the caller should try instead.

        Returns:
            JSON string with success=false.
        """
        return json.dumps({
            "success": False,
            "resolution_mode": mode,
            "error": error_msg,
            "suggestion": suggestion,
            "fallback_options": [
                "Use criteria_based with explicit filters",
                "Use profile_based_resolver with a natural language description",
                "Use direct_lookup with specific transaction IDs",
            ],
        }, default=str)

    def _format_amount(self, amount: float) -> str:
        """Format amount with ₹ symbol and comma separators."""
        return _fmt_inr(amount)

    def _format_timestamp(self, ts: Any) -> Tuple[str, str]:
        """
        Format a timestamp into ISO and human-readable forms.

        Returns:
            (iso_string, human_readable_string) tuple.
        """
        if pd.isna(ts):
            return ("N/A", "N/A")
        try:
            ts_dt = pd.Timestamp(ts)
            iso = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
            try:
                human = ts_dt.strftime("%A, %b %d at %I:%M %p").replace(" 0", " ")
            except Exception:
                human = iso
            return (iso, human)
        except Exception:
            return (str(ts), str(ts))


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def create_transaction_resolver_tool() -> StructuredTool:
    """
    Factory function to create the transaction resolver tool for LangChain.

    Returns:
        StructuredTool configured for transaction resolution and drill-down.
    """
    tool_instance = TransactionResolverTool()

    return StructuredTool.from_function(
        func=tool_instance.resolve,
        name="transaction_resolver_tool",
        description=(
            "Use this WHENEVER a user asks for actual transaction IDs, specific "
            "transaction records, raw evidence behind a finding, or drill-down "
            "details after any prior analysis. This is the ONLY tool that returns "
            "individual transaction rows and IDs. Use resolution_mode "
            "'context_aware_resolver' when the user asks 'show me the transactions' "
            "or 'give me the IDs' after a prior tool output — pass the prior output "
            "as prior_tool_output parameter. Use 'criteria_based' for direct "
            "filtering requests. Use 'profile_based_resolver' for natural language "
            "transaction descriptions. NEVER return empty transaction lists — if no "
            "transactions match, explain why and suggest alternative criteria. "
            "Input: resolution_mode (string: direct_lookup, criteria_based, "
            "graph_hub_resolver, graph_cycle_resolver, graph_community_resolver, "
            "anomaly_resolver, ranking_resolver, comparison_resolver, "
            "time_window_resolver, profile_based_resolver, multi_finding_resolver, "
            "context_aware_resolver) and parameters (JSON string with filters, "
            "top_n, sort_by, prior_tool_output, prior_tool_name, user_intent, "
            "node_id, cycle_nodes, community_id, transaction_ids, "
            "segment_column, segment_value, profile_description, amount_range, "
            "min_anomaly_score, include_non_flagged_only, finding_sets)."
        ),
        args_schema=TransactionResolverInput,
    )
```
