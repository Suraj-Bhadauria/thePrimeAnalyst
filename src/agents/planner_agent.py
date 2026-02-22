# WHAT DOES THIS AGENT DO?
# - takes the structured query from query_agent and make a plan to follow 
# - prompt used : PLANNER_PROMPT

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
import re
from src.config import config
from src.utils.prompts import PLANNER_PROMPT

# ---------- Valid schema constants for semantic validation ----------

VALID_COLUMNS = {
    "transaction_id", "timestamp", "transaction_type", "merchant_category",
    "amount_inr", "transaction_status", "sender_age_group", "receiver_age_group",
    "sender_state", "sender_bank", "receiver_bank", "device_type",
    "network_type", "fraud_flag", "hour_of_day", "day_of_week", "is_weekend",
}

# Common LLM mistakes → correct column names
COLUMN_CORRECTION_MAP = {
    "transaction_date": "timestamp",
    "date": "timestamp",
    "datetime": "timestamp",
    "time": "timestamp",
    "age_group": "sender_age_group",
    "state": "sender_state",
    "bank": "sender_bank",
    "amount": "amount_inr",
    "status": "transaction_status",
    "type": "transaction_type",
    "category": "merchant_category",
    "device": "device_type",
    "network": "network_type",
    "fraud": "fraud_flag",
    "weekend": "is_weekend",
    "hour": "hour_of_day",
    "day": "day_of_week",
    "sender_device_type": "device_type",
    "receiver_device_type": "device_type",
    "merchant": "merchant_category",
    "sender_network_type": "network_type",
}

VALID_OPERATORS = {"==", "!=", ">", "<", ">=", "<=", "in"}

OPERATOR_CORRECTION_MAP = {
    "=": "==",
    "equals": "==",
    "equal": "==",
    "eq": "==",
    "ne": "!=",
    "not_equal": "!=",
    "not_equals": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "contains": "in",
    "not in": "!=",
}

INTENT_TO_TOOL_MAP = {
    "descriptive": "query_transaction_data",
    "comparative": "comparison_tool",
    "temporal": "time_analysis_tool",
    "segmentation": "ranking_tool",
    "correlation": "statistical_analysis",
    "risk_analysis": "statistical_analysis",
    "trend": "trend_tool",
    "date_query": "date_query_tool",
    "network_analysis": "network_graph_tool",
    "drill_down": "transaction_resolver_tool",
}


class ExecutionPlan(BaseModel):
    # ── Original 6 fields (unchanged) ──────────────────────────────
    filters: List[Dict] = Field(default_factory=list)
    groupby: List[str] = Field(default_factory=list)
    aggregations: List[Dict] = Field(default_factory=list)
    computations: List[Dict] = Field(default_factory=list)
    sort: Optional[Dict] = None
    limit: Optional[int] = None

    # ── Routing signal fields ──────────────────────────────────────
    suggested_tool: Optional[str] = None
    analysis_intent: Optional[str] = None

    # ── Tool subtype ───────────────────────────────────────────────
    tool_subtype: Optional[str] = None

    # ── Comparison-specific fields ─────────────────────────────────
    segment_column: Optional[str] = None
    segment_a: Optional[str] = None
    segment_b: Optional[str] = None

    # ── Temporal / trend fields ────────────────────────────────────
    metric: Optional[str] = None
    time_granularity: Optional[str] = None
    smoothing_window: Optional[int] = None

    # ── Date-specific fields ───────────────────────────────────────
    date_reference: Optional[str] = None
    date_query_subtype: Optional[str] = None

    # ── Network graph fields ───────────────────────────────────────
    graph_metric: Optional[str] = None
    time_window_hours: Optional[int] = None

    # ── Drill-down / resolver fields ───────────────────────────────
    is_chained_resolver: Optional[bool] = None
    resolver_description: Optional[str] = None


