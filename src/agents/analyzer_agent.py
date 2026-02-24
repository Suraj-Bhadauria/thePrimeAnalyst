# Fixed: Now actually executes tools instead of just binding them
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.config import config
from src.tools.data_tools import create_data_query_tool
from src.tools.stats_tools import create_stats_tool
from src.tools.time_analysis_tool import create_time_analysis_tool
from src.tools.comparison_tool import create_comparison_tool
from src.tools.ranking_tool import create_ranking_tool
from src.tools.multi_metric_tool import create_multi_metric_tool
from src.tools.trend_tool import create_trend_tool
from src.tools.network_graph_tool import create_network_graph_tool
from src.tools.transaction_resolver_tool import create_transaction_resolver_tool
from src.tools.date_query_tool import create_date_query_tool
from src.tools.correlation_tool import create_correlation_tool
import json

class AnalyzerAgent:
    def __init__(self):
        # Create tool instances
        self.data_tool = create_data_query_tool()
        self.stats_tool = create_stats_tool()
        self.time_tool = create_time_analysis_tool()
        self.comparison_tool = create_comparison_tool()
        self.ranking_tool = create_ranking_tool()
        self.multi_metric_tool = create_multi_metric_tool()
        self.trend_tool = create_trend_tool()
        self.network_graph_tool = create_network_graph_tool()
        self.transaction_resolver_tool = create_transaction_resolver_tool()
        self.date_query_tool = create_date_query_tool()
        self.correlation_tool = create_correlation_tool()
        
        self.tools = [self.data_tool, self.stats_tool, self.time_tool, self.comparison_tool, self.ranking_tool, self.multi_metric_tool, self.trend_tool, self.network_graph_tool, self.transaction_resolver_tool, self.date_query_tool, self.correlation_tool]
        
        # Create a lookup dict for tool execution
        self.tool_map = {
            "query_transaction_data": self.data_tool,
            "statistical_analysis": self.stats_tool,
            "time_analysis_tool": self.time_tool,
            "comparison_tool": self.comparison_tool,
            "ranking_tool": self.ranking_tool,
            "multi_metric_tool": self.multi_metric_tool,
            "trend_tool": self.trend_tool,
            "network_graph_tool": self.network_graph_tool,
            "transaction_resolver_tool": self.transaction_resolver_tool,
            "date_query_tool": self.date_query_tool,
            "correlation_importance_tool": self.correlation_tool
        }

        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        ).bind_tools(self.tools)
    
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert data analyst.

CRITICAL ANTI-HALLUCINATION RULE: When a user asks about transactions on a specific date (e.g., 'how many transactions on 2024-12-30'), you MUST call date_query_tool BEFORE generating any response. NEVER estimate, calculate, or infer transaction counts for specific dates from memory or from dataset-wide statistics. The answer must come directly from date_query_tool's output. Returning the full dataset size as a daily count is ALWAYS wrong — daily counts are a small fraction of 250,000.

You are given a structured execution plan.
Use the appropriate tools to execute the plan.
Return the final results clearly.

