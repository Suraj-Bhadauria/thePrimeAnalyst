# WHAT DOES THIS AGENT DO?
# - this file takes the user query and sends it to llm to get structured data
# - converting vague user query into structured data
# - then agents will work on this structured data 
# - the better we can convert user query to structured data, the more accurate analysis we can get 
# - prompt used : QUERY_UNDERSTANDING_PROMPT 

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from src.config import config
from src.utils.prompts import QUERY_UNDERSTANDING_PROMPT
import json
import re
import logging

logger = logging.getLogger(__name__)

# --- Valid intent types ---
VALID_INTENTS = {
    "descriptive", "comparative", "temporal", "segmentation",
    "correlation", "risk_analysis", "trend", "date_query",
    "network_analysis", "drill_down",
}

# Map common LLM hallucinated intent strings to nearest valid intent
_INTENT_ALIAS_MAP = {
    "analysis": "descriptive",
    "graph": "network_analysis",
    "graph_query": "network_analysis",
    "p2p": "network_analysis",
    "network": "network_analysis",
    "retrieve": "drill_down",
    "lookup": "drill_down",
    "resolve": "drill_down",
    "time": "temporal",
    "time_series": "temporal",
    "date": "date_query",
    "calendar": "date_query",
}

# Valid suggested_tool names
VALID_TOOLS = {
    "query_transaction_data", "multi_metric_tool", "comparison_tool",
    "time_analysis_tool", "ranking_tool", "statistical_analysis",
    "trend_tool", "date_query_tool", "network_graph_tool",
    "transaction_resolver_tool",
}


class QueryPlan(BaseModel):
    intent: str = Field(description="Type of query intent")
    entities: Dict[str, Any] = Field(description="Extracted entities")
    metrics: List[str] = Field(description="Metrics to calculate")
    filters: List[Dict] = Field(description="Filter conditions")
    grouping: List[str] = Field(description="Grouping dimensions")
    is_followup: bool = Field(description="Whether this is a follow-up question")
    suggested_tool: Optional[str] = Field(default=None, description="Suggested downstream tool name")

    @field_validator("intent", mode="before")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        cleaned = str(v).strip().lower()
        if cleaned in VALID_INTENTS:
            return cleaned
        if cleaned in _INTENT_ALIAS_MAP:
            mapped = _INTENT_ALIAS_MAP[cleaned]
            logger.warning("Intent '%s' mapped to '%s' via alias table", v, mapped)
            return mapped
        logger.warning("Unrecognised intent '%s' defaulted to 'descriptive'", v)
        return "descriptive"

    @field_validator("suggested_tool", mode="before")
    @classmethod
    def validate_suggested_tool(cls, v):
        if v is None:
            return None
        cleaned = str(v).strip().lower()
        if cleaned in VALID_TOOLS:
            return cleaned
        logger.warning("Unrecognised suggested_tool '%s' — cleared to None", v)
        return None