class PlannerAgent:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        )

    # ----------------------------------------------------------------
    #  PUBLIC METHOD — unchanged signature
    # ----------------------------------------------------------------
    def create_execution_plan(self, query_plan: dict) -> ExecutionPlan:
        """Create execution plan from query understanding"""

        prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
        chain = prompt | self.llm

        response = chain.invoke({
            "query_plan": json.dumps(query_plan, indent=2)
        })

        plan = self._parse_response(response.content, query_plan)
        plan = self._validate_plan(plan, query_plan)
        self._assess_plan_quality(plan)
        return plan

    # ----------------------------------------------------------------
    #  PARSE — multi-step recovery
    # ----------------------------------------------------------------
    def _parse_response(self, raw: str, query_plan: dict) -> ExecutionPlan:
        """Parse LLM response with multi-step fallback."""

        # --- Step 1: full JSON parse ---
        try:
            content = self._extract_json_block(raw)
            parsed = json.loads(content)
            return ExecutionPlan(**parsed)
        except Exception as e:
            print(f"[PlannerAgent] Full JSON parse failed: {e}")

        # --- Step 2: partial field recovery from raw string ---
        recovered: Dict = {}
        try:
            # Try to recover suggested_tool
            tool_match = re.search(r'"suggested_tool"\s*:\s*"([^"]+)"', raw)
            if tool_match:
                recovered["suggested_tool"] = tool_match.group(1)

            # Try to recover analysis_intent
            intent_match = re.search(r'"analysis_intent"\s*:\s*"([^"]+)"', raw)
            if intent_match:
                recovered["analysis_intent"] = intent_match.group(1)

            # Try to recover filters array
            filters_match = re.search(r'"filters"\s*:\s*(\[.*?\])', raw, re.DOTALL)
            if filters_match:
                try:
                    recovered["filters"] = json.loads(filters_match.group(1))
                except Exception:
                    pass

            # Try to recover date_reference
            date_ref_match = re.search(r'"date_reference"\s*:\s*"([^"]+)"', raw)
            if date_ref_match:
                recovered["date_reference"] = date_ref_match.group(1)

            # Try to recover tool_subtype
            subtype_match = re.search(r'"tool_subtype"\s*:\s*"([^"]+)"', raw)
            if subtype_match:
                recovered["tool_subtype"] = subtype_match.group(1)

            # Try to recover graph_metric
            graph_match = re.search(r'"graph_metric"\s*:\s*"([^"]+)"', raw)
            if graph_match:
                recovered["graph_metric"] = graph_match.group(1)

            # Try to recover metric
            metric_match = re.search(r'"metric"\s*:\s*"([^"]+)"', raw)
            if metric_match:
                recovered["metric"] = metric_match.group(1)
        except Exception:
            pass

        # --- Step 3: if we recovered routing signals, build partial plan ---
        if recovered.get("suggested_tool") or recovered.get("analysis_intent"):
            print(f"[PlannerAgent] Partial recovery succeeded — recovered fields: {list(recovered.keys())}")
            try:
                return ExecutionPlan(**recovered)
            except Exception:
                pass

        # --- Step 4: absolute fallback — preserve routing from query_plan ---
        print("[PlannerAgent] Full fallback — preserving routing from query_plan input")
        fallback_tool = query_plan.get("suggested_tool")
        fallback_intent = query_plan.get("intent")
        if not fallback_tool and fallback_intent:
            fallback_tool = INTENT_TO_TOOL_MAP.get(fallback_intent)

        # Also try to carry forward key entities from query_plan
        entities = query_plan.get("entities", {}) or {}
        fallback_kwargs: Dict = {
            "suggested_tool": fallback_tool,
            "analysis_intent": fallback_intent,
        }
        if entities.get("date_reference"):
            fallback_kwargs["date_reference"] = entities["date_reference"]
        if entities.get("graph_metric"):
            fallback_kwargs["graph_metric"] = entities["graph_metric"]
        if entities.get("is_chained_resolver") is not None:
            fallback_kwargs["is_chained_resolver"] = entities["is_chained_resolver"]
        if entities.get("target_segment_description"):
            fallback_kwargs["resolver_description"] = entities["target_segment_description"]
        if entities.get("time_granularity"):
            fallback_kwargs["time_granularity"] = entities["time_granularity"]

        return ExecutionPlan(**fallback_kwargs)

    # ----------------------------------------------------------------
    #  VALIDATE — semantic checks + corrections
    # ----------------------------------------------------------------
    def _validate_plan(self, plan: ExecutionPlan, query_plan: dict) -> ExecutionPlan:
        """Semantic validation: fix common LLM mistakes before returning."""

        corrections: List[str] = []

        # --- Ensure routing signals are never lost ---
        if not plan.suggested_tool:
            incoming_tool = query_plan.get("suggested_tool")
            if incoming_tool:
                plan.suggested_tool = incoming_tool
                corrections.append(f"Restored suggested_tool from query_plan: {incoming_tool}")
            else:
                intent = plan.analysis_intent or query_plan.get("intent")
                if intent and intent in INTENT_TO_TOOL_MAP:
                    plan.suggested_tool = INTENT_TO_TOOL_MAP[intent]
                    corrections.append(f"Inferred suggested_tool from intent '{intent}': {plan.suggested_tool}")

        if not plan.analysis_intent:
            incoming_intent = query_plan.get("intent")
            if incoming_intent:
                plan.analysis_intent = incoming_intent
                corrections.append(f"Restored analysis_intent from query_plan: {incoming_intent}")

        # --- Column name validation & correction ---
        # Filters
        for f in plan.filters:
            col = f.get("column", "")
            if col and col not in VALID_COLUMNS:
                corrected = COLUMN_CORRECTION_MAP.get(col.lower())
                if corrected:
                    corrections.append(f"Filter column corrected: '{col}' → '{corrected}'")
                    f["column"] = corrected

        # Groupby
        corrected_groupby = []
        for col in plan.groupby:
            if col in VALID_COLUMNS:
                corrected_groupby.append(col)
            else:
                corrected = COLUMN_CORRECTION_MAP.get(col.lower())
                if corrected:
                    corrections.append(f"Groupby column corrected: '{col}' → '{corrected}'")
                    corrected_groupby.append(corrected)
                else:
                    corrections.append(f"Groupby column removed (invalid): '{col}'")
        plan.groupby = corrected_groupby

        # Aggregations
        for agg in plan.aggregations:
            col = agg.get("column", "")
            if col and col not in VALID_COLUMNS and col != "*":
                corrected = COLUMN_CORRECTION_MAP.get(col.lower())
                if corrected:
                    corrections.append(f"Aggregation column corrected: '{col}' → '{corrected}'")
                    agg["column"] = corrected

        # --- Operator validation ---
        for f in plan.filters:
            op = f.get("operator", "")
            if op and op not in VALID_OPERATORS:
                corrected = OPERATOR_CORRECTION_MAP.get(op.lower())
                if corrected:
                    corrections.append(f"Filter operator corrected: '{op}' → '{corrected}'")
                    f["operator"] = corrected
                else:
                    corrections.append(f"Filter operator unknown: '{op}' — defaulting to '=='")
                    f["operator"] = "=="

        # --- Sort reference validation ---
        if plan.sort and plan.sort.get("by"):
            sort_col = plan.sort["by"]
            agg_aliases = {a.get("alias", "") for a in plan.aggregations if a.get("alias")}
            comp_names = {c.get("name", "") for c in plan.computations if c.get("name")}
            valid_refs = VALID_COLUMNS | agg_aliases | comp_names
            if sort_col not in valid_refs:
                # Try column correction first
                corrected = COLUMN_CORRECTION_MAP.get(sort_col.lower())
                if corrected and corrected in VALID_COLUMNS:
                    corrections.append(f"Sort column corrected: '{sort_col}' → '{corrected}'")
                    plan.sort["by"] = corrected
                else:
                    corrections.append(f"Sort reference removed (invalid): '{sort_col}'")
                    plan.sort = None

        # --- Limit sanity check ---
        if plan.limit is not None:
            if plan.limit <= 0 or plan.limit > 10000:
                corrections.append(f"Limit sanitized: {plan.limit} → None")
                plan.limit = None

        # --- Intent-specific presence checks ---
        if plan.analysis_intent == "date_query" and not plan.date_reference:
            # Try to recover from query_plan entities
            entities = query_plan.get("entities", {}) or {}
            if entities.get("date_reference"):
                plan.date_reference = entities["date_reference"]
                corrections.append(f"Restored date_reference from query_plan entities: {plan.date_reference}")
            else:
                print("[PlannerAgent] WARNING: date_query plan has no date_reference — date_query_tool will likely fail")

        if plan.analysis_intent == "network_analysis" and not plan.graph_metric:
            entities = query_plan.get("entities", {}) or {}
            if entities.get("graph_metric"):
                plan.graph_metric = entities["graph_metric"]
                corrections.append(f"Restored graph_metric from query_plan entities: {plan.graph_metric}")
            else:
                plan.graph_metric = "overview"
                corrections.append("Defaulted graph_metric to 'overview'")

        if plan.analysis_intent == "drill_down":
            if plan.tool_subtype is None:
                entities = query_plan.get("entities", {}) or {}
                if entities.get("is_chained_resolver"):
                    plan.tool_subtype = "context_aware_resolver"
                else:
                    plan.tool_subtype = "criteria_based"
                corrections.append(f"Defaulted drill_down tool_subtype to '{plan.tool_subtype}'")
            if plan.is_chained_resolver is None:
                entities = query_plan.get("entities", {}) or {}
                plan.is_chained_resolver = bool(entities.get("is_chained_resolver", False))
                corrections.append(f"Defaulted is_chained_resolver to {plan.is_chained_resolver}")

        if corrections:
            print(f"[PlannerAgent] Semantic corrections applied ({len(corrections)}):")
            for c in corrections:
                print(f"  • {c}")

        return plan

    # ----------------------------------------------------------------
    #  PLAN QUALITY ASSESSMENT
    # ----------------------------------------------------------------
    def _assess_plan_quality(self, plan: ExecutionPlan) -> None:
        """Log plan completeness for debugging."""

        routing_fields = {
            "suggested_tool": plan.suggested_tool,
            "analysis_intent": plan.analysis_intent,
        }
        optional_fields = {
            "tool_subtype": plan.tool_subtype,
            "segment_column": plan.segment_column,
            "segment_a": plan.segment_a,
            "segment_b": plan.segment_b,
            "metric": plan.metric,
            "time_granularity": plan.time_granularity,
            "smoothing_window": plan.smoothing_window,
            "date_reference": plan.date_reference,
            "date_query_subtype": plan.date_query_subtype,
            "graph_metric": plan.graph_metric,
            "time_window_hours": plan.time_window_hours,
            "is_chained_resolver": plan.is_chained_resolver,
            "resolver_description": plan.resolver_description,
        }

        populated = [k for k, v in optional_fields.items() if v is not None]
        empty = [k for k, v in optional_fields.items() if v is None]

        print(f"[PlannerAgent] Plan quality — intent: {plan.analysis_intent}, tool: {plan.suggested_tool}")
        print(f"  Populated optional fields ({len(populated)}): {populated}")

        # Intent-specific completeness warnings
        intent = plan.analysis_intent
        warnings: List[str] = []

        if not plan.suggested_tool:
            warnings.append("suggested_tool is missing — AnalyzerAgent will have to guess tool")
        if not plan.analysis_intent:
            warnings.append("analysis_intent is missing — AnalyzerAgent has no intent signal")

        if intent == "date_query" and not plan.date_reference:
            warnings.append("date_query without date_reference — tool will fail")
        if intent == "network_analysis" and not plan.graph_metric:
            warnings.append("network_analysis without graph_metric — tool will default")
        if intent == "comparative" and not plan.segment_column:
            warnings.append("comparative without segment_column — comparison target unknown")
        if intent == "drill_down" and plan.is_chained_resolver is None:
            warnings.append("drill_down without is_chained_resolver — resolver mode ambiguous")
        if intent == "trend" and not plan.metric:
            warnings.append("trend without metric — trend_tool will default to volume")
        if intent == "temporal" and not plan.time_granularity:
            warnings.append("temporal without time_granularity — time tool will guess")

        if warnings:
            print(f"  ⚠ Completeness warnings ({len(warnings)}):")
            for w in warnings:
                print(f"    - {w}")
        else:
            print(f"  ✓ Plan appears complete for intent '{intent}'")

    # ----------------------------------------------------------------
    #  HELPERS
    # ----------------------------------------------------------------
    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extract JSON from a possibly markdown-wrapped LLM response."""
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        if "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()