Available tools:
- query_transaction_data: Execute queries on transaction data. Input: execution_plan (JSON string with filters, groupby, aggregations, sort, limit)
- statistical_analysis: Perform statistical analysis. Input: analysis_type (failure_rate, fraud_rate, correlation, distribution, comparison) and parameters (JSON string)
- time_analysis_tool: For ALL time-based and temporal analysis. Use this for questions about peak hours, hourly patterns, day-of-week trends, weekend vs weekday comparisons, time-series trends, and heatmap data. Input: analysis_type (string: peak_hours, hourly_distribution, day_of_week_pattern, weekend_vs_weekday, time_trend, peak_hours_by_category, failure_heatmap_data, hourly_comparison) and parameters (JSON string with optional filters, metric, top_n, smoothing_window, segment_a/segment_b, include_stats).
- comparison_tool: For ALL segment comparison questions — A vs B, which is better, cross-segment analysis. Use for device comparisons, network comparisons, bank comparisons, age group comparisons, state comparisons, and any 'compare X to Y' question. Input: comparison_type (string: head_to_head, multi_segment, cross_segment, metric_comparison, conditional_comparison, ranked_comparison, bank_vs_bank, device_network_matrix) and parameters (JSON string with segment_column, segment_a, segment_b, metric, filters, include_statistical_tests, confidence_level, top_n).
- ranking_tool: For ALL ranking, leaderboard, top-N, bottom-N, and share-of-total questions. Use this when the user asks "which is most/least," "top N," "rank by," "which has highest/lowest," "share of," or "who leads in." Covers state rankings, bank rankings, merchant category rankings, device rankings, age group rankings. Input: ranking_type (string: top_n, bottom_n, full_ranking, share_of_wallet, fraud_ranking, failure_ranking, multi_metric_ranking, pareto_analysis, state_ranking, category_ranking) and parameters (JSON string with dimension, metric, top_n, filters, include_pareto, tier_count, composite_weights).
- multi_metric_tool: For ALL multi-KPI questions requiring several metrics at once on the same dataset. Use this for "complete picture," "full snapshot," "health check," "overall performance," "give me all metrics," "how is X performing," and any question that would otherwise require multiple separate tool calls. Computes count, average amount, failure rate, fraud rate, success rate, and 20+ more metrics in a single pass. Input: analysis_mode (string: snapshot, grouped_snapshot, multi_group_snapshot, segment_profile, health_scorecard, transaction_type_profile, temporal_snapshot, funnel_analysis, anomaly_snapshot, comparative_snapshot) and parameters (JSON string with filters, group_by, include_benchmarks, metrics_to_include).
- trend_tool: For ALL time-series and trend questions. Use this when questions involve how a metric changes over time, whether something is increasing or decreasing, trend direction, patterns across hours or days, trajectory analysis, or SMA smoothing. Use this for questions containing words like "trend," "over time," "increasing," "decreasing," "pattern," "trajectory," "moving average," "how does X change," "getting better/worse," "rising/falling," and "across the day/week." Input: trend_type (string: hourly_trend, daily_trend, date_trend, multi_metric_trend, segmented_trend, rolling_anomaly_trend, acceleration_trend, comparative_period_trend, cumulative_trend, volatility_trend) and parameters (JSON string with metric, time_granularity, smoothing_window, smoothing_method, filters, segment_column, segment_values, secondary_metrics, include_forecast, period_a_filter, period_b_filter, period_a_label, period_b_label).
- network_graph_tool: For ALL P2P network relationship analysis, money flow graph analysis, cycle detection, round-tripping detection, money mule identification, hub detection, centrality analysis, community detection, and PageRank analysis. Use this when questions involve P2P money flow patterns, circular transactions, suspicious sender-receiver relationships, network structure, or graph-based fraud detection. This tool exclusively analyzes P2P transactions — it automatically filters to transaction_type == 'P2P' before building the graph. For non-P2P transaction analysis, use other tools. Input: graph_analysis_type (string: graph_overview, cycle_detection, degree_centrality, hub_identification, flow_analysis, community_detection, path_analysis, temporal_graph_analysis, pagerank_analysis, composite_fraud_graph) and parameters (JSON string with time_window_hours, top_n_hubs, min_cycle_length, max_cycle_length, filters, include_amount_weights, status_filter, min_transaction_count, centrality_threshold, pagerank_damping, community_resolution, node_a, node_b).
- date_query_tool: Use this tool for ALL questions involving specific calendar dates, date ranges, months, or any query where the user mentions an actual date like '2024-12-30' or 'December' or 'last week.' This is the ONLY tool in the system that can filter by calendar date — no other tool can do this. Use query_type 'single_date' for specific date questions, 'date_range' for date spans, 'month_breakdown' for single month queries, 'month_comparison' for comparing two or more months side by side (e.g. 'January vs February 2024', 'compare Q1 months'), 'date_comparison' for comparing specific dates, 'date_ranking' for finding busiest/quietest dates, 'calendar_context' for date context and peer comparisons, 'relative_date' for relative time references, 'date_distribution' for volume distribution, 'weekday_vs_weekend_by_date' for weekend vs weekday by actual dates, 'date_anomaly' for unusual days. Input: query_type (string) and parameters (JSON string with date, start_date, end_date, month, year, months_list, dates_list, reference_date, relative_period, metric, filters, include_hourly_breakdown).
- transaction_resolver_tool: Use this WHENEVER a user asks for actual transaction IDs, specific transaction records, raw evidence behind a finding, or drill-down details after any prior analysis. This is the ONLY tool that returns individual transaction rows and IDs. Use resolution_mode "context_aware_resolver" when the user asks "show me the transactions" or "give me the IDs" after a prior tool output — pass the prior output as prior_tool_output parameter. Use "criteria_based" for direct filtering requests. Use "profile_based_resolver" for natural language transaction descriptions. NEVER return empty transaction lists — if no transactions match, explain why and suggest alternative criteria. Input: resolution_mode (string) and parameters (JSON string with filters, top_n, sort_by, prior_tool_output, prior_tool_name, user_intent, node_id, cycle_nodes, community_id).

CRITICAL ANTI-HALLUCINATION RULE: When a user asks for transaction IDs or specific transactions after a prior analysis, ALWAYS call transaction_resolver_tool before generating a response. NEVER generate transaction IDs, amounts, or transaction details from memory or inference — only report what transaction_resolver_tool actually returns. If the tool returns zero transactions, report zero and explain why — never invent transaction data.

CRITICAL CHAINING RULE: When a query requires first finding suspicious patterns AND then retrieving the underlying transactions, chain two tool calls: first call the appropriate analysis tool (network_graph_tool, anomaly_detection_tool, etc.), then call transaction_resolver_tool with resolution_mode='context_aware_resolver' passing the first tool's complete output as prior_tool_output.

CRITICAL DISTINCTION — date_query_tool vs time_analysis_tool vs trend_tool:
- date_query_tool — handles actual calendar dates by parsing the timestamp column — use for any question mentioning a specific date, date range, or month. This is the ONLY tool that can filter by calendar date.
- time_analysis_tool — handles hour-of-day and day-of-week patterns using pre-derived integer columns — use for 'peak hours' and 'busiest day of week' questions.
- trend_tool — handles time-series smoothing and direction — use for 'is volume trending up' questions.

CRITICAL DISTINCTION — time_analysis_tool vs trend_tool:
- time_analysis_tool is for SNAPSHOT comparisons at time points — "what is the failure rate at 7 PM" or "which hour has the most transactions" — static aggregations at specific times.
- trend_tool is for DIRECTIONAL MOVEMENT across time — "is failure rate rising or falling through the day" or "show me how transaction volume moves with a smoothed trend line" — dynamic sequences showing change over time.