class QueryUnderstandingAgent:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        )
        self.parser = PydanticOutputParser(pydantic_object=QueryPlan)

    # ------------------------------------------------------------------
    # Heuristic intent detection from question text (last-resort fallback)
    # ------------------------------------------------------------------
    @staticmethod
    def _heuristic_intent(question: str) -> str:
        q = question.lower()
        # network_analysis keywords
        if any(kw in q for kw in ["p2p network", "money mule", "round trip", "round-trip",
                                   "cycle", "pagerank", "page rank", "graph", "hub node",
                                   "circular transaction", "communities"]):
            return "network_analysis"
        # drill_down keywords
        if any(kw in q for kw in ["transaction id", "transaction ids", "show me the transactions",
                                   "give me the records", "actual transactions", "raw records",
                                   "list the transactions", "show me proof"]):
            return "drill_down"
        # date_query keywords — specific dates / month names / 4-digit year
        month_names = ["january", "february", "march", "april", "may", "june",
                       "july", "august", "september", "october", "november", "december"]
        if re.search(r"\b20\d{2}\b", q) or any(m in q for m in month_names):
            return "date_query"
        # trend keywords — check BEFORE segmentation so volatility phrases
        # like "most unstable" are not captured by the "most " segmentation keyword
        if any(kw in q for kw in ["trend", "over time", "increasing", "decreasing",
                                   "rising", "falling", "trajectory", "moving average",
                                   "getting worse", "getting better", "forecast",
                                   "accelerat", "decelerat", "momentum",
                                   "rate of change", "speeding up", "slowing down",
                                   "volatil", "unstable", "instabil", "stability",
                                   "stable", "fluctuat", "variabil"]):
            return "trend"
        # segmentation / ranking keywords
        if any(kw in q for kw in ["rank", "top ", "bottom ", "most ", "least ",
                                   "highest", "lowest", "best ", "worst ",
                                   "leading", "leaderboard", "pareto",
                                   "share of", "dominant", "popular",
                                   "which state", "which bank", "which category",
                                   "rank all", "rank by", "ranked"]):
            return "segmentation"
        # comparative keywords
        if any(kw in q for kw in ["compare", " vs ", "versus", "difference between",
                                   "better than", "worse than", "android vs",
                                   "ios vs", "compared to"]):
            return "comparative"
        # (trend already checked above segmentation)
        # temporal keywords
        if any(kw in q for kw in ["peak hour", "busiest hour", "busiest day",
                                   "hourly", "weekend vs weekday", "time of day",
                                   "day of week"]):
            return "temporal"
        # multi-metric / overview keywords
        if any(kw in q for kw in ["overall", "complete picture", "health check",
                                   "all metrics", "full snapshot", "scorecard",
                                   "dashboard", "performance overview"]):
            return "descriptive"  # will be upgraded to multi_metric by planner
        return "descriptive"

    @staticmethod
    def _heuristic_suggested_tool(intent: str) -> Optional[str]:
        mapping = {
            "network_analysis": "network_graph_tool",
            "drill_down": "transaction_resolver_tool",
            "date_query": "date_query_tool",
            "temporal": "time_analysis_tool",
            "trend": "trend_tool",
            "comparative": "comparison_tool",
            "segmentation": "ranking_tool",
            "correlation": "statistical_analysis",
            "risk_analysis": "statistical_analysis",
            "descriptive": "query_transaction_data",
        }
        return mapping.get(intent)

    # ------------------------------------------------------------------
    # Partial field recovery from malformed LLM response
    # ------------------------------------------------------------------
    @staticmethod
    def _try_partial_recovery(raw: str, question: str) -> Optional[QueryPlan]:
        """Try to recover individual fields from a malformed JSON response."""
        recovered: Dict[str, Any] = {}
        recovered_fields: list[str] = []
        defaulted_fields: list[str] = []

        # --- intent ---
        intent_match = re.search(r'"intent"\s*:\s*"([^"]+)"', raw)
        if intent_match:
            recovered["intent"] = intent_match.group(1)
            recovered_fields.append("intent")
        else:
            recovered["intent"] = QueryUnderstandingAgent._heuristic_intent(question)
            defaulted_fields.append("intent")

        # --- entities ---
        entities_match = re.search(r'"entities"\s*:\s*(\{[^}]*\})', raw)
        if entities_match:
            try:
                recovered["entities"] = json.loads(entities_match.group(1))
                recovered_fields.append("entities")
            except json.JSONDecodeError:
                recovered["entities"] = {}
                defaulted_fields.append("entities")
        else:
            recovered["entities"] = {}
            defaulted_fields.append("entities")

        # --- metrics ---
        metrics_match = re.search(r'"metrics"\s*:\s*(\[[^\]]*\])', raw)
        if metrics_match:
            try:
                recovered["metrics"] = json.loads(metrics_match.group(1))
                recovered_fields.append("metrics")
            except json.JSONDecodeError:
                recovered["metrics"] = ["count"]
                defaulted_fields.append("metrics")
        else:
            recovered["metrics"] = ["count"]
            defaulted_fields.append("metrics")

        # --- filters ---
        filters_match = re.search(r'"filters"\s*:\s*(\[[^\]]*\])', raw)
        if filters_match:
            try:
                recovered["filters"] = json.loads(filters_match.group(1))
                recovered_fields.append("filters")
            except json.JSONDecodeError:
                recovered["filters"] = []
                defaulted_fields.append("filters")
        else:
            recovered["filters"] = []
            defaulted_fields.append("filters")

        # --- grouping ---
        grouping_match = re.search(r'"grouping"\s*:\s*(\[[^\]]*\])', raw)
        if grouping_match:
            try:
                recovered["grouping"] = json.loads(grouping_match.group(1))
                recovered_fields.append("grouping")
            except json.JSONDecodeError:
                recovered["grouping"] = []
                defaulted_fields.append("grouping")
        else:
            recovered["grouping"] = []
            defaulted_fields.append("grouping")

        # --- is_followup ---
        followup_match = re.search(r'"is_followup"\s*:\s*(true|false)', raw, re.IGNORECASE)
        if followup_match:
            recovered["is_followup"] = followup_match.group(1).lower() == "true"
            recovered_fields.append("is_followup")
        else:
            recovered["is_followup"] = False
            defaulted_fields.append("is_followup")

        # --- suggested_tool ---
        tool_match = re.search(r'"suggested_tool"\s*:\s*"([^"]+)"', raw)
        if tool_match:
            recovered["suggested_tool"] = tool_match.group(1)
            recovered_fields.append("suggested_tool")
        else:
            recovered["suggested_tool"] = QueryUnderstandingAgent._heuristic_suggested_tool(
                recovered["intent"]
            )
            defaulted_fields.append("suggested_tool")

        # Only count as partial recovery if at least intent was recovered
        if not recovered_fields:
            return None

        logger.info(
            "Partial recovery succeeded — recovered: %s, defaulted: %s",
            recovered_fields, defaulted_fields,
        )
        try:
            return QueryPlan(**recovered)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Post-LLM intent correction — safety net for known misclassifications
    # ------------------------------------------------------------------
    @staticmethod
    def _post_llm_intent_correction(plan: 'QueryPlan', question: str) -> 'QueryPlan':
        """Override LLM intent when keywords strongly indicate a different intent.

        The LLM sometimes classifies volatility / stability questions as
        'segmentation' because phrases like 'most unstable' match the
        segmentation pattern.  This method corrects that.
        """
        q = question.lower()
        volatility_kws = ["volatil", "unstable", "instabil", "stability",
                          "stable", "fluctuat", "variabil"]
        if plan.intent != "trend" and any(kw in q for kw in volatility_kws):
            logger.info(
                "Post-LLM correction: intent '%s' → 'trend' (volatility keywords detected)",
                plan.intent,
            )
            plan.intent = "trend"
            plan.suggested_tool = "trend_tool"
        return plan

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def understand_query(self, question: str, history: str = "") -> QueryPlan:
        """Understand user query and extract structured information"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_UNDERSTANDING_PROMPT),
            ("human", "User Question: {question}"),
            ("human", "Conversation History: {history}"),
            ("system", "{format_instructions}")
        ])

        chain = prompt | self.llm

        response = chain.invoke({
            "question": question,
            "history": history,
            "format_instructions": self.parser.get_format_instructions()
        })

        raw_content = response.content

        # ---- Step 1: attempt full JSON parse ----
        try:
            content = raw_content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            plan = QueryPlan(**parsed)
            return self._post_llm_intent_correction(plan, question)
        except Exception as e:
            logger.warning("Full JSON parse failed: %s", e)

        # ---- Step 2: attempt partial field recovery ----
        partial = self._try_partial_recovery(raw_content, question)
        if partial is not None:
            logger.info("Returning partially recovered QueryPlan (intent=%s)", partial.intent)
            return self._post_llm_intent_correction(partial, question)

        # ---- Step 3: full-failure fallback with heuristic intent ----
        logger.warning(
            "Complete parse failure — falling back to heuristic. Raw response: %s",
            raw_content[:500],
        )
        fallback_intent = self._heuristic_intent(question)
        return QueryPlan(
            intent=fallback_intent,
            entities={},
            metrics=["count"],
            filters=[],
            grouping=[],
            is_followup=False,
            suggested_tool=self._heuristic_suggested_tool(fallback_intent),
        )