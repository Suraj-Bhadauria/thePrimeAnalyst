# THIS IS THE MAIN ORCHESTRATION WORKFLOW FOR ALL AGENTS
# - it defines the flow how the pre-defined agents work together

from typing import TypedDict, Annotated, Callable, Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
import json
import re
import time

from src.agents.query_agent import QueryUnderstandingAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.analyzer_agent import AnalyzerAgent
from src.agents.insight_agent import InsightAgent

# SHARED STATE
# this is the common state which will be shared by all the agents to work together
class AgentState(TypedDict):
    question: str
    conversation_history: list
    query_plan: dict
    execution_plan: dict
    analysis_results: dict
    final_response: str
    error: str

class Workflow:
    # initializing the 4 agents in constructor 
    def __init__(self):
        self.query_agent = QueryUnderstandingAgent()
        self.planner_agent = PlannerAgent()
        self.analyzer_agent = AnalyzerAgent()
        self.insight_agent = InsightAgent()
        
        # Callback for thought process updates (set per-run)
        self._thinking_callback: Optional[Callable] = None
        
        # Build the graph
        self.workflow = self._build_workflow()
    
    def _emit_thought(self, step: int, title: str, status: str, detail: str = "", metadata: dict = None):
        """Emit a thought process event to the UI callback."""
        if self._thinking_callback:
            self._thinking_callback({
                "step": step,
                "title": title,
                "status": status,   # 'started', 'detail', 'completed', 'error'
                "detail": detail,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })

    # ------------------------------------------------------------------
    # Keyword-based fallbacks for LLM failures
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Filter normalization & entity-to-filter enrichment
    # ------------------------------------------------------------------

    # Columns that can be directly filtered from entity values
    _ENTITY_TO_COLUMN = {
        "merchant_category": "merchant_category",
        "transaction_type": "transaction_type",
        "device_type": "device_type",
        "network_type": "network_type",
        "state": "sender_state",
        "bank": "sender_bank",
        "age_group": "sender_age_group",
    }

    # All valid dataset column names (for recognizing malformed filter keys)
    _VALID_FILTER_COLUMNS = {
        "transaction_id", "timestamp", "transaction_type", "merchant_category",
        "amount_inr", "transaction_status", "sender_age_group", "receiver_age_group",
        "sender_state", "sender_bank", "receiver_bank", "device_type",
        "network_type", "fraud_flag", "hour_of_day", "day_of_week", "is_weekend",
    }

    # LLM shorthand aliases → canonical column names
    _COLUMN_ALIAS = {
        "category": "merchant_category",
        "merchant": "merchant_category",
        "type": "transaction_type",
        "status": "transaction_status",
        "amount": "amount_inr",
        "bank": "sender_bank",
        "state": "sender_state",
        "device": "device_type",
        "network": "network_type",
        "fraud": "fraud_flag",
        "age_group": "sender_age_group",
    }

    def _normalize_and_enrich_filters(self, query_plan: dict, question: str = "") -> dict:
        """Fix malformed filters and auto-generate filters from entities.

        The LLM sometimes produces filters as ``{"merchant_category": "Food"}``
        instead of the required ``{"column": "merchant_category", "operator": "==", "value": "Food"}``.
        This method normalizes such entries and then fills in any missing filters
        that can be inferred from extracted entities.

        Only entities whose values appear in the original question text are
        enriched into filters, to avoid converting LLM-inferred entities that
        the user did not explicitly mention (e.g. transaction_type: P2M when
        the user only said "food").
        """
        filters: list = query_plan.get("filters", []) or []
        entities: dict = query_plan.get("entities", {}) or {}
        q_lower = question.lower() if question else ""

        # --- Step 1: Normalize malformed filter dicts ---
        normalized: list = []
        for f in filters:
            if not isinstance(f, dict):
                continue
            # Already in correct format
            if "column" in f and "value" in f:
                normalized.append(f)
                continue
            # Malformed: {"merchant_category": "Food"} or {"category": "Food"}
            for key, val in f.items():
                if val is None:
                    continue
                col = key if key in self._VALID_FILTER_COLUMNS else self._COLUMN_ALIAS.get(key.lower())
                if col:
                    if isinstance(val, list):
                        normalized.append({"column": col, "operator": "in", "value": val})
                    else:
                        normalized.append({"column": col, "operator": "==", "value": val})

        # --- Step 2: Enrich from entities (add if no matching filter exists) ---
        existing_columns = {f.get("column") for f in normalized}
        for entity_key, column_name in self._ENTITY_TO_COLUMN.items():
            if column_name in existing_columns:
                continue
            val = entities.get(entity_key)
            if val and val not in (None, "null", "None", "all"):
                # Only enrich if the entity value was explicitly mentioned in the question
                val_str = str(val).lower()
                if q_lower and val_str not in q_lower:
                    continue
                if isinstance(val, list):
                    normalized.append({"column": column_name, "operator": "in", "value": val})
                else:
                    normalized.append({"column": column_name, "operator": "==", "value": val})

        if normalized != filters:
            print(f"  🔧 Filter normalization: {filters} → {normalized}")

        query_plan["filters"] = normalized
        return query_plan

    def _fallback_query_plan(self, question: str) -> dict:
        """Build a basic query plan from the question using keyword heuristics.

        Used when the LLM-based query understanding fails entirely (e.g. rate
        limits).  Covers the most common query patterns so the pipeline can
        still produce useful output without the LLM.
        """
        intent = QueryUnderstandingAgent._heuristic_intent(question)
        tool = QueryUnderstandingAgent._heuristic_suggested_tool(intent)

        q = question.lower()

        entities: Dict[str, Any] = {}

        # Detect state-related queries
        if any(kw in q for kw in ["state", "states", "india", "indian"]):
            entities["state"] = "all"

        # Extract date references from question text
        # YYYY-MM-DD or YYYY/MM/DD
        date_match = re.search(r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b', question)
        if date_match:
            entities["date_reference"] = date_match.group(1)
        else:
            # DD-MM-YYYY or DD/MM/YYYY or MM/DD/YYYY
            date_match2 = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', question)
            if date_match2:
                entities["date_reference"] = date_match2.group(1)

        # Detect metric from question
        metric = "volume"
        if any(kw in q for kw in ["failure", "fail rate"]):
            metric = "failure_rate"
        elif any(kw in q for kw in ["fraud"]):
            metric = "fraud_rate"
        elif any(kw in q for kw in ["amount", "value", "revenue"]):
            metric = "total_amount"
        elif any(kw in q for kw in ["success"]):
            metric = "success_rate"
        elif any(kw in q for kw in ["average", "avg"]):
            metric = "avg_amount"

        return {
            "intent": intent,
            "entities": entities,
            "metrics": [metric],
            "filters": [],
            "grouping": [],
            "is_followup": False,
            "suggested_tool": tool,
        }

    def _fallback_execution_plan(self, query_plan: dict, question: str) -> dict:
        """Build a minimal execution plan from a query plan and question text.

        Used when the LLM-based planner fails.  Constructs the routing fields
        that the AnalyzerAgent's deterministic fallback needs.
        """
        q = question.lower()
        intent = query_plan.get("intent", "descriptive")
        tool = query_plan.get("suggested_tool", "query_transaction_data")
        filters = query_plan.get("filters", [])

        plan: Dict[str, Any] = {
            "suggested_tool": tool,
            "analysis_intent": intent,
            "filters": filters,
            "groupby": [],
            "aggregations": [],
            "computations": [],
            "sort": None,
            "limit": None,
            "original_question": question,
        }

        # --- segmentation / ranking ---
        if intent == "segmentation":
            # Determine dimension
            if any(kw in q for kw in ["state", "states", "india", "indian"]):
                plan["segment_column"] = "sender_state"
                plan["tool_subtype"] = "state_ranking"
            elif any(kw in q for kw in ["bank", "banks"]):
                plan["segment_column"] = "sender_bank"
                plan["tool_subtype"] = "top_n" if any(kw in q for kw in ["top ", "top-"]) else "full_ranking"
            elif any(kw in q for kw in ["category", "categories", "merchant"]):
                plan["segment_column"] = "merchant_category"
                plan["tool_subtype"] = "category_ranking"
            elif any(kw in q for kw in ["device"]):
                plan["segment_column"] = "device_type"
                plan["tool_subtype"] = "full_ranking"
            elif any(kw in q for kw in ["network"]):
                plan["segment_column"] = "network_type"
                plan["tool_subtype"] = "full_ranking"
            elif any(kw in q for kw in ["age", "age group"]):
                plan["segment_column"] = "sender_age_group"
                plan["tool_subtype"] = "full_ranking"
            else:
                plan["segment_column"] = "sender_bank"
                plan["tool_subtype"] = "full_ranking"

            # Determine ranking subtype from keywords
            if "pareto" in q or "80-20" in q or "concentration" in q:
                plan["tool_subtype"] = "pareto_analysis"
            elif any(kw in q for kw in ["fraud"]):
                plan["tool_subtype"] = "fraud_ranking"
            elif any(kw in q for kw in ["failure", "fail"]):
                plan["tool_subtype"] = "failure_ranking"
            elif any(kw in q for kw in ["bottom", "worst", "least", "lowest"]):
                plan["tool_subtype"] = "bottom_n"
            elif any(kw in q for kw in ["share of wallet", "wallet share", "value share"]):
                plan["tool_subtype"] = "share_of_wallet"
            elif any(kw in q for kw in ["rank all", "full rank", "complete rank",
                                         "all state", "all bank"]):
                if plan.get("tool_subtype") != "state_ranking":
                    plan["tool_subtype"] = "full_ranking"

            # Determine metric
            if any(kw in q for kw in ["failure", "fail rate"]):
                plan["metric"] = "failure_rate"
            elif any(kw in q for kw in ["fraud"]):
                plan["metric"] = "fraud_rate"
            elif any(kw in q for kw in ["amount", "value", "revenue"]):
                plan["metric"] = "total_amount"
            elif any(kw in q for kw in ["success"]):
                plan["metric"] = "success_rate"
            elif any(kw in q for kw in ["average", "avg"]):
                plan["metric"] = "avg_amount"
            else:
                plan["metric"] = "volume"

            # Detect top_n
            top_match = re.search(r"top\s*(\d+)", q)
            bottom_match = re.search(r"bottom\s*(\d+)", q)
            if top_match:
                plan["limit"] = int(top_match.group(1))
            elif bottom_match:
                plan["limit"] = int(bottom_match.group(1))

        # --- comparative ---
        elif intent == "comparative":
            plan["tool_subtype"] = "head_to_head"
            if "device" in q:
                plan["segment_column"] = "device_type"
            elif "bank" in q:
                plan["segment_column"] = "sender_bank"
            elif "network" in q:
                plan["segment_column"] = "network_type"
            elif "state" in q:
                plan["segment_column"] = "sender_state"
            else:
                plan["segment_column"] = "device_type"

        # --- temporal ---
        elif intent == "temporal":
            if "weekend" in q and "weekday" in q:
                plan["tool_subtype"] = "weekend_vs_weekday"
            elif "peak" in q or "busiest" in q:
                plan["tool_subtype"] = "peak_hours"
            elif "day of week" in q or "daily" in q:
                plan["tool_subtype"] = "day_of_week_pattern"
            else:
                plan["tool_subtype"] = "hourly_distribution"
            plan["metric"] = "volume"

        # --- trend ---
        elif intent == "trend":
            # Determine trend subtype from keywords
            if any(kw in q for kw in ["accelerat", "decelerat", "rate of change",
                                       "speeding up", "slowing down", "momentum"]):
                plan["tool_subtype"] = "acceleration_trend"
            elif any(kw in q for kw in ["volatil", "stability", "instability",
                                         "fluctuat"]):
                plan["tool_subtype"] = "volatility_trend"
            elif any(kw in q for kw in ["cumulat", "running total", "by what hour"]):
                plan["tool_subtype"] = "cumulative_trend"
            elif any(kw in q for kw in ["anomal", "spike", "unusual point",
                                         "outlier trend"]):
                plan["tool_subtype"] = "rolling_anomaly_trend"
            elif any(kw in q for kw in ["segment", "android vs", "ios vs",
                                         "compare trend"]):
                plan["tool_subtype"] = "segmented_trend"
            else:
                plan["tool_subtype"] = "hourly_trend"

            # Determine metric from keywords
            if any(kw in q for kw in ["fraud"]):
                plan["metric"] = "fraud_rate"
            elif any(kw in q for kw in ["failure", "fail rate"]):
                plan["metric"] = "failure_rate"
            elif any(kw in q for kw in ["success"]):
                plan["metric"] = "success_rate"
            elif any(kw in q for kw in ["amount", "value", "revenue"]):
                plan["metric"] = "total_amount"
            elif any(kw in q for kw in ["average", "avg"]):
                plan["metric"] = "avg_amount"
            else:
                plan["metric"] = "volume"

            # Determine time_granularity from keywords
            if any(kw in q for kw in ["week", "day of week", "monday", "tuesday",
                                       "wednesday", "thursday", "friday",
                                       "saturday", "sunday", "daily",
                                       "weekday", "weekend"]):
                plan["time_granularity"] = "day_of_week"
            elif any(kw in q for kw in ["date", "calendar", "over the month",
                                         "across dates"]):
                plan["time_granularity"] = "date"
            else:
                plan["time_granularity"] = "hour"

            plan["smoothing_window"] = 3

        # --- date_query ---
        elif intent == "date_query":
            # Extract date_reference from query_plan entities or question
            entities = query_plan.get("entities", {}) or {}
            date_ref = entities.get("date_reference")
            if not date_ref:
                # Try to extract from question text
                dm = re.search(r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b', question)
                if dm:
                    date_ref = dm.group(1)
                else:
                    dm2 = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', question)
                    if dm2:
                        date_ref = dm2.group(1)
            plan["date_reference"] = date_ref

            # Determine the correct date_query subtype.
            # Check range keywords first (they take priority even with a specific date).
            # A specific calendar date (YYYY-MM-DD) without range keywords means single_date,
            # even if the user also says "breakdown" (e.g. "breakdown by type").
            has_specific_date = bool(date_ref and re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', date_ref))

            # Detect month names in the question (indicates month-level query)
            month_names = ["january", "february", "march", "april", "may", "june",
                           "july", "august", "september", "october", "november", "december"]
            has_month_name = any(m in q for m in month_names)

            if any(kw in q for kw in ["range", "between", "from", "to "]):
                plan["tool_subtype"] = "date_range"
            elif has_specific_date:
                plan["tool_subtype"] = "single_date"
            elif has_month_name and not has_specific_date:
                # Check if multiple month names are mentioned (month comparison)
                mentioned = [m for m in month_names if m in q]
                is_compare = any(kw in q for kw in [" vs ", "versus", "compare",
                                                     "comparison", "against",
                                                     "difference between", "compared to"])
                if len(mentioned) >= 2 or (len(mentioned) >= 2 and is_compare):
                    plan["tool_subtype"] = "month_comparison"
                else:
                    # Month name without a specific date → month_breakdown
                    plan["tool_subtype"] = "month_breakdown"
            elif any(kw in q for kw in ["month", "monthly"]):
                plan["tool_subtype"] = "month_breakdown"
            else:
                plan["tool_subtype"] = "single_date"

        # --- correlation ---
        elif intent == "correlation":
            plan["suggested_tool"] = "correlation_importance_tool"
            if any(kw in q for kw in ["combination", "multivariate", "riskiest", "profile"]):
                plan["tool_subtype"] = "multivariate_combination"
                plan["factors"] = ["sender_bank", "device_type", "network_type"]
            elif any(kw in q for kw in ["interaction", "does", "only for", "affect differently"]):
                plan["tool_subtype"] = "interaction_effects"
            elif any(kw in q for kw in ["matrix", "pairwise", "all associations", "cramers"]):
                plan["tool_subtype"] = "cramers_v_matrix"
            elif any(kw in q for kw in ["amount", "value", "point biserial"]):
                plan["tool_subtype"] = "point_biserial"
            else:
                plan["tool_subtype"] = "feature_importance"

            if any(kw in q for kw in ["fraud"]):
                plan["metric"] = "fraud"
            elif any(kw in q for kw in ["success"]):
                plan["metric"] = "success"
            else:
                plan["metric"] = "failure"

        return plan

    def _format_results_locally(self, question: str, analysis_results: dict) -> str:
        """Format analysis results as structured markdown without needing the LLM.

        Used as a last resort when the insight generation LLM fails.
        """
        if not analysis_results:
            return "⚠️ No analysis results available. Please try again."

        # Check if we have tool results
        results_list = analysis_results.get("results", [])
        if not results_list:
            error = analysis_results.get("error", "")
            if error:
                return f"⚠️ Analysis error: {error}\n\nPlease try rephrasing your question."
            resp = analysis_results.get("response", "")
            if resp:
                return resp
            return "⚠️ No analysis results available. Please try again."

        # Process each tool result
        formatted_parts = []
        for tool_result in results_list:
            tool_name = tool_result.get("tool", "unknown")
            raw = tool_result.get("result", "")

            # Parse JSON result if string
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                formatted_parts.append(str(raw))
                continue

            if not isinstance(data, dict):
                formatted_parts.append(str(data))
                continue

            if not data.get("success", False):
                formatted_parts.append(f"⚠️ {data.get('error', 'Unknown error')}")
                continue

            # Format based on tool type
            if tool_name == "ranking_tool":
                formatted_parts.append(self._format_ranking_result(data, question))
            elif tool_name == "correlation_importance_tool":
                formatted_parts.append(self._format_correlation_result(data, question))
            else:
                # Generic formatting for other tools
                formatted_parts.append(self._format_generic_result(data, question))

        return "\n\n".join(formatted_parts) if formatted_parts else "⚠️ Could not format results."

    def _format_ranking_result(self, data: dict, question: str) -> str:
        """Format ranking tool results as detailed, structured markdown."""
        ranking_type = data.get("ranking_type", "ranking")
        dimension = data.get("dimension", "")
        metric = data.get("metric", "volume")
        ranked_items = data.get("ranked_items", [])
        summary = data.get("summary", {})
        pareto = data.get("pareto_insights", {})
        tier_summary = data.get("tier_summary", {})
        regional_summary = data.get("regional_summary", {})
        total_unique = data.get("total_unique_values", 0)
        total_records = data.get("total_records_analyzed", 0)

        lines = []

        # --- Header ---
        dim_label = dimension.replace("_", " ").title()
        metric_label = metric.replace("_", " ").title()
        lines.append(f"## 📊 {dim_label} Ranking by {metric_label}")
        lines.append(f"*Analyzed {total_records:,} transactions across {total_unique} {dim_label.lower()}s*\n")

        # --- Key Finding ---
        key_finding = summary.get("key_finding", "")
        if key_finding:
            lines.append(f"**💡 Key Finding:** {key_finding}\n")

        # --- Full Ranking Table ---
        if ranked_items:
            # Determine which columns to show based on metric
            lines.append("### Complete Ranking\n")
            lines.append("| Rank | {dim} | Transactions | Volume Share | Amount (₹) | Amount Share | Avg (₹) | Success% | Fraud% | Gap to #1 (abs) | Gap to #1 (%) | Tier |".format(dim=dim_label))
            lines.append("|------|" + "------|" * 11)

            for item in ranked_items:
                m = item.get("metrics", {})
                gap = item.get("gap_to_rank_1", {})
                region_tag = ""
                if item.get("region"):
                    region_tag = f" [{item['region']}]"

                lines.append(
                    f"| {item['rank']} | **{item['label']}**{region_tag} "
                    f"| {m.get('total_transactions', 0):,} "
                    f"| {m.get('share_of_total_volume_pct', 0):.1f}% "
                    f"| ₹{m.get('total_amount', 0):,.0f} "
                    f"| {m.get('share_of_total_amount_pct', 0):.1f}% "
                    f"| ₹{m.get('avg_amount', 0):,.0f} "
                    f"| {m.get('success_rate_pct', 0):.1f}% "
                    f"| {m.get('fraud_rate_pct', 0):.2f}% "
                    f"| {gap.get('absolute', 0):,.0f} "
                    f"| {gap.get('pct', 0):.1f}% "
                    f"| {item.get('tier', '')} |"
                )
            lines.append("")

        # --- Regional Summary (if available) ---
        if regional_summary:
            lines.append("### 🗺️ Regional Grouping\n")
            lines.append("| Region | States | Total Transactions | Volume Share | Total Amount (₹) | Avg Success% | Avg Fraud% |")
            lines.append("|--------|--------|-------------------|-------------|------------------|-------------|-----------|")
            for region, info in sorted(regional_summary.items(), key=lambda x: x[1].get("total_transactions", 0), reverse=True):
                lines.append(
                    f"| **{region}** "
                    f"| {info.get('states_count', 0)} "
                    f"| {info.get('total_transactions', 0):,} "
                    f"| {info.get('volume_share_pct', 0):.1f}% "
                    f"| ₹{info.get('total_amount', 0):,.0f} "
                    f"| {info.get('avg_success_rate_pct', 0):.1f}% "
                    f"| {info.get('avg_fraud_rate_pct', 0):.2f}% |"
                )
            lines.append("")

            # Regional state breakdown
            lines.append("### 🏆 State Performance by Region\n")
            regions_with_states: Dict[str, list] = {}
            for item in ranked_items:
                region = item.get("region", "Other")
                regions_with_states.setdefault(region, []).append(item)
            for region in sorted(regions_with_states.keys()):
                states = regions_with_states[region]
                states_sorted = sorted(states, key=lambda x: x.get("regional_rank", 99))
                state_strs = []
                for s in states_sorted:
                    m = s.get("metrics", {})
                    state_strs.append(
                        f"  - **#{s.get('regional_rank', '?')} {s['label']}**: "
                        f"{m.get('total_transactions', 0):,} txns "
                        f"({s.get('regional_share_pct', s.get('state_performance_vs_region_pct', 0)):.1f}% of region)"
                    )
                lines.append(f"**{region}** ({len(states)} state{'s' if len(states) > 1 else ''}):")
                lines.extend(state_strs)
                lines.append("")

        # --- Gap Analysis ---
        if len(ranked_items) > 1:
            lines.append("### 📉 Gap Analysis from Rank #1\n")
            top = ranked_items[0]
            top_txns = top.get("metrics", {}).get("total_transactions", 0)
            for item in ranked_items[1:]:
                gap = item.get("gap_to_rank_1", {})
                gap_abs = gap.get("absolute", 0)
                gap_pct = gap.get("pct", 0)
                m = item.get("metrics", {})
                lines.append(
                    f"- **{item['label']}** (#{item['rank']}): "
                    f"{gap_abs:,.0f} fewer transactions ({gap_pct:.1f}% behind {top['label']})"
                )
            lines.append("")

        # --- Tier Summary ---
        if tier_summary:
            lines.append("### 🏅 Performance Tiers\n")
            for tier_name, info in tier_summary.items():
                lines.append(
                    f"- **{tier_name}**: {info.get('count', 0)} states, "
                    f"{info.get('combined_share_pct', 0):.1f}% combined share, "
                    f"avg {info.get('avg_metric_value', 0):,.0f} transactions"
                )
            lines.append("")

        # --- Pareto Insights ---
        if pareto:
            lines.append("### 📐 Concentration / Pareto Insights\n")
            conc = pareto.get("concentration_label", "")
            hhi = pareto.get("concentration_index", 0)
            p80 = pareto.get("top_80pct_threshold_rank")
            lines.append(f"- **Distribution**: {conc} (HHI: {hhi:.4f})")
            if p80:
                lines.append(f"- **80% threshold**: Top {p80} out of {total_unique} states account for ~80% of volume")
            pareto_stmt = summary.get("pareto_statement", "")
            if pareto_stmt:
                lines.append(f"- {pareto_stmt}")
            lines.append("")

        return "\n".join(lines)

    def _format_correlation_result(self, data: dict, question: str) -> str:
        """Format correlation_importance_tool results as detailed, structured markdown."""
        lines = []
        analysis_type = data.get("analysis_type", "")

        # Key finding always at the top
        kf = data.get("key_finding", "")
        if kf:
            lines.append(f"**💡 {kf}**")
            lines.append("")

        if analysis_type == "feature_importance":
            lines.append("## 📊 Feature Importance Ranking")
            lines.append(f"*Target: {data.get('target', 'failure')} | Records: {data.get('total_records', 0):,}*")
            lines.append("")
            ranked = data.get("ranked_features", [])
            if ranked:
                lines.append("| Rank | Feature | Cramér's V | Strength | Significant |")
                lines.append("|------|---------|-----------|----------|-------------|")
                for f in ranked:
                    sig = "✅" if f.get("significant") else "❌"
                    lines.append(
                        f"| {f.get('rank', '')} | **{f.get('feature', '')}** "
                        f"| {f.get('cramers_v', 0):.4f} | {f.get('strength', '')} | {sig} |"
                    )
                lines.append("")
            feat_summary = data.get("summary", {})
            if feat_summary.get("strong_predictors"):
                lines.append(f"**Strong predictors**: {', '.join(feat_summary['strong_predictors'])}")
            if feat_summary.get("moderate_predictors"):
                lines.append(f"**Moderate predictors**: {', '.join(feat_summary['moderate_predictors'])}")
            if feat_summary.get("weak_predictors"):
                lines.append(f"**Weak predictors**: {', '.join(feat_summary['weak_predictors'])}")

        elif analysis_type == "cramers_v_matrix":
            lines.append("## 📊 Cramér's V Association Matrix")
            lines.append("")
            top_assoc = data.get("top_associations", [])
            if top_assoc:
                lines.append("| Rank | Pair | Cramér's V | Strength |")
                lines.append("|------|------|-----------|----------|")
                for i, a in enumerate(top_assoc, 1):
                    pair_str = " × ".join(a.get("pair", []))
                    lines.append(f"| {i} | {pair_str} | {a.get('cramers_v', 0):.4f} | {a.get('strength', '')} |")
                lines.append("")

        elif analysis_type == "interaction_effects":
            lines.append(f"## 📊 Interaction Effects: {data.get('factor_a', '')} × {data.get('factor_b', '')}")
            lines.append(f"*Target: {data.get('target', '')} | Overall rate: {data.get('overall_rate', 0):.2f}%*")
            lines.append("")
            combos = data.get("combinations", [])
            if combos:
                lines.append(f"| {data.get('factor_a', 'Factor A')} | {data.get('factor_b', 'Factor B')} | Count | {data.get('target', 'Target')} Rate % | Interaction Effect | Rating |")
                lines.append("|------|------|-------|---------|-------------------|--------|")
                for c in combos:
                    lines.append(
                        f"| **{c.get('factor_a_value', '')}** | {c.get('factor_b_value', '')} "
                        f"| {c.get('count', 0):,} | {c.get('target_rate', 0):.2f}% "
                        f"| {c.get('interaction_effect', 0):+.2f}pp | {c.get('rating', '')} |"
                    )
                lines.append("")
            notable = data.get("notable_interactions", [])
            if notable:
                lines.append("### Notable Interactions")
                for n in notable:
                    lines.append(f"- {n}")
                lines.append("")

        elif analysis_type == "multivariate_combination":
            lines.append("## 📊 Multivariate Combination Analysis")
            lines.append(f"*Factors: {', '.join(data.get('factors', []))} | Target: {data.get('target', '')} | Baseline: {data.get('overall_baseline_rate', 0):.2f}%*")
            lines.append("")
            riskiest = data.get("riskiest_combinations", [])
            if riskiest:
                lines.append("### 🔴 Riskiest Combinations")
                lines.append("| Rank | Combination | Count | Rate % | vs Baseline | Risk Multiplier |")
                lines.append("|------|------------|-------|--------|-------------|-----------------|")
                for r in riskiest:
                    lines.append(
                        f"| {r.get('rank', '')} | **{r.get('combination_label', '')}** "
                        f"| {r.get('count', 0):,} | {r.get('target_rate', 0):.2f}% "
                        f"| {r.get('vs_baseline', 0):+.2f}pp | {r.get('risk_multiplier', 0):.2f}x |"
                    )
                lines.append("")
            safest = data.get("safest_combinations", [])
            if safest:
                lines.append("### 🟢 Safest Combinations")
                lines.append("| Rank | Combination | Count | Rate % | vs Baseline | Risk Multiplier |")
                lines.append("|------|------------|-------|--------|-------------|-----------------|")
                for s in safest:
                    lines.append(
                        f"| {s.get('rank', '')} | **{s.get('combination_label', '')}** "
                        f"| {s.get('count', 0):,} | {s.get('target_rate', 0):.2f}% "
                        f"| {s.get('vs_baseline', 0):+.2f}pp | {s.get('risk_multiplier', 0):.2f}x |"
                    )
                lines.append("")
            insights = data.get("pattern_insights", [])
            if insights:
                lines.append("### 💡 Pattern Insights")
                for ins in insights:
                    lines.append(f"- {ins}")
                lines.append("")

        elif analysis_type == "point_biserial":
            lines.append("## 📊 Point-Biserial Correlation")
            corr = data.get("correlation", {})
            lines.append(f"*{data.get('continuous_var', '')} vs {data.get('binary_target', '')} | Records: {data.get('total_records', 0):,}*")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Correlation (r) | **{corr.get('r', 0):.4f}** |")
            lines.append(f"| p-value | {corr.get('p_value', 0):.6f} |")
            lines.append(f"| Significant | {'✅' if corr.get('significant') else '❌'} |")
            lines.append(f"| Direction | {corr.get('direction', '')} |")
            lines.append(f"| Effect Size | {corr.get('effect_size', '')} |")
            lines.append(f"| Cohen's d | {data.get('cohens_d', 0):.4f} |")
            lines.append("")
            dists = data.get("group_distributions", {})
            if dists:
                lines.append("### Group Distributions")
                lines.append("| Group | Count | Mean (₹) | Median (₹) | Std |")
                lines.append("|-------|-------|----------|-----------|-----|")
                for group, d in dists.items():
                    lines.append(
                        f"| **{group.replace('_', ' ').title()}** "
                        f"| {d.get('count', 0):,} "
                        f"| ₹{d.get('mean', 0):,.2f} "
                        f"| ₹{d.get('median', 0):,.2f} "
                        f"| ₹{d.get('std', 0):,.2f} |"
                    )
                lines.append("")

        else:
            return self._format_deep_dict(data, question)

        return "\n".join(lines)

    def _format_date_query_result(self, data: dict, question: str) -> str:
        """Format date_query_tool results as detailed, structured markdown."""
        lines = []
        summary = data.get("summary", {})
        query_type = data.get("query_type", "")
        date_info = data.get("date_info", data.get("date_context", {}))

        # --- Header ---
        target_date = data.get("target_date", data.get("date", ""))
        if target_date:
            lines.append(f"## 📊 Transaction Analysis for {target_date}")
        else:
            lines.append("## 📊 Date-Based Transaction Analysis")
        lines.append("")

        # --- Key Finding ---
        kf = summary.get("key_finding", "")
        if kf:
            lines.append(f"**💡 Key Finding:** {kf}")
            lines.append("")

        # --- Overview metrics ---
        overview = data.get("overview", data.get("metrics", {}))
        if isinstance(overview, dict) and overview:
            lines.append("### 📈 Overview Metrics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            metric_labels = {
                "total_transactions": "Total Transactions",
                "total_amount": "Total Amount",
                "avg_amount": "Average Amount",
                "median_amount": "Median Amount",
                "max_amount": "Max Amount",
                "min_amount": "Min Amount",
                "success_rate": "Success Rate",
                "success_rate_pct": "Success Rate",
                "failure_rate": "Failure Rate",
                "failure_rate_pct": "Failure Rate",
                "fraud_rate": "Fraud Rate",
                "fraud_rate_pct": "Fraud Rate",
                "fraud_flagged": "Fraud Flagged",
                "pending_count": "Pending",
                "failed_count": "Failed",
                "success_count": "Successful",
                "unique_senders": "Unique Senders",
                "unique_receivers": "Unique Receivers",
            }
            for k, v in overview.items():
                label = metric_labels.get(k, k.replace("_", " ").title())
                if isinstance(v, float):
                    if "rate" in k or "pct" in k:
                        lines.append(f"| {label} | **{v:.2f}%** |")
                    elif "amount" in k:
                        lines.append(f"| {label} | **₹{v:,.2f}** |")
                    else:
                        lines.append(f"| {label} | **{v:,.2f}** |")
                elif isinstance(v, int):
                    if "amount" in k:
                        lines.append(f"| {label} | **₹{v:,}** |")
                    else:
                        lines.append(f"| {label} | **{v:,}** |")
                else:
                    lines.append(f"| {label} | **{v}** |")
            lines.append("")

        # --- Breakdown tables ---
        breakdowns = data.get("breakdowns", data.get("breakdown", {}))
        if isinstance(breakdowns, dict):
            for breakdown_name, breakdown_data in breakdowns.items():
                dim_label = breakdown_name.replace("_", " ").replace("by ", "").title()
                lines.append(f"### 📋 Breakdown by {dim_label}")
                lines.append("")

                if isinstance(breakdown_data, list) and breakdown_data:
                    # Build table from list of dicts
                    first = breakdown_data[0]
                    if isinstance(first, dict):
                        cols = list(first.keys())
                        # Format header
                        header_labels = [c.replace("_", " ").title() for c in cols]
                        lines.append("| " + " | ".join(header_labels) + " |")
                        lines.append("|" + "------|" * len(cols))
                        for row in breakdown_data:
                            cells = []
                            for c in cols:
                                v = row.get(c, "")
                                if isinstance(v, float):
                                    if "rate" in c or "pct" in c or "share" in c:
                                        cells.append(f"{v:.2f}%")
                                    elif "amount" in c:
                                        cells.append(f"₹{v:,.2f}")
                                    else:
                                        cells.append(f"{v:,.2f}")
                                elif isinstance(v, int):
                                    if "amount" in c:
                                        cells.append(f"₹{v:,}")
                                    else:
                                        cells.append(f"{v:,}")
                                else:
                                    cells.append(f"**{v}**" if c == cols[0] else str(v))
                            lines.append("| " + " | ".join(cells) + " |")
                        lines.append("")
                elif isinstance(breakdown_data, dict):
                    lines.append("| Category | Count |")
                    lines.append("|----------|-------|")
                    for k, v in sorted(breakdown_data.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
                        if isinstance(v, (int, float)):
                            lines.append(f"| **{k}** | {v:,} |")
                        else:
                            lines.append(f"| **{k}** | {v} |")
                    lines.append("")

        # --- Hourly breakdown ---
        hourly = data.get("hourly_breakdown", data.get("hourly_distribution", []))
        if isinstance(hourly, list) and hourly:
            lines.append("### ⏰ Hourly Distribution")
            lines.append("")
            lines.append("| Hour | Transactions | Amount (₹) |")
            lines.append("|------|-------------|------------|")
            for h in hourly:
                if isinstance(h, dict):
                    hour = h.get("hour", h.get("hour_of_day", ""))
                    count = h.get("count", h.get("transactions", h.get("total_transactions", 0)))
                    amount = h.get("amount", h.get("total_amount", ""))
                    amount_str = f"₹{amount:,.0f}" if isinstance(amount, (int, float)) else str(amount)
                    lines.append(f"| {hour}:00 | {count:,} | {amount_str} |")
            lines.append("")

        # --- Date context / comparison to peers ---
        if isinstance(date_info, dict) and date_info:
            lines.append("### 🔍 Date Context")
            lines.append("")
            for k, v in date_info.items():
                label = k.replace("_", " ").title()
                if isinstance(v, float):
                    lines.append(f"- **{label}**: {v:,.2f}")
                elif isinstance(v, int):
                    lines.append(f"- **{label}**: {v:,}")
                else:
                    lines.append(f"- **{label}**: {v}")
            lines.append("")

        # --- Peer comparison ---
        peer_comp = data.get("peer_comparison", data.get("comparison", {}))
        if isinstance(peer_comp, dict) and peer_comp:
            lines.append("### 📊 Comparison to Peers")
            lines.append("")
            for k, v in peer_comp.items():
                label = k.replace("_", " ").title()
                if isinstance(v, float):
                    lines.append(f"- **{label}**: {v:,.2f}")
                elif isinstance(v, int):
                    lines.append(f"- **{label}**: {v:,}")
                else:
                    lines.append(f"- **{label}**: {v}")
            lines.append("")

        # --- Additional summary fields ---
        for key in ["observation", "context", "recommendation", "insight", "pareto_statement", "comparison_note"]:
            val = summary.get(key, "")
            if val and val != "N/A":
                lines.append(f"💡 **{key.replace('_', ' ').title()}**: {val}")
                lines.append("")

        if len(lines) <= 3:
            # If we got almost nothing from structured extraction, dump all keys nicely
            return self._format_deep_dict(data, question)

        return "\n".join(lines)

    def _format_deep_dict(self, data: dict, question: str) -> str:
        """Recursively format a nested dict as readable markdown sections."""
        lines = []
        summary = data.get("summary", {})
        if isinstance(summary, dict):
            kf = summary.get("key_finding", "")
            if kf:
                lines.append(f"## 📊 Key Finding\n\n**{kf}**\n")

        def _render(obj, depth=0):
            prefix = "  " * depth
            rendered = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("success", "query_type", "tool"):
                        continue
                    label = k.replace("_", " ").title()
                    if isinstance(v, dict):
                        rendered.append(f"{prefix}**{label}:**")
                        rendered.extend(_render(v, depth + 1))
                    elif isinstance(v, list):
                        rendered.append(f"{prefix}**{label}:**")
                        rendered.extend(_render(v, depth + 1))
                    elif isinstance(v, float):
                        if "rate" in k or "pct" in k:
                            rendered.append(f"{prefix}- {label}: **{v:.2f}%**")
                        elif "amount" in k:
                            rendered.append(f"{prefix}- {label}: **₹{v:,.2f}**")
                        else:
                            rendered.append(f"{prefix}- {label}: **{v:,.2f}**")
                    elif isinstance(v, int):
                        if "amount" in k:
                            rendered.append(f"{prefix}- {label}: **₹{v:,}**")
                        else:
                            rendered.append(f"{prefix}- {label}: **{v:,}**")
                    else:
                        rendered.append(f"{prefix}- {label}: **{v}**")
            elif isinstance(obj, list):
                for i, item in enumerate(obj[:30]):
                    if isinstance(item, dict):
                        # Try to make a nice row
                        label = item.get("label", item.get("name", item.get("type", f"Item {i+1}")))
                        rendered.append(f"{prefix}- **{label}**")
                        for mk, mv in item.items():
                            if mk in ("label", "name", "type"):
                                continue
                            if isinstance(mv, dict):
                                rendered.extend(_render(mv, depth + 2))
                            elif isinstance(mv, float):
                                rendered.append(f"{prefix}  - {mk.replace('_',' ').title()}: {mv:,.2f}")
                            elif isinstance(mv, int):
                                rendered.append(f"{prefix}  - {mk.replace('_',' ').title()}: {mv:,}")
                            else:
                                rendered.append(f"{prefix}  - {mk.replace('_',' ').title()}: {mv}")
                    else:
                        rendered.append(f"{prefix}- {item}")
            return rendered

        lines.extend(_render(data))
        return "\n".join(lines) if lines else json.dumps(data, indent=2, default=str)[:5000]

    def _format_generic_result(self, data: dict, question: str) -> str:
        """Format any tool result as readable markdown (detailed fallback)."""
        # Detect tool type and route to specialized formatters
        query_type = data.get("query_type", "")
        if query_type or data.get("target_date") or data.get("date_info"):
            return self._format_date_query_result(data, question)

        # For other tools, use the deep dict formatter for comprehensive output
        return self._format_deep_dict(data, question)
    
    def _build_workflow(self):
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("understand_query", self.understand_query)
        workflow.add_node("create_plan", self.create_plan)
        workflow.add_node("analyze_data", self.analyze_data)
        workflow.add_node("generate_insights", self.generate_insights)
        
        # Add edges
        workflow.set_entry_point("understand_query")
        workflow.add_edge("understand_query", "create_plan")
        workflow.add_edge("create_plan", "analyze_data")
        workflow.add_edge("analyze_data", "generate_insights")
        workflow.add_edge("generate_insights", END)
        
        return workflow.compile()
    
    def understand_query(self, state: AgentState) -> AgentState:
        """Step 1: Understand the query"""
        print("\n🔍 Step 1: Understanding query...")
        self._emit_thought(1, "Understanding Query", "started",
                          f"Parsing: \"{state['question']}\"")
        
        try:
            history = "\n".join([
                f"Q: {msg['question']}\nA: {msg['response']}"
                for msg in state.get('conversation_history', [])[-3:]
            ])
            
            self._emit_thought(1, "Understanding Query", "detail",
                              "Sending query to LLM for intent classification & entity extraction...")
            
            query_plan = self.query_agent.understand_query(
                state['question'],
                history
            )
            
            state['query_plan'] = query_plan.model_dump()
            # Normalize filters & enrich from entities
            state['query_plan'] = self._normalize_and_enrich_filters(state['query_plan'], state['question'])
            print(f"✓ Query understood: Intent={query_plan.intent}")
            
            # Emit rich detail about what was understood
            entities_str = ", ".join(f"{k}: {v}" for k, v in query_plan.entities.items()) if query_plan.entities else "none"
            metrics_str = ", ".join(query_plan.metrics) if query_plan.metrics else "none"
            filters_str = ", ".join(f"{f.get('column','')} {f.get('operator','')} {f.get('value','')}" for f in query_plan.filters) if query_plan.filters else "none"
            tool_str = query_plan.suggested_tool or "auto-detect"
            
            self._emit_thought(1, "Understanding Query", "completed",
                              f"Intent: **{query_plan.intent}** | Suggested tool: **{tool_str}**",
                              metadata={
                                  "intent": query_plan.intent,
                                  "entities": entities_str,
                                  "metrics": metrics_str,
                                  "filters": filters_str,
                                  "is_followup": query_plan.is_followup,
                                  "suggested_tool": tool_str,
                              })
            
        except Exception as e:
            # LLM failed — use keyword-based fallback so the pipeline can continue
            print(f"  ⚠️ LLM query understanding failed: {e}")
            print(f"  🔄 Using keyword-based fallback...")
            fallback_plan = self._fallback_query_plan(state['question'])
            state['query_plan'] = fallback_plan
            state['error'] = ''  # Clear error so pipeline continues

            self._emit_thought(1, "Understanding Query", "completed",
                              f"Intent: **{fallback_plan['intent']}** (keyword fallback) | Tool: **{fallback_plan.get('suggested_tool', 'auto')}**",
                              metadata={
                                  "intent": fallback_plan['intent'],
                                  "suggested_tool": fallback_plan.get('suggested_tool', ''),
                                  "fallback": True,
                              })
        
        return state
    
    def create_plan(self, state: AgentState) -> AgentState:
        """Step 2: Create execution plan"""
        print("\n📋 Step 2: Creating execution plan...")
        self._emit_thought(2, "Planning Execution", "started",
                          "Converting query understanding into an actionable execution plan...")
        
        try:
            self._emit_thought(2, "Planning Execution", "detail",
                              "Determining filters, grouping, aggregations, and tool routing...")
            
            execution_plan = self.planner_agent.create_execution_plan(
                state['query_plan']
            )
            
            state['execution_plan'] = execution_plan.dict()
            # Ensure query_plan filters are not lost by the planner LLM
            qp_filters = state.get('query_plan', {}).get('filters', [])
            ep_filters = state['execution_plan'].get('filters', [])
            if qp_filters and not ep_filters:
                state['execution_plan']['filters'] = qp_filters
                print(f"  🔧 Restored {len(qp_filters)} filter(s) from query_plan (planner dropped them)")
            # Normalize execution_plan filters as well
            state['execution_plan'] = self._normalize_and_enrich_filters(state['execution_plan'], state['question'])
            print(f"✓ Execution plan created")
            print(f"  Filters: {len(execution_plan.filters)}")
            print(f"  Grouping: {execution_plan.groupby}")
            print(f"  Aggregations: {len(execution_plan.aggregations)}")
            
            # Emit rich detail about the plan
            tool_name = execution_plan.suggested_tool or "auto-select"
            subtype = execution_plan.tool_subtype or ""
            filters_detail = []
            for f in execution_plan.filters:
                col = f.get('column', '')
                op = f.get('operator', '')
                val = f.get('value', '')
                filters_detail.append(f"`{col}` {op} `{val}`")
            filters_str = ", ".join(filters_detail) if filters_detail else "none"
            groupby_str = ", ".join(execution_plan.groupby) if execution_plan.groupby else "none"
            
            self._emit_thought(2, "Planning Execution", "completed",
                              f"Tool: **{tool_name}**" + (f" ({subtype})" if subtype else "") + f" | Filters: {len(execution_plan.filters)} | Groups: {groupby_str}",
                              metadata={
                                  "tool": tool_name,
                                  "subtype": subtype,
                                  "filters": filters_str,
                                  "groupby": groupby_str,
                                  "aggregations": len(execution_plan.aggregations),
                              })
            
        except Exception as e:
            # LLM failed — build plan from query_plan using keyword heuristics
            print(f"  ⚠️ LLM planning failed: {e}")
            print(f"  🔄 Using keyword-based plan fallback...")
            fallback_plan = self._fallback_execution_plan(
                state.get('query_plan', {}), state['question']
            )
            state['execution_plan'] = fallback_plan
            state['error'] = ''  # Clear error so pipeline continues

            tool_name = fallback_plan.get("suggested_tool", "auto")
            subtype = fallback_plan.get("tool_subtype", "")
            self._emit_thought(2, "Planning Execution", "completed",
                              f"Tool: **{tool_name}**" + (f" ({subtype})" if subtype else "") + " (keyword fallback)",
                              metadata={
                                  "tool": tool_name,
                                  "subtype": subtype,
                                  "fallback": True,
                              })
        
        return state
    
    def analyze_data(self, state: AgentState) -> AgentState:
        """Step 3: Analyze data"""
        print("\n📊 Step 3: Analyzing data...")
        
        tool_name = state.get('execution_plan', {}).get('suggested_tool', 'auto')
        self._emit_thought(3, "Analyzing Data", "started",
                          f"Executing analysis using **{tool_name}**...")
        
        try:
            self._emit_thought(3, "Analyzing Data", "detail",
                              "Running tool against 250K+ transaction records...")
            
            # Inject original question so deterministic fallback can use keywords
            execution_plan = state.get('execution_plan', {})
            execution_plan['original_question'] = state['question']
            
            results = self.analyzer_agent.analyze(execution_plan)
            state['analysis_results'] = results
            print(f"✓ Analysis completed")
            
            # Emit details about what was returned
            tool_calls = results.get('tool_calls', 0)
            result_tools = [r.get('tool', 'unknown') for r in results.get('results', [])]
            tools_used = ", ".join(result_tools) if result_tools else "direct response"
            
            self._emit_thought(3, "Analyzing Data", "completed",
                              f"Executed **{tool_calls}** tool call(s): {tools_used}",
                              metadata={
                                  "tool_calls": tool_calls,
                                  "tools_used": tools_used,
                              })
            
        except Exception as e:
            state['error'] = f"Analysis failed: {str(e)}"
            print(f"✗ Error: {state['error']}")
            self._emit_thought(3, "Analyzing Data", "error", str(e))
        
        return state
    
    def generate_insights(self, state: AgentState) -> AgentState:
        """Step 4: Generate insights"""
        print("\n💡 Step 4: Generating insights...")
        self._emit_thought(4, "Generating Insights", "started",
                          "Synthesizing analysis results into human-readable insights...")
        
        # If analysis produced an error and no results, surface the error
        if state.get('error') and not state.get('analysis_results'):
            state['final_response'] = (
                f"⚠️ Analysis could not be completed: {state['error']}\n\n"
                "Please try rephrasing your question."
            )
            print(f"✗ Skipping insight generation — prior error: {state['error']}")
            self._emit_thought(4, "Generating Insights", "error",
                              f"Skipped — prior error: {state['error']}")
            return state
        
        try:
            self._emit_thought(4, "Generating Insights", "detail",
                              "Sending raw data to LLM for narrative generation...")
            
            # Retry up to 2 times on transient LLM failures (rate limits, timeouts)
            last_error = None
            for attempt in range(3):
                try:
                    insights = self.insight_agent.generate_insights(
                        state['question'],
                        state['analysis_results']
                    )
                    state['final_response'] = insights
                    print(f"✓ Insights generated (attempt {attempt + 1})")
                    self._emit_thought(4, "Generating Insights", "completed",
                                      "Final response ready")
                    last_error = None
                    break
                except Exception as retry_err:
                    last_error = retry_err
                    print(f"  ⚠️ LLM attempt {attempt + 1} failed: {retry_err}")
                    if attempt < 2:
                        import time as _time
                        _time.sleep(2 * (attempt + 1))  # Back off: 2s, 4s
            
            if last_error:
                raise last_error
            
        except Exception as e:
            # LLM insight generation failed — try local formatting
            print(f"  ⚠️ LLM insight generation failed: {e}")
            print(f"  🔄 Using local result formatter...")
            local_response = self._format_results_locally(
                state['question'], state.get('analysis_results', {})
            )
            state['final_response'] = local_response
            state['error'] = ''
            print(f"✓ Local formatting produced {len(local_response)} chars")
            self._emit_thought(4, "Generating Insights", "completed",
                              "Formatted results locally (LLM unavailable)")
        
        return state
    
    def run(self, question: str, conversation_history: list = None) -> str:
        """Run the complete workflow"""
        self._thinking_callback = None  # Reset callback for plain runs
        return self._execute(question, conversation_history)
    
    def run_with_thinking(self, question: str, conversation_history: list = None,
                          thinking_callback: Callable = None) -> str:
        """Run the complete workflow with a thinking callback for UI updates.
        
        The callback receives dicts with keys:
          step (int), title (str), status (str), detail (str), metadata (dict)
        """
        self._thinking_callback = thinking_callback
        try:
            return self._execute(question, conversation_history)
        finally:
            self._thinking_callback = None
    
    def _execute(self, question: str, conversation_history: list = None) -> str:
        """Internal: run the LangGraph workflow."""
        initial_state = {
            "question": question,
            "conversation_history": conversation_history or [],
            "query_plan": {},
            "execution_plan": {},
            "analysis_results": {},
            "final_response": "",
            "error": ""
        }
        
        print(f"\n{'='*60}")
        print(f"💬 Question: {question}")
        print(f"{'='*60}")
        
        final_state = self.workflow.invoke(initial_state)
        
        if final_state.get('error'):
            print(f"\n⚠️ Workflow completed with errors")
        else:
            print(f"\n✅ Workflow completed successfully")
        
        return final_state['final_response']