Tool Selection Guidelines:
- For ANY question involving hours, time of day, peak periods, or temporal patterns → use time_analysis_tool
- For weekend/weekday comparisons → use time_analysis_tool
- For day-of-week analysis → use time_analysis_tool
- For comparing two or more segments (e.g. Android vs iOS, 4G vs 5G, Bank A vs Bank B) → use comparison_tool
- For 'which is better/worse' between two specific segments → use comparison_tool
- For device × network matrix analysis → use comparison_tool
- For ranking, top-N, bottom-N, leaderboard, share-of-total, or distribution questions → use ranking_tool
- For 'which has highest/lowest', 'which is most/least', 'rank all', 'top N by' → use ranking_tool
- For Pareto / 80-20 concentration analysis → use ranking_tool
- For share-of-wallet or value distribution across segments → use ranking_tool
- For fraud or failure ranking across segments → use ranking_tool
- For ANY question mentioning a specific date (YYYY-MM-DD, 'December 30', 'on that day', 'this month', 'in December', 'daily count', 'how many on', 'transactions on', 'what happened on', 'last week', 'yesterday', a 4-digit year, a month name) → ALWAYS use date_query_tool FIRST
- For comparing two or more months (e.g. 'January vs February 2024', 'compare months') → use date_query_tool with query_type='month_comparison' and months_list parameter
- For general data queries without time, comparison, or ranking focus → use query_transaction_data
- For statistical tests (correlation, distribution) without time, comparison, or ranking focus → use statistical_analysis
- For ANY question needing multiple metrics at once (snapshot, health check, full picture, overall performance, dashboard, scorecard, funnel, profile, anomaly check, executive summary) → use multi_metric_tool
- For 'how is X performing', 'give me a complete picture of', 'health check', 'full breakdown', 'all metrics' → use multi_metric_tool
- For trend, over time, increasing, decreasing, rising, falling, trajectory, pattern, moving average, SMA, forecast → use trend_tool
- For 'is X getting better/worse', 'show me how X changes across the day', 'trend line', 'smooth', 'momentum', 'acceleration', 'volatility' → use trend_tool
- For comparing trends between segments (e.g. Android vs iOS trend) → use trend_tool with segmented_trend
- For comparing trend between periods (weekday vs weekend trend) → use trend_tool with comparative_period_trend
- For cumulative totals over time, 'by what hour does 50%' → use trend_tool with cumulative_trend
- For anomaly spikes in trends, 'flag unusual points' → use trend_tool with rolling_anomaly_trend
- For P2P network, money flow, round trip, cycle, circular, mule, hub, centrality, graph, network, sender receiver relationship, money laundering, layering, community, PageRank, path between, flow between, who sends to whom, circular transaction → use network_graph_tool
- For P2P network overview, topology → use network_graph_tool with graph_overview
- For finding circular money flows or round-tripping → use network_graph_tool with cycle_detection
- For identifying money mules or aggregation hubs → use network_graph_tool with hub_identification
- For comprehensive fraud risk assessment of P2P network → use network_graph_tool with composite_fraud_graph
- For transaction IDs, show me the transactions, give me the records, actual transactions, drill down, evidence, which transactions, list transactions, transaction details, specific records, raw data, verify, show proof → ALWAYS use transaction_resolver_tool
- For "show me the transactions behind that finding" after any prior analysis → use transaction_resolver_tool with context_aware_resolver, passing prior output
- For retrieving transactions by explicit ID → use transaction_resolver_tool with direct_lookup
- For transactions matching a natural language description → use transaction_resolver_tool with profile_based_resolver
- For transactions in a specific time window → use transaction_resolver_tool with time_window_resolver
- For transactions from a ranked segment → use transaction_resolver_tool with ranking_resolver
- For transactions from a comparison segment → use transaction_resolver_tool with comparison_resolver
- For transactions involving a graph hub node → use transaction_resolver_tool with graph_hub_resolver
- For transactions forming a detected cycle → use transaction_resolver_tool with graph_cycle_resolver
- For transactions within a community cluster → use transaction_resolver_tool with graph_community_resolver
- For transactions flagged as anomalous → use transaction_resolver_tool with anomaly_resolver
- For transactions appearing in multiple findings → use transaction_resolver_tool with multi_finding_resolver

Anti-Redundancy Rule: When a question requires 3 or more metrics about the same filtered dataset, ALWAYS use multi_metric_tool instead of calling data_tools or stats_tools multiple times. Multi_metric_tool computes everything in one pass and is always more efficient for multi-KPI questions.
"""),
            ("human", "{input}")
        ])

        self.chain = self.prompt | self.llm

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool and return its result"""
        if tool_name not in self.tool_map:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        
        tool = self.tool_map[tool_name]
        try:
            # Invoke the tool with its arguments
            result = tool.invoke(tool_args)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def analyze(self, execution_plan: dict):
        """Execute analysis based on execution plan"""

        # ------------------------------------------------------------------
        # Fast-path: if the planner already resolved a high-confidence tool,
        # skip the LLM tool-selection entirely and execute deterministically.
        # This avoids cases where the LLM picks the wrong tool or produces
        # an invalid tool-call schema that Groq rejects.
        # ------------------------------------------------------------------
        suggested = execution_plan.get("suggested_tool")
        intent = execution_plan.get("analysis_intent", "")
        HIGH_CONFIDENCE_INTENTS = {"drill_down", "network_analysis", "date_query"}
        if suggested and suggested in self.tool_map and intent in HIGH_CONFIDENCE_INTENTS:
            print(f"  🎯 High-confidence routing → {suggested} (intent={intent})")
            return self._deterministic_fallback(execution_plan)

        # Detect if this is a time-related query and add routing hint
        trend_keywords = ['trend', 'over time', 'increasing', 'decreasing', 'rising',
                         'falling', 'pattern', 'trajectory', 'moving average', 'smooth',
                         'time series', 'hourly pattern', 'daily pattern', 'getting worse',
                         'getting better', 'change over', 'across hours', 'across days',
                         'forecast', 'predict next', 'momentum', 'acceleration',
                         'accelerat', 'decelerat', 'rate of change', 'speeding up',
                         'slowing down',
                         'volatility', 'sma', 'cumulative', 'anomaly trend',
                         'trend line', 'how does', 'moves across']
        time_keywords = ['hour_of_day', 'day_of_week', 'is_weekend', 'peak', 'hourly', 
                         'temporal', 'time', 'weekend', 'weekday', 'daily']
        comparison_keywords = ['compare', 'vs', 'versus', 'difference', 'better', 'worse',
                               'android', 'ios', '4g', '5g', 'device', 'network']
        ranking_keywords = ['rank', 'top', 'bottom', 'most', 'least', 'highest', 'lowest',
                            'best', 'worst', 'which', 'leading', 'share', 'dominant',
                            'dominates', 'dominate', 'wallet', 'share-of-wallet',
                            'popular', 'concentrate', 'pareto', 'leaderboard', 'state',
                            'category', 'distribution']
        multi_metric_keywords = ['overall', 'complete', 'full', 'all metrics', 'snapshot',
                                  'dashboard', 'health', 'performance', 'profile', 'how is',
                                  'tell me about', 'breakdown', 'summary', 'scorecard',
                                  'funnel', 'overview', 'anomal', 'compare all',
                                  'complete picture', 'health check', 'kpi']
        network_graph_keywords = ['p2p network', 'money flow', 'round trip', 'round-trip',
                                   'cycle', 'circular', 'mule', 'hub', 'centrality',
                                   'graph', 'network analysis', 'sender receiver',
                                   'money laundering', 'layering', 'community detection',
                                   'pagerank', 'path between', 'flow between',
                                   'who sends to whom', 'circular transaction',
                                   'money mule', 'aggregation hub', 'round tripping',
                                   'network graph', 'p2p relationship', 'p2p pattern']
        date_query_keywords = ['2024', '2025', '2023', 'january', 'february', 'march', 'april',
                               'may', 'june', 'july', 'august', 'september', 'october',
                               'november', 'december', 'on that day', 'that date', 'yesterday',
                               'last week', 'this month', 'in december', 'during q4', 'calendar',
                               'daily count', 'how many on', 'transactions on', 'what happened on',
                               'specific date', 'date range', 'month breakdown', 'which date',
                               'busiest date', 'quietest date', 'compare dates', 'date comparison',
                               'on 2024', 'on 2025', 'dec 30', 'dec 31', 'jan 1',
                               'weekend vs weekday by date', 'anomalous day', 'unusual day']
        transaction_resolver_keywords = ['transaction id', 'transaction ids', 'show me the transactions',
                                          'give me the records', 'actual transactions', 'drill down',
                                          'evidence', 'which transactions', 'list transactions',
                                          'transaction details', 'specific records', 'raw data',
                                          'verify', 'show proof', 'give me the ids',
                                          'show me the actual', 'underlying transactions',
                                          'transaction_id', 'txn id', 'show the records',
                                          'retrieve transactions', 'get transactions']
        correlation_keywords = [
            'what drives', 'what factors', 'which factors', 'most influence',
            'most influential', 'feature importance', 'what predicts', 'what causes',
            'strongest predictor', 'cramers', "cramer's", 'cramér', 'association matrix',
            'interaction between', 'interaction effect', 'does x affect',
            'combination of', 'riskiest combination', 'worst combination',
            'which bank and device', 'multivariate', 'point biserial',
            'amount correlate', 'amount and fraud', 'higher value transactions',
            'what combination', 'which combination', 'rank the factors',
            'rank factors', 'rank columns', 'which column', 'which columns predict'
        ]
        plan_str = json.dumps(execution_plan).lower()
        is_date_query = any(keyword in plan_str for keyword in date_query_keywords)
        # Also detect date patterns (YYYY-MM-DD, DD/MM/YYYY, etc.)
        import re as _re
        is_date_query = is_date_query or bool(_re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', plan_str))
        is_date_query = is_date_query or bool(_re.search(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b', plan_str))
        is_transaction_resolver_query = any(keyword in plan_str for keyword in transaction_resolver_keywords)
        is_correlation_query = any(keyword in plan_str for keyword in correlation_keywords)
        is_trend_query = any(keyword in plan_str for keyword in trend_keywords)
        is_time_query = any(keyword in plan_str for keyword in time_keywords)
        is_comparison_query = any(keyword in plan_str for keyword in comparison_keywords)
        is_ranking_query = any(keyword in plan_str for keyword in ranking_keywords)
        is_multi_metric_query = any(keyword in plan_str for keyword in multi_metric_keywords)
        is_network_graph_query = any(keyword in plan_str for keyword in network_graph_keywords)
        
        if is_date_query and not is_transaction_resolver_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves specific calendar dates or date-based analysis.
Use the date_query_tool for this analysis. Choose the appropriate query_type:
- single_date: Retrieve all metrics for one specific calendar date (e.g. 'how many transactions on 2024-12-30')
- date_range: Aggregated and day-by-day metrics across a span of dates
- month_breakdown: Full day-by-day breakdown for an entire month
- month_comparison: Compare metrics between two or more months side by side (e.g. 'January vs February 2024'). Parameters: months_list (list of {month, year} dicts or 'Month YYYY' strings)
- date_comparison: Compare metrics between two or more specific dates side by side
- date_ranking: Rank all dates by a chosen metric (busiest/quietest days)
- calendar_context: Full calendar context for a date with peer comparisons
- relative_date: Query using relative references like 'last 7 days', 'weekly average'
- date_distribution: Transaction volume distribution across all dates
- weekday_vs_weekend_by_date: Compare actual weekend vs weekday dates in a range
- date_anomaly: Identify dates with unusual metric deviations

Parameters JSON should include: date (string), start_date, end_date, month (int), year (int), months_list (list of {month, year} dicts or 'Month YYYY' strings), dates_list (list), reference_date, relative_period, metric, filters (list), top_n (int), include_hourly_breakdown (bool), include_benchmarks (bool), anomaly_threshold_multiplier (float).
For month-vs-month comparisons (e.g. 'January vs February 2024'), use query_type='month_comparison' with months_list=[{"month":1,"year":2024},{"month":2,"year":2024}].
This is the ONLY tool that can filter by actual calendar dates. Do NOT use time_analysis_tool or trend_tool for date-specific queries.
"""
        elif is_transaction_resolver_query:
            routing_hint = """\n\n**IMPORTANT**: This query asks for specific transaction IDs, records, or drill-down evidence.
Use the transaction_resolver_tool for this analysis. Choose the appropriate resolution_mode:
- direct_lookup: Retrieve transactions by explicit transaction_id list
- criteria_based: Retrieve transactions matching column filter criteria
- graph_hub_resolver: Retrieve transactions involving a specific hub node from network_graph_tool
- graph_cycle_resolver: Retrieve transactions forming a detected cycle from network_graph_tool
- graph_community_resolver: Retrieve internal transactions within a community cluster
- anomaly_resolver: Retrieve transactions flagged as anomalous by anomaly_detection_tool
- ranking_resolver: Retrieve transactions from a ranked segment
- comparison_resolver: Retrieve transactions from a comparison segment
- time_window_resolver: Retrieve transactions within a specific time window
- profile_based_resolver: Parse natural language profile into filters and retrieve matching transactions
- multi_finding_resolver: Retrieve transactions appearing in multiple findings (intersection)
- context_aware_resolver: Auto-determine criteria from prior tool output and user intent

Parameters JSON should include: filters (list), top_n (int), sort_by (string), prior_tool_output (string), prior_tool_name (string), user_intent (string), node_id (string), cycle_nodes (list), community_id (int), transaction_ids (list), segment_column (string), segment_value (string), profile_description (string).
NEVER generate transaction IDs from memory — only report what the tool returns.
"""
        elif is_network_graph_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves P2P network relationship or graph-based analysis.
Use the network_graph_tool for this analysis. Choose the appropriate graph_analysis_type:
- graph_overview: Build the P2P graph and return fundamental topology statistics
- cycle_detection: Find circular money flows within a specified time window (for round-tripping, layering detection)
- degree_centrality: Compute in-degree, out-degree, and total degree centrality for all nodes
- hub_identification: Identify potential money mules and aggregation hubs with abnormally high in-degree
- flow_analysis: Analyze total money flow volume and direction between node pairs
- community_detection: Find clusters of nodes that interact more with each other than with the rest
- path_analysis: Find paths between two specified nodes (requires node_a and node_b)
- temporal_graph_analysis: Analyze how graph structure changes across time-of-day buckets
- pagerank_analysis: Apply PageRank to identify high-influence nodes in the money flow network
- composite_fraud_graph: Combine cycle detection + hub identification + PageRank + community detection into unified fraud risk report

Parameters JSON should include: status_filter (list), time_window_hours (int), min_cycle_length (int), max_cycle_length (int), top_n_hubs (int), filters (list), include_amount_weights (bool), centrality_threshold (float), pagerank_damping (float), community_resolution (float), node_a/node_b (for path_analysis).
This tool exclusively analyzes P2P transactions. For non-P2P analysis, use other tools.
"""
        elif is_trend_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves trend or time-series analysis.
Use the trend_tool for this analysis. Choose the appropriate trend_type:
- hourly_trend: 24-hour cycle analysis for a metric with SMA smoothing
- daily_trend: 7-day weekly cycle analysis (Monday–Sunday)
- date_trend: Calendar date-level temporal progression
- multi_metric_trend: Multiple metrics tracked simultaneously on the same time axis
- segmented_trend: Same metric trended separately for two or more segments (e.g., Android vs iOS)
- rolling_anomaly_trend: Trend line plus anomaly detection bands (±2σ)
- acceleration_trend: Rate of change and acceleration analysis
- comparative_period_trend: Compare trend patterns between two time periods (e.g., weekday vs weekend)
- cumulative_trend: Running cumulative total of a metric over time
- volatility_trend: Rolling standard deviation — measures stability vs instability

Parameters JSON should include: metric (volume, failure_rate, success_rate, fraud_rate, avg_amount, total_amount, pending_rate, fraud_by_value_rate), time_granularity (hour, day_of_week, date), smoothing_window (int), filters (list), and mode-specific keys.
"""
        elif is_multi_metric_query:
            routing_hint = """\n\n**IMPORTANT**: This query requires multiple metrics or a comprehensive analysis.
Use the multi_metric_tool for this analysis. Choose the appropriate analysis_mode:
- snapshot: Full KPI snapshot of a filtered dataset (no grouping)
- grouped_snapshot: Full KPI snapshot grouped by one dimension column
- multi_group_snapshot: Full KPI snapshot grouped by two dimensions simultaneously
- segment_profile: Deep profile of a specific segment with benchmarking
- health_scorecard: Structured health check with letter grade and risk flags
- transaction_type_profile: Breakdown across all four transaction types
- temporal_snapshot: Metrics split by peak/off-peak hours and weekend/weekday
- funnel_analysis: Transaction success funnel with drop-off rates
- anomaly_snapshot: Standard snapshot with anomaly detection flags
- comparative_snapshot: Compare two filtered subsets side by side

Parameters JSON should include: filters (list), group_by (string or list), include_benchmarks (bool), segment_a_filters/segment_b_filters (for comparative).
When a question requires 3 or more metrics, ALWAYS prefer multi_metric_tool over calling other tools separately.
"""
        elif is_time_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves time-based analysis. 
Use the time_analysis_tool for this analysis. Choose the appropriate analysis_type:
- peak_hours: Find busiest hours
- hourly_distribution: Full 24-hour breakdown
- day_of_week_pattern: Daily patterns across the week
- weekend_vs_weekday: Compare weekend vs weekday metrics
- time_trend: Rolling average trends
- peak_hours_by_category: Peak hours filtered by category/type
- failure_heatmap_data: Hour x Day failure rate matrix
- hourly_comparison: Compare two segments across hours
"""
        elif is_ranking_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves ranking, leaderboard, or share-of-total analysis.
Use the ranking_tool for this analysis. Choose the appropriate ranking_type:
- top_n: Rank dimension values and return the top N (e.g. top 5 banks by volume)
- bottom_n: Return worst performers (e.g. bottom 3 states by success rate)
- full_ranking: Complete ranked list of all unique values with tiers
- share_of_wallet: Distribution of transaction value across segments
- fraud_ranking: Rank by fraud rate with volume context and risk scores
- failure_ranking: Rank by failure rate with revenue impact estimates
- multi_metric_ranking: Composite score across multiple weighted metrics
- pareto_analysis: Identify 80-20 concentration patterns
- state_ranking: Deep state-level ranking with regional grouping
- category_ranking: Deep merchant category ranking for P2M transactions

Parameters JSON should include: dimension (column to rank), metric (volume, total_amount, avg_amount, failure_rate, fraud_rate, success_rate), top_n (int), filters (list).
"""
        elif is_comparison_query:
            routing_hint = """\n\n**IMPORTANT**: This query involves segment comparison.
Use the comparison_tool for this analysis. Choose the appropriate comparison_type:
- head_to_head: Compare two specific values on the same column (e.g. Android vs iOS)
- multi_segment: Compare all values of a column with ranking
- cross_segment: Compare values from different columns (e.g. UPI payments vs Android users)
- metric_comparison: Side-by-side metric table for two segments
- conditional_comparison: Compare within a filtered subset with filter impact analysis
- ranked_comparison: Rank all segment values by a metric with gap/cliff detection
- bank_vs_bank: Deep bank comparison with breakdowns by txn type and device
- device_network_matrix: Full device × network matrix with hotspot detection
"""
        elif is_correlation_query:
            routing_hint = """\n\n**IMPORTANT**: This query asks for correlation, feature importance, or factor analysis.
Use the correlation_importance_tool. Choose the appropriate analysis_type:
- feature_importance: Rank all factors by their association with failure/fraud/success rate. 
  Parameters: target (failure/fraud/success), filters (list)
- cramers_v_matrix: Full pairwise Cramér's V association matrix across all categorical columns.
  Parameters: include_geography (bool), filters (list)
- interaction_effects: Detect how two factors interact to affect the target rate.
  Parameters: factor_a (column), factor_b (column), target, filters, min_sample_size
- multivariate_combination: Find riskiest/safest combinations of 2-4 factors simultaneously.
  Parameters: factors (list of columns), target, top_n, min_sample_size, filters
- point_biserial: Correlation between amount_inr and a binary outcome (fraud/failure).
  Parameters: continuous_var (default amount_inr), binary_target, filters, include_distribution, segment_by

Parameters JSON should include: target (string), filters (list), factor_a, factor_b, factors (list), 
top_n (int), min_sample_size (int), include_geography (bool), segment_by (string).
"""
        else:
            routing_hint = ""

        input_text = f"""
Execute this analysis plan:

{json.dumps(execution_plan, indent=2)}
{routing_hint}
Use the most appropriate tool based on the analysis requirements.
"""

        try:
            # First LLM call - may request tool calls
            result = self.chain.invoke({"input": input_text})
        except Exception as llm_err:
            print(f"  ⚠️ LLM tool-call failed: {llm_err}")
            print(f"  🔄 Falling back to deterministic tool execution...")
            return self._deterministic_fallback(execution_plan)
        
        # Check if LLM wants to call tools
        if hasattr(result, 'tool_calls') and result.tool_calls:
            # Store all tool results
            all_tool_results = []
            
            for tool_call in result.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']

                # Fix: LLM sometimes passes 'parameters' as dict instead of
                # the JSON string the tool schema requires.  Coerce it.
                if 'parameters' in tool_args and not isinstance(tool_args['parameters'], str):
                    tool_args['parameters'] = json.dumps(tool_args['parameters'])
                
                print(f"  ⚙️ Executing tool: {tool_name}")
                
                # Actually execute the tool
                tool_result = self._execute_tool(tool_name, tool_args)
                all_tool_results.append({
                    "tool": tool_name,
                    "result": tool_result
                })
            
            # Return the actual tool execution results
            return {
                "tool_calls": len(all_tool_results),
                "results": all_tool_results
            }
        
        # If no tool calls, return the content (fallback)
        if hasattr(result, 'content') and result.content:
            return {"response": result.content}
        
        return {"error": "No results generated"}
    
    # ----------------------------------------------------------------
    #  Deterministic fallback — bypass LLM when tool-call fails
    # ----------------------------------------------------------------
    def _deterministic_fallback(self, execution_plan: dict) -> dict:
        """
        When the LLM tool-binding call fails (e.g. Groq schema validation
        error), use the execution_plan's routing signals to directly invoke
        the correct tool without needing the LLM.
        """
        suggested = execution_plan.get("suggested_tool")
        intent = execution_plan.get("analysis_intent", "")
        filters = execution_plan.get("filters", [])
        plan_str = json.dumps(execution_plan).lower()

        # Also use original_question for keyword matching when plan is sparse
        original_question = execution_plan.get("original_question", "")
        if original_question:
            plan_str = plan_str + " " + original_question.lower()

        # --- Determine tool name ---
        tool_name = None
        if suggested and suggested in self.tool_map:
            tool_name = suggested
        else:
            # Infer from intent
            INTENT_TOOL = {
                "drill_down": "transaction_resolver_tool",
                "descriptive": "query_transaction_data",
                "comparative": "comparison_tool",
                "temporal": "time_analysis_tool",
                "segmentation": "ranking_tool",
                "correlation": "correlation_importance_tool",
                "risk_analysis": "statistical_analysis",
                "trend": "trend_tool",
                "date_query": "date_query_tool",
                "network_analysis": "network_graph_tool",
            }
            tool_name = INTENT_TOOL.get(intent)

        # If still no tool, try keyword-based inference from plan_str
        if not tool_name or tool_name not in self.tool_map:
            if any(kw in plan_str for kw in ["rank", "top ", "bottom ", "most ", "least ",
                                              "highest", "lowest", "leaderboard", "state_ranking"]):
                tool_name = "ranking_tool"
            elif any(kw in plan_str for kw in ["compare", " vs ", "versus"]):
                tool_name = "comparison_tool"
            elif any(kw in plan_str for kw in ["trend", "over time", "increasing"]):
                tool_name = "trend_tool"
            elif any(kw in plan_str for kw in ["peak", "hourly", "weekend"]):
                tool_name = "time_analysis_tool"

        # --- Re-route: share-of-wallet / "across all" queries belong in
        #     ranking_tool even if the LLM or intent tagged them comparative.
        if tool_name == "comparison_tool":
            sow_keywords = ["share of wallet", "share-of-wallet", "across all",
                            "all age group", "all bank", "all state", "all categor",
                            "all device", "all network", "dominates", "dominate",
                            "distribution across", "breakdown across"]
            if any(kw in plan_str for kw in sow_keywords):
                tool_name = "ranking_tool"
                execution_plan["tool_subtype"] = "share_of_wallet"
                print("  🔀 Re-routing comparison → ranking_tool (share-of-wallet detected)")

        if not tool_name or tool_name not in self.tool_map:
            return {"error": "Deterministic fallback could not determine correct tool."}

        # --- Build tool arguments based on tool ---
        tool_args = self._build_fallback_args(tool_name, execution_plan)

        print(f"  ⚙️ Deterministic fallback → {tool_name}")
        tool_result = self._execute_tool(tool_name, tool_args)
        return {
            "tool_calls": 1,
            "results": [{"tool": tool_name, "result": tool_result}],
        }

    def _build_fallback_args(self, tool_name: str, plan: dict) -> dict:
        """Build tool invocation args from the execution plan for fallback."""
        filters = plan.get("filters", [])
        limit = plan.get("limit", 50)

        if tool_name == "transaction_resolver_tool":
            subtype = plan.get("tool_subtype", "criteria_based")
            if subtype not in {"direct_lookup", "criteria_based", "profile_based_resolver",
                               "context_aware_resolver", "graph_hub_resolver",
                               "graph_cycle_resolver", "graph_community_resolver",
                               "anomaly_resolver", "ranking_resolver",
                               "comparison_resolver", "time_window_resolver",
                               "multi_finding_resolver"}:
                subtype = "criteria_based"
            params = {"filters": filters, "top_n": limit, "sort_by": "amount_inr", "sort_ascending": False}
            desc = plan.get("resolver_description", "")
            if desc:
                params["profile_description"] = desc
            return {"resolution_mode": subtype, "parameters": json.dumps(params)}

        if tool_name == "query_transaction_data":
            return {"execution_plan": json.dumps({
                "filters": filters,
                "groupby": plan.get("groupby", []),
                "aggregations": plan.get("aggregations", []),
                "sort": plan.get("sort"),
                "limit": limit,
            })}

        if tool_name == "comparison_tool":
            seg_col = plan.get("segment_column", "")
            # Infer segment_column from original question when planner left it empty
            if not seg_col:
                orig_q = plan.get("original_question", "").lower()
                col_hints = [
                    (["age group", "age_group"], "sender_age_group"),
                    (["state", "states", "india"], "sender_state"),
                    (["bank", "banks"], "sender_bank"),
                    (["device", "android", "ios"], "device_type"),
                    (["network", "4g", "5g", "wifi"], "network_type"),
                    (["category", "merchant"], "merchant_category"),
                    (["transaction type", "txn type"], "transaction_type"),
                ]
                for keywords, col_name in col_hints:
                    if any(kw in orig_q for kw in keywords):
                        seg_col = col_name
                        break
                if not seg_col:
                    seg_col = "device_type"

            seg_a = plan.get("segment_a")
            seg_b = plan.get("segment_b")
            subtype = plan.get("tool_subtype", "head_to_head")

            # If both segment values are missing, head_to_head is impossible;
            # switch to multi_segment so the tool compares all values.
            if subtype == "head_to_head" and not seg_a and not seg_b:
                subtype = "multi_segment"

            params = {
                "segment_column": seg_col,
                "segment_a": seg_a,
                "segment_b": seg_b,
                "filters": filters,
                "include_statistical_tests": True,
            }
            return {"comparison_type": subtype,
                     "parameters": json.dumps(params)}

        if tool_name == "ranking_tool":
            # Determine subtype and dimension intelligently
            VALID_RANKING_TYPES = {"top_n", "bottom_n", "full_ranking", "share_of_wallet",
                                   "fraud_ranking", "failure_ranking", "multi_metric_ranking",
                                   "pareto_analysis", "state_ranking", "category_ranking"}
            subtype = plan.get("tool_subtype", "top_n")
            if subtype not in VALID_RANKING_TYPES:
                subtype = "top_n"  # reset invalid subtypes (e.g. head_to_head from re-routing)
            dimension = plan.get("segment_column",
                                 plan.get("groupby", ["sender_bank"])[0] if plan.get("groupby") else "sender_bank")
            metric = plan.get("metric", "volume")

            # If original question mentions states/India, override to state_ranking
            orig_q = plan.get("original_question", "").lower()
            if orig_q:
                if any(kw in orig_q for kw in ["state", "states", "india", "indian"]):
                    dimension = "sender_state"
                    if subtype in ("top_n", "full_ranking"):
                        subtype = "state_ranking"
                if any(kw in orig_q for kw in ["category", "categories", "merchant"]):
                    dimension = "merchant_category"
                    if subtype in ("top_n", "full_ranking"):
                        subtype = "category_ranking"
                if any(kw in orig_q for kw in ["bank", "banks"]):
                    dimension = "sender_bank"
                if any(kw in orig_q for kw in ["age group", "age_group", "age-group"]):
                    dimension = "sender_age_group"
                if any(kw in orig_q for kw in ["share of wallet", "share-of-wallet",
                                                "dominat", "distribution across",
                                                "breakdown across"]):
                    if subtype in ("top_n", "full_ranking"):
                        subtype = "share_of_wallet"

            params = {
                "dimension": dimension,
                "metric": metric,
                "top_n": limit or 10,
                "filters": filters,
            }
            return {"ranking_type": subtype,
                     "parameters": json.dumps(params)}

        if tool_name == "trend_tool":
            params = {"metric": plan.get("metric", "volume"),
                      "time_granularity": plan.get("time_granularity", "hour"),
                      "filters": filters,
                      "smoothing_window": plan.get("smoothing_window", 3)}
            return {"trend_type": plan.get("tool_subtype", "hourly_trend"),
                     "parameters": json.dumps(params)}

        if tool_name == "date_query_tool":
            date_ref = plan.get("date_reference")
            # Last-resort: extract date from original_question if date_reference is missing
            if not date_ref:
                import re as _re
                orig_q = plan.get("original_question", "")
                dm = _re.search(r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b', orig_q)
                if dm:
                    date_ref = dm.group(1)
                else:
                    dm2 = _re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', orig_q)
                    if dm2:
                        date_ref = dm2.group(1)
                    else:
                        # Try month name + year pattern (e.g. "May 2024", "in december 2024")
                        import calendar as _cal
                        _month_map = {name.lower(): i for i, name in enumerate(_cal.month_name) if i}
                        _month_map.update({name.lower(): i for i, name in enumerate(_cal.month_abbr) if i})
                        for mname, mnum in _month_map.items():
                            if mname in orig_q.lower():
                                ym = _re.search(r'\b(20\d{2})\b', orig_q)
                                if ym:
                                    date_ref = f"{_cal.month_name[mnum]} {ym.group(1)}"
                                    break
            params = {"filters": filters, "date": date_ref, "original_question": plan.get("original_question", "")}
            # For month_breakdown, also extract explicit month/year into params
            query_subtype = plan.get("date_query_subtype", plan.get("tool_subtype", "single_date"))

            # Auto-detect month comparison: if the original question compares
            # two or more months (e.g. "January vs February 2024"), upgrade
            # month_breakdown to month_comparison and build months_list.
            orig_q = plan.get("original_question", "")
            orig_q_lower = orig_q.lower()
            import calendar as _cal_mc
            _mc_month_map = {name.lower(): i for i, name in enumerate(_cal_mc.month_name) if i}
            _mc_month_map.update({name.lower(): i for i, name in enumerate(_cal_mc.month_abbr) if i})
            # Count distinct months mentioned
            mentioned_months = []
            _seen_months = set()
            for mname, mnum in sorted(_mc_month_map.items(), key=lambda x: -len(x[0])):
                if mname in orig_q_lower and mnum not in _seen_months:
                    mentioned_months.append(mnum)
                    _seen_months.add(mnum)
            is_compare_query = any(kw in orig_q_lower for kw in [
                " vs ", "versus", "compare", "comparison", "against",
                "difference between", "compared to",
            ])
            if len(mentioned_months) >= 2 and (is_compare_query or query_subtype in ("month_breakdown", "single_date")):
                # Extract year
                ym_match = _re.search(r'\b(20\d{2})\b', orig_q)
                default_year = int(ym_match.group(1)) if ym_match else 2024
                months_list = [{"month": m, "year": default_year} for m in mentioned_months]
                params["months_list"] = months_list
                query_subtype = "month_comparison"

            if query_subtype == "month_breakdown" and date_ref:
                import re as _re2
                import calendar as _cal2
                _month_map2 = {name.lower(): i for i, name in enumerate(_cal2.month_name) if i}
                _month_map2.update({name.lower(): i for i, name in enumerate(_cal2.month_abbr) if i})
                ref_lower = str(date_ref).lower()
                for mname, mnum in _month_map2.items():
                    if mname in ref_lower:
                        ym2 = _re2.search(r'\b(20\d{2})\b', ref_lower)
                        if ym2:
                            params["month"] = mnum
                            params["year"] = int(ym2.group(1))
                            break
            return {"query_type": query_subtype,
                     "parameters": json.dumps(params)}

        if tool_name == "network_graph_tool":
            params = {"filters": filters, "top_n_hubs": limit or 10}
            return {"graph_analysis_type": plan.get("graph_metric", plan.get("tool_subtype", "graph_overview")),
                     "parameters": json.dumps(params)}

        if tool_name == "statistical_analysis":
            params = {"filters": filters}
            return {"analysis_type": plan.get("tool_subtype", "distribution"),
                     "parameters": json.dumps(params)}

        if tool_name == "correlation_importance_tool":
            subtype = plan.get("tool_subtype", "feature_importance")
            target = plan.get("metric", "failure")
            # Normalize target names
            if target in ("failure_rate", "fail"):
                target = "failure"
            elif target in ("fraud_rate",):
                target = "fraud"
            elif target in ("success_rate",):
                target = "success"
            elif target not in ("failure", "fraud", "success"):
                target = "failure"
            params = {"target": target, "filters": filters}
            if subtype == "interaction_effects":
                params["factor_a"] = plan.get("segment_column", "device_type")
                factor_b = plan.get("segment_b", plan.get("segment_a", "network_type"))
                # If factor_b looks like a value rather than column, fallback
                valid_cols = {"device_type", "network_type", "sender_bank", "sender_age_group",
                              "sender_state", "transaction_type", "merchant_category"}
                if factor_b not in valid_cols:
                    factor_b = "network_type"
                params["factor_b"] = factor_b
                params["min_sample_size"] = 100
            elif subtype == "multivariate_combination":
                factors = plan.get("factors", None)
                if not factors:
                    factors = ["sender_bank", "device_type", "network_type"]
                params["factors"] = factors
                params["top_n"] = plan.get("limit", 15) or 15
                params["min_sample_size"] = 200
            elif subtype == "cramers_v_matrix":
                params["include_geography"] = False
            elif subtype == "point_biserial":
                params["continuous_var"] = "amount_inr"
                params["binary_target"] = target
                params["include_distribution"] = True
            return {"analysis_type": subtype,
                     "parameters": json.dumps(params)}

        # Generic fallback
        return {"execution_plan": json.dumps(plan